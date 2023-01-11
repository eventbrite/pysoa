from __future__ import (
    absolute_import,
    division,
    unicode_literals,
)

import abc
import binascii
import itertools
import random
from typing import (
    Any,
    Callable,
    List,
    Optional,
)

from pymetrics.instruments import Counter
import redis
import redis.client
import six


_no_op_counter = Counter('')


class CannotGetConnectionError(Exception):
    pass


class LuaRedisCommand(object):
    _script = ''

    def __init__(self, redis_connection):  # type: (redis.StrictRedis) -> None
        """
        Registers this Lua script with the connections. The supplied redis connection is only used to create a
        registered script option; no connection is established or communicated over.

        :param redis_connection: The connection for registering this script
        """
        self._redis_script = redis_connection.register_script(self._script.strip())  # type: ignore

    def _call(self, keys, args, connection):  # type: (List[six.text_type], List[Any], redis.StrictRedis) -> Any
        return self._redis_script(keys=keys, args=args, client=connection)


class SendMessageToQueueCommand(LuaRedisCommand):
    # KEYS[1] = queue key
    # ARGV[1] = expiry
    # ARGV[2] = queue capacity
    # ARGV[3] = message
    _script = """
if redis.call('llen', KEYS[1]) >= tonumber(ARGV[2]) then
    return redis.error_reply("queue full")
end
redis.call('rpush', KEYS[1], ARGV[3])
redis.call('expire', KEYS[1], ARGV[1])
"""

    def __call__(
        self,
        queue_key,  # type: six.text_type
        message,  # type: six.binary_type
        expiry,  # type: int
        capacity,  # type: int
        connection,  # type: redis.StrictRedis
    ):
        # type: (...) -> None
        self._call(keys=[queue_key], args=[expiry, capacity, message], connection=connection)


@six.add_metaclass(abc.ABCMeta)
class BaseRedisClient(object):
    DEFAULT_RECEIVE_TIMEOUT = 5
    RESPONSE_QUEUE_SPECIFIER = '!'

    def __init__(self, ring_size):  # type: (int) -> None
        self.metrics_counter_getter = None  # type: Optional[Callable[[six.text_type], Counter]]

        # These should not be overridden by subclasses. The standard or Sentinel base class determines the ring size
        # and passes it in, and then we create a randomized cycle-iterator (which can be infinitely next-ed) of
        # connection indexes to use for choosing a connection when posting to request queues (response queues use a
        # consistent hashing algorithm).
        self._ring_size = ring_size
        self._connection_index_generator = itertools.cycle(random.sample(range(self._ring_size), k=self._ring_size))

        # It doesn't matter which connection we use for this. The underlying socket connection isn't even used (or
        # established, for that matter). But constructing a Script with the `redis` library requires passing it a
        # "default" connection that will be used if we ever call that script without a connection (we won't).
        self.send_message_to_queue = SendMessageToQueueCommand(self._get_connection(0))

    def get_connection(self, queue_key):  # type: (six.text_type) -> redis.StrictRedis
        """
        Get the correct Redis connection for the given queue key.

        :param queue_key: The queue key for which to get the appropriate connection
        :return: the Redis connection.
        """
        if self.RESPONSE_QUEUE_SPECIFIER in queue_key:
            # It's a response queue, so use a consistent connection
            return self._get_connection(self._get_consistent_hash_index(queue_key))
        else:
            # It's a request queue, so use a random connection
            return self._get_connection(next(self._connection_index_generator))

    @abc.abstractmethod
    def _get_connection(self, index):  # type: (int) -> redis.StrictRedis
        """
        Returns the correct connection for the current thread. The `index` determines which server to use in a
        multi-server (standalone Redis) or multi-master (Redis Cluster or Redis Sentinel) environment. It is provided
        by the caller based on either a consistent hash or using the next index from the `_connection_index_generator`.

        :param index: The index of the server to use
        :return: the connection to use.
        """

    def _get_consistent_hash_index(self, value):  # type: (six.text_type) -> int
        """
        Maps the value to a node value between 0 and 4095 using CRC, then down to one of the ring nodes.

        :param value: The value for which to calculate a hash
        :return: The Redis server ring index from the calculated hash
        """
        big_value = binascii.crc32(value.encode('utf8') if isinstance(value, six.text_type) else value) & 0xfff
        ring_divisor = 4096.0 / self._ring_size
        return int(big_value / ring_divisor)

    def _get_counter(self, name):  # type: (six.text_type) -> Counter
        return self.metrics_counter_getter(name) if self.metrics_counter_getter else _no_op_counter
