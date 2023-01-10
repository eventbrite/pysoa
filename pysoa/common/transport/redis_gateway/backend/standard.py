from __future__ import (
    absolute_import,
    unicode_literals,
)

import re
from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Optional,
    Tuple,
    Union,
)
import warnings

import redis
import six

from pysoa.common.transport.redis_gateway.backend.base import BaseRedisClient


class StandardRedisClient(BaseRedisClient):
    DEFAULT_PORT = 6379
    URL_SYNTAX = re.compile(r'^(unix|rediss?)://')

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

        self._connection_list = self._get_connection_list(hosts, **connection_kwargs)

        super(StandardRedisClient, self).__init__(ring_size=len(self._connection_list))

    @classmethod
    def _get_connection_list(
        cls,
        hosts,  # type: Optional[Iterable[Union[six.text_type, Tuple[six.text_type, int]]]]
        **connection_kwargs  # type: Any
    ):
        # type: (...) -> List[redis.Redis]
        if not hosts:
            return [redis.Redis(host='localhost', port=cls.DEFAULT_PORT, **connection_kwargs)]

        if isinstance(hosts, six.string_types):
            raise ValueError('Redis hosts must be specified as an iterable of hosts.')

        connections = []  # type: List[redis.Redis]
        for entry in hosts:
            if isinstance(entry, six.string_types):
                if cls.URL_SYNTAX.match(entry):
                    warnings.warn(
                        'Support for redis://, rediss://, and unix:// Redis host syntax is deprecated and will be '
                        'removed in PySOA 2.0. Please use a string hostname or two-tuple (string, int) host and port.',
                        DeprecationWarning,
                    )
                    connections.append(redis.Redis.from_url(entry, **connection_kwargs))
                else:
                    connections.append(redis.Redis(host=entry, port=cls.DEFAULT_PORT, **connection_kwargs))
            elif (
                isinstance(entry, tuple) and len(entry) == 2 and isinstance(entry[0], six.string_types) and
                isinstance(entry[1], int)
            ):
                connections.append(redis.Redis(host=entry[0], port=entry[1], **connection_kwargs))
            else:
                raise ValueError(
                    'Each Redis `hosts` entries must be specified as either a string host name (which will default to '
                    'port {}), string Redis URI, or a two-tuple of (string, int) host and port. `{}` did not fit this '
                    'requirement.'.format(cls.DEFAULT_PORT, repr(entry)),
                )
        return connections

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
