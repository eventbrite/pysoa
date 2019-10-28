from __future__ import (
    absolute_import,
    unicode_literals,
)

from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Optional,
    Tuple,
    Union,
)

import redis
import six

from pysoa.common.transport.redis_gateway.backend.base import BaseRedisClient


class StandardRedisClient(BaseRedisClient):
    def __init__(
        self,
        hosts=None,  # type: Optional[Iterable[Union[six.text_type, Tuple[six.text_type, int]]]]
        connection_kwargs=None,  # type: Dict[six.text_type, Any]
    ):
        # type: (...) -> None
        connection_kwargs = dict(connection_kwargs) if connection_kwargs else {}
        if 'socket_connect_timeout' not in connection_kwargs:
            connection_kwargs['socket_connect_timeout'] = 5.0  # so that we don't wait indefinitely during failover
        if 'socket_keepalive' not in connection_kwargs:
            connection_kwargs['socket_keepalive'] = True

        self._hosts = self._setup_hosts(hosts)
        self._connection_list = [
            redis.Redis.from_url(host, **connection_kwargs) for host in self._hosts
        ]  # type: List[redis.Redis]

        super(StandardRedisClient, self).__init__(ring_size=len(self._hosts))

    @staticmethod
    def _setup_hosts(
        hosts,  # type: Optional[Iterable[Union[six.text_type, Tuple[six.text_type, int]]]]
    ):
        # type: (...) -> List[six.text_type]
        if not hosts:
            hosts = [('localhost', 6379)]

        if isinstance(hosts, six.string_types):
            raise ValueError('Redis hosts must be specified as an iterable list of hosts.')

        final_hosts = list()
        for entry in hosts:
            if isinstance(entry, six.string_types):
                final_hosts.append(entry)
            else:
                final_hosts.append('redis://{name}:{port:d}/0'.format(name=entry[0], port=entry[1]))
        return final_hosts

    def _get_connection(self, index):  # type: (int) -> redis.StrictRedis
        # Catch bad indexes
        if not 0 <= index < self._ring_size:
            raise ValueError(
                'There are only {count} hosts, but you asked for connection {index}.'.format(
                    count=self._ring_size,
                    index=index,
                )
            )
        return self._connection_list[index]
