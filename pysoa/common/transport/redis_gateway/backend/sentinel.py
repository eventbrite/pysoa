from __future__ import (
    absolute_import,
    unicode_literals,
)

import itertools
import random
import time

import redis
import redis.sentinel
import six

from pysoa.common.metrics import NoOpMetricsRecorder
from pysoa.common.transport.redis_gateway.backend.base import (
    BaseRedisClient,
    CannotGetConnectionError,
)


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
        hosts=None,
        connection_kwargs=None,
        sentinel_services=None,
        sentinel_failover_retries=0,
    ):
        # Master client caching
        self._master_clients = {}

        # Master failover behavior
        assert sentinel_failover_retries >= 0
        self._sentinel_failover_retries = sentinel_failover_retries

        self._sentinel = redis.sentinel.Sentinel(self._setup_hosts(hosts), **(connection_kwargs or {}))
        if sentinel_services:
            self._validate_service_names(sentinel_services)
            self._services = sentinel_services
        else:
            self._services = self._get_service_names()
        self._ring_size = len(self._services)
        self._connection_index_generator = itertools.cycle(range(self._ring_size))

        self.metrics_counter_getter = None

        super(SentinelRedisClient, self).__init__(ring_size=len(self._services))

    def reset_clients(self):
        self._master_clients = {}

    @staticmethod
    def _setup_hosts(hosts):
        if not hosts:
            hosts = [('localhost', 26379)]

        if isinstance(hosts, six.string_types):
            raise ValueError('Redis hosts must be specified as an iterable list of hosts.')

        final_hosts = list()
        for entry in hosts:
            if isinstance(entry, six.string_types):
                raise ValueError('Sentinel Redis host entries must be specified as tuples, not strings.')
            else:
                final_hosts.append(entry)
        return final_hosts

    @staticmethod
    def _validate_service_names(services):
        if isinstance(services, six.string_types):
            raise ValueError('Sentinel service types must be specified as an iterable list of strings.')
        for entry in services:
            if not isinstance(entry, six.string_types):
                raise ValueError('Sentinel service types must be specified as strings.')

    def _get_service_names(self):
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

    def _get_master_client_for(self, service_name):
        if service_name not in self._master_clients:
            self._get_counter('backend.sentinel.populate_master_client').increment()
            self._master_clients[service_name] = self._sentinel.master_for(service_name)

        return self._master_clients[service_name]

    def _get_connection(self, index=None):
        if index is None:
            index = self._get_random_index()

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
                if i == self._sentinel_failover_retries:
                    raise CannotGetConnectionError('Master not found; gave up reloading master info after failover.')
                self._get_counter('backend.sentinel.master_not_found_retry').increment()
                time.sleep((2 ** i + random.random()) / 4.0)

    def _get_random_index(self):
        return random.randint(0, len(self._services) - 1)

    def _get_counter(self, name):
        return self.metrics_counter_getter(name) if self.metrics_counter_getter else NoOpMetricsRecorder.no_op_counter
