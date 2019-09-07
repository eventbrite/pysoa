from __future__ import (
    absolute_import,
    unicode_literals,
)

from typing import (  # noqa: F401 TODO Python 3
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
        hosts=None,  # type: Iterable[Union[six.text_type, Tuple[six.text_type, int]]]
        connection_kwargs=None,  # type: Dict[six.text_type, Any]
    ):
        # type: (...) -> None
        self._hosts = self._setup_hosts(hosts)
        self._connection_list = [
            redis.Redis.from_url(host, **(connection_kwargs or {})) for host in self._hosts
        ]  # type: List[redis.Redis]

        super(StandardRedisClient, self).__init__(ring_size=len(self._hosts))

    @staticmethod
    def _setup_hosts(
        hosts,  # type: Iterable[Union[six.text_type, Tuple[six.text_type, int]]]
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

    def _get_connection(self, index=None):  # type: (Optional[int]) -> redis.StrictRedis
        # If index is explicitly None, pick a random server
        if index is None:
            index = self._get_random_index()
        # Catch bad indexes
        if not 0 <= index < self._ring_size:
            raise ValueError(
                'There are only {count} hosts, but you asked for connection {index}.'.format(
                    count=self._ring_size,
                    index=index,
                )
            )
        return self._connection_list[index]
