from __future__ import (
    absolute_import,
    unicode_literals,
)

import abc
import binascii
import itertools
import random
from typing import (  # noqa: F401 TODO Python 3
    Any,
    Callable,
    List,
    Optional,
)

import redis  # noqa: F401 TODO Python 3
import redis.client  # noqa: F401 TODO Python 3
import six

from pysoa.common.metrics import (  # noqa: F401 TODO Python 3
    Counter,
    NoOpMetricsRecorder,
)


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
        self._redis_script = redis_connection.register_script(self._script.strip())  # type: redis.client.Script

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

        self._ring_size = ring_size
        self._connection_index_generator = itertools.cycle(range(self._ring_size))  # may be overridden by subclasses

        connection = self._get_connection()
        self.send_message_to_queue = SendMessageToQueueCommand(connection)

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
    def _get_connection(self, index=None):  # type: (Optional[int]) -> redis.StrictRedis
        """
        Returns the correct connection for the current thread. Pass `index` to use a server based on consistent hashing
        of the key value; `pass` None to use a random server instead.

        :param index: The optional index of a server to use
        :return: the connection to use.
        """
        raise NotImplementedError()

    def _get_random_index(self):  # type: () -> int
        """
        Get a random index from the ring of servers.

        :return: the random index.
        """
        return random.randint(0, self._ring_size - 1)

    def _get_consistent_hash_index(self, value):  # type: (six.text_type) -> int
        """
        Maps the value to a node value between 0 and 4095 using CRC, then down to one of the ring nodes.

        :param value: The value for which to calculate a hash
        :return: The Redis server ring index from the calculated hash
        """
        if isinstance(value, six.text_type):
            value = value.encode('utf8')
        big_value = binascii.crc32(value) & 0xfff
        ring_divisor = 4096 / float(self._ring_size)
        return int(big_value / ring_divisor)

    def _get_counter(self, name):  # type: (six.text_type) -> Counter
        return self.metrics_counter_getter(name) if self.metrics_counter_getter else NoOpMetricsRecorder.no_op_counter
