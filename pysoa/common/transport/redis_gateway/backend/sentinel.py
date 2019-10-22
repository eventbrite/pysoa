from __future__ import (
    absolute_import,
    unicode_literals,
)

import logging
import random
import time
from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Optional,
    Tuple,
)

import redis
import redis.sentinel
import six

from pysoa.common.transport.redis_gateway.backend.base import (
    BaseRedisClient,
    CannotGetConnectionError,
)


_logger = logging.getLogger(__name__)


class SentinelRedisClient(BaseRedisClient):
    """
    Variant of the Redis client that supports the Redis Sentinel HA protocol.

    Supports sharding, but assumes that there is only one sentinel cluster with multiple Redis services
    monitored by that cluster. So, this will only connect to a single cluster of Sentinel servers,
    but will support sharding by asking that sentinel cluster for different services. Also, any Redis connection
    options (socket timeout, socket keepalive, etc) will be assumed to be identical across Redis server, and
    across all services.

    "hosts" in this arrangement, is used to list the Redis sentinel hosts. As such, it only supports the
    tuple method of specifying hosts, as that's all the Redis sentinel python library supports at the moment.

    "services" is the list of Redis services monitored by the sentinel system that Redis keys will be distributed
     across. If services is empty, this will fetch all services from Sentinel at initialization.
    """

    def __init__(
        self,
        hosts=None,  # type: Optional[Iterable[Tuple[six.text_type, int]]]
        connection_kwargs=None,  # type: Dict[six.text_type, Any]
        sentinel_services=None,  # type: Iterable[six.text_type]
        sentinel_failover_retries=0,  # type: int
    ):
        # type: (...) -> None
        # Master client caching
        self._master_clients = {}  # type: Dict[six.text_type, redis.StrictRedis]

        # Master failover behavior
        if sentinel_failover_retries < 0:
            raise ValueError('sentinel_failover_retries must be >= 0')
        self._sentinel_failover_retries = sentinel_failover_retries

        connection_kwargs = dict(connection_kwargs) if connection_kwargs else {}
        if 'socket_connect_timeout' not in connection_kwargs:
            connection_kwargs['socket_connect_timeout'] = 5.0  # so that we don't wait indefinitely during failover
        if 'socket_keepalive' not in connection_kwargs:
            connection_kwargs['socket_keepalive'] = True

        self._sentinel = redis.sentinel.Sentinel(
            self._setup_hosts(hosts),
            sentinel_kwargs={'socket_connect_timeout': 5.0, 'socket_timeout': 5.0, 'socket_keepalive': True},
            **connection_kwargs
        )
        if sentinel_services:
            self._validate_service_names(sentinel_services)
            self._services = list(sentinel_services)  # type: List[six.text_type]
        else:
            self._services = self._get_service_names()

        super(SentinelRedisClient, self).__init__(ring_size=len(self._services))

    def reset_clients(self):  # type: () -> None
        self._master_clients = {}

    @staticmethod
    def _setup_hosts(
        hosts,  # type: Optional[Iterable[Tuple[six.text_type, int]]]
    ):
        # type: (...) -> List[Tuple[six.text_type, int]]
        if not hosts:
            hosts = [('localhost', 26379)]

        if isinstance(hosts, six.string_types):
            raise ValueError('Redis hosts must be specified as an iterable list of hosts.')

        final_hosts = list()
        for entry in hosts:
            if isinstance(entry, six.string_types):
                raise ValueError('Sentinel Redis host entries must be specified as tuples, not strings.')
            elif isinstance(entry, tuple):
                final_hosts.append(entry)
            else:
                raise ValueError(
                    'Sentinel Redis hosts entries must be specified as tuples, not {}.'.format(type(entry)),
                )
        return final_hosts

    @staticmethod
    def _validate_service_names(services):  # type: (Iterable[six.text_type]) -> None
        if isinstance(services, six.string_types):
            raise ValueError('Sentinel service types must be specified as an iterable list of strings.')
        for entry in services:
            if not isinstance(entry, six.string_types):
                raise ValueError('Sentinel service types must be specified as strings.')

    def _get_service_names(self):  # type: () -> List[six.text_type]
        """
        Get a list of service names from Sentinel. Tries Sentinel hosts until one succeeds; if none succeed,
        raises a ConnectionError.

        :return: the list of service names from Sentinel.
        """
        master_info = None
        connection_errors = []
        for sentinel in self._sentinel.sentinels:
            # Unfortunately, redis.sentinel.Sentinel does not support sentinel_masters, so we have to step
            # through all of its connections manually
            try:
                master_info = sentinel.sentinel_masters()
                break
            except (redis.ConnectionError, redis.TimeoutError) as e:
                connection_errors.append('Failed to connect to {} due to error: "{}".'.format(sentinel, e))
                continue
        if master_info is None:
            raise redis.ConnectionError(
                'Could not get master info from Sentinel\n{}:'.format('\n'.join(connection_errors))
            )
        return list(master_info.keys())

    def _get_master_client_for(self, service_name):  # type: (six.text_type) -> redis.StrictRedis
        if service_name not in self._master_clients:
            self._get_counter('backend.sentinel.populate_master_client').increment()
            self._master_clients[service_name] = self._sentinel.master_for(service_name)
            master_address = self._master_clients[service_name].connection_pool.get_master_address()
            _logger.info('Sentinel master address: {}'.format(master_address))

        return self._master_clients[service_name]

    def _get_connection(self, index):  # type: (int) -> redis.StrictRedis
        if not 0 <= index < self._ring_size:
            raise ValueError(
                'There are only {count} hosts, but you asked for connection {index}.'.format(
                    count=self._ring_size,
                    index=index,
                )
            )

        for i in range(self._sentinel_failover_retries + 1):
            try:
                return self._get_master_client_for(self._services[index])
            except redis.sentinel.MasterNotFoundError:
                self.reset_clients()  # make sure we reach out to get master info again on next call
                _logger.warning('Redis master not found, so resetting clients (failover?)')
                if i != self._sentinel_failover_retries:
                    self._get_counter('backend.sentinel.master_not_found_retry').increment()
                    time.sleep((2 ** i + random.random()) / 4.0)

        raise CannotGetConnectionError('Master not found; gave up reloading master info after failover.')
