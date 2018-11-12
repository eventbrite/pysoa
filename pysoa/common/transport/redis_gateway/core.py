from __future__ import (
    absolute_import,
    unicode_literals,
)

from copy import deepcopy
import logging
import random
import time

import attr
import redis
import six

from pysoa.common.logging import RecursivelyCensoredDictWrapper
from pysoa.common.metrics import (
    MetricsRecorder,
    NoOpMetricsRecorder,
    TimerResolution,
)
from pysoa.common.serializer.base import Serializer
from pysoa.common.serializer.msgpack_serializer import MsgpackSerializer
from pysoa.common.transport.exceptions import (
    InvalidMessageError,
    MessageReceiveError,
    MessageReceiveTimeout,
    MessageSendError,
    MessageTooLarge,
)
from pysoa.common.transport.redis_gateway.backend.base import CannotGetConnectionError
from pysoa.common.transport.redis_gateway.backend.sentinel import SentinelRedisClient
from pysoa.common.transport.redis_gateway.backend.standard import StandardRedisClient
from pysoa.common.transport.redis_gateway.constants import (
    DEFAULT_MAXIMUM_MESSAGE_BYTES_CLIENT,
    REDIS_BACKEND_TYPE_SENTINEL,
    REDIS_BACKEND_TYPES,
)
from pysoa.utils import dict_to_hashable


_oversized_message_logger = logging.getLogger('pysoa.transport.oversized_message')


def valid_backend_type(_, __, value):
    if not value or value not in REDIS_BACKEND_TYPES:
        raise ValueError('backend_type must be one of {}, got {}'.format(REDIS_BACKEND_TYPES, value))


@attr.s()
class RedisTransportCore(object):
    """Handles communication with Redis."""

    # The backend layer holds Redis connections and should be reused as much as possible to reduce Redis connections.
    # Given identical input settings, two given backend layer instances will operate identically, and so we cash using
    # input variables as a key. This applies even across services--backend layers have no service-specific code, so
    # a single backend can be used for multiple services if those services' backend settings are the same.
    _backend_layer_cache = {}

    backend_type = attr.ib(validator=valid_backend_type)

    backend_layer_kwargs = attr.ib(
        # Keyword args for the backend layer (Standard Redis and Sentinel Redis modes)
        default={},
        validator=attr.validators.instance_of(dict),
    )

    log_messages_larger_than_bytes = attr.ib(
        default=DEFAULT_MAXIMUM_MESSAGE_BYTES_CLIENT,
        converter=int,
    )

    maximum_message_size_in_bytes = attr.ib(
        default=DEFAULT_MAXIMUM_MESSAGE_BYTES_CLIENT,
        converter=int,
    )

    message_expiry_in_seconds = attr.ib(
        # How long after a message is sent before it's considered "expired" and not received by default, unless
        # overridden in the send_message argument `message_expiry_in_seconds`
        default=60,
        converter=int,
    )

    metrics = attr.ib(
        default=NoOpMetricsRecorder(),
        validator=attr.validators.instance_of(MetricsRecorder),
    )

    metrics_prefix = attr.ib(
        default='',
        validator=attr.validators.instance_of(six.text_type),
    )

    queue_capacity = attr.ib(
        # The capacity for queues to which messages are sent
        default=10000,
        converter=int,
    )

    queue_full_retries = attr.ib(
        # Number of times to retry when the send queue is full
        default=10,
        converter=int,
    )

    receive_timeout_in_seconds = attr.ib(
        # How long to block when waiting to receive a message by default, unless overridden in the receive_message
        # argument `receive_timeout_in_seconds`
        default=5,
        converter=int,
    )

    default_serializer_config = attr.ib(
        # Configuration for which serializer should be used by this transport
        default={'object': MsgpackSerializer, 'kwargs': {}},
        converter=dict,
    )

    service_name = attr.ib(
        # Service name used for error messages
        default='',
        validator=attr.validators.instance_of(six.text_type),
    )

    EXPONENTIAL_BACK_OFF_FACTOR = 4.0
    QUEUE_NAME_PREFIX = 'pysoa:'
    GLOBAL_QUEUE_SPECIFIER = '!'

    def __attrs_post_init__(self):
        # set the hosts property after all attrs are validated
        if self.backend_layer_kwargs.get('hosts'):
            final_hosts = []
            for host in self.backend_layer_kwargs['hosts']:
                if isinstance(host, tuple) and len(host) == 2:
                    final_hosts.append(host)
                elif isinstance(host, six.string_types):
                    final_hosts.append((host, self.backend_layer_kwargs.get('redis_port', 6379)))
                else:
                    raise Exception("connection_kwargs['hosts'] must be a list of tuples of (host, port), or strings")
            self.backend_layer_kwargs['hosts'] = final_hosts

        if self.backend_layer_kwargs.get('redis_db') is not None:
            self.backend_layer_kwargs.setdefault('connection_kwargs', {})['db'] = self.backend_layer_kwargs['redis_db']

        self.backend_layer_kwargs.pop('redis_db', None)
        self.backend_layer_kwargs.pop('redis_port', None)

        self._backend_layer = None
        self._default_serializer = None

    # noinspection PyAttributeOutsideInit
    @property
    def backend_layer(self):
        if self._backend_layer is None:
            cache_key = (self.backend_type, dict_to_hashable(self.backend_layer_kwargs))
            if cache_key not in self._backend_layer_cache:
                with self._get_timer('backend.initialize'):
                    backend_layer_kwargs = deepcopy(self.backend_layer_kwargs)
                    if self.backend_type == REDIS_BACKEND_TYPE_SENTINEL:
                        self._backend_layer_cache[cache_key] = SentinelRedisClient(**backend_layer_kwargs)
                    else:
                        self._backend_layer_cache[cache_key] = StandardRedisClient(**backend_layer_kwargs)

            self._backend_layer = self._backend_layer_cache[cache_key]

        # Each time the backend layer is accessed, use _this_ transport's metrics recorder for the backend layer
        self._backend_layer.metrics_counter_getter = lambda name: self._get_counter(name)
        return self._backend_layer

    # noinspection PyAttributeOutsideInit
    @property
    def default_serializer(self):
        if self._default_serializer is None:
            self._default_serializer = self.default_serializer_config['object'](
                **self.default_serializer_config.get('kwargs', {})
            )

        return self._default_serializer

    def send_message(self, queue_name, request_id, meta, body, message_expiry_in_seconds=None):
        """
        Send a message to the specified queue in Redis.

        :param queue_name: The name of the queue to which to send the message
        :type queue_name: union(str, unicode)
        :param request_id: The message's request ID
        :type request_id: int
        :param meta: The message meta information, if any (should be an empty dict if no metadata)
        :type meta: dict
        :param body: The message body (should be a dict)
        :type body: dict
        :param message_expiry_in_seconds: The optional message expiry, which defaults to the setting with the same name
        :type message_expiry_in_seconds: int

        :raise: InvalidMessageError, MessageTooLarge, MessageSendError
        """
        if request_id is None:
            raise InvalidMessageError('No request ID')

        if message_expiry_in_seconds:
            message_expiry = time.time() + message_expiry_in_seconds
            redis_expiry = message_expiry_in_seconds + 10
        else:
            message_expiry = time.time() + self.message_expiry_in_seconds
            redis_expiry = self.message_expiry_in_seconds

        meta['__expiry__'] = message_expiry

        message = {'request_id': request_id, 'meta': meta, 'body': body}

        with self._get_timer('send.serialize'):
            serializer = self.default_serializer
            non_default_serializer = False
            if 'serializer' in meta:
                # TODO: Breaking change: Assume a MIME type is always specified. This should not be done until all
                # TODO servers and clients have Step 2 code. This will be a Step 3 breaking change.
                serializer = meta.pop('serializer')
                non_default_serializer = True
            serialized_message = serializer.dict_to_blob(message)
            if non_default_serializer:
                # TODO: Breaking change: Make this happen always, not just when a specific MIME type was requested.
                # TODO This should not be done until all servers and clients have this Step 1 code. This will be a Step
                # TODO 2 breaking change.
                serialized_message = (
                    'content-type:{};'.format(serializer.mime_type).encode('utf-8') + serialized_message
                )

        message_size_in_bytes = len(serialized_message)
        if message_size_in_bytes > self.maximum_message_size_in_bytes:
            self._get_counter('send.error.message_too_large').increment()
            raise MessageTooLarge(message_size_in_bytes)
        elif self.log_messages_larger_than_bytes and message_size_in_bytes > self.log_messages_larger_than_bytes:
            _oversized_message_logger.warning(
                'Oversized message sent for PySOA service {}'.format(self.service_name),
                extra={'data': {
                    'message': RecursivelyCensoredDictWrapper(message),
                    'serialized_length_in_bytes': message_size_in_bytes,
                    'threshold': self.log_messages_larger_than_bytes,
                }},
            )

        queue_key = self.QUEUE_NAME_PREFIX + queue_name

        # Try at least once, up to queue_full_retries times, then error
        for i in range(-1, self.queue_full_retries):
            if i >= 0:
                time.sleep((2 ** i + random.random()) / self.EXPONENTIAL_BACK_OFF_FACTOR)
                self._get_counter('send.queue_full_retry').increment()
                self._get_counter('send.queue_full_retry.retry_{}'.format(i + 1)).increment()
            try:
                with self._get_timer('send.get_redis_connection'):
                    connection = self.backend_layer.get_connection(queue_key)

                with self._get_timer('send.send_message_to_redis_queue'):
                    self.backend_layer.send_message_to_queue(
                        queue_key=queue_key,
                        message=serialized_message,
                        expiry=redis_expiry,
                        capacity=self.queue_capacity,
                        connection=connection,
                    )
                return
            except redis.exceptions.ResponseError as e:
                # The Lua script handles capacity checking and sends the "full" error back
                if e.args[0] == 'queue full':
                    continue
                self._get_counter('send.error.response').increment()
                raise MessageSendError('Redis error sending message for service {}'.format(self.service_name), *e.args)
            except CannotGetConnectionError as e:
                self._get_counter('send.error.connection').increment()
                raise MessageSendError('Cannot get connection: {}'.format(e.args[0]))
            except Exception as e:
                self._get_counter('send.error.unknown').increment()
                raise MessageSendError(
                    'Unknown error sending message for service {}'.format(self.service_name),
                    six.text_type(type(e).__name__),
                    *e.args
                )

        self._get_counter('send.error.redis_queue_full').increment()
        raise MessageSendError(
            'Redis queue {queue_name} was full after {retries} retries'.format(
                queue_name=queue_name,
                retries=self.queue_full_retries,
            )
        )

    def receive_message(self, queue_name, receive_timeout_in_seconds=None):
        """
        Receive a message from the specified queue in Redis.

        :param queue_name: The name of the queue to which to send the message
        :type queue_name: union(str, unicode)
        :param receive_timeout_in_seconds: The optional timeout, which defaults to the setting with the same name
        :type receive_timeout_in_seconds: int

        :return: A tuple of request ID, message meta-information dict, and message body dict
        :rtype: tuple(int, dict, dict)

        :raise: MessageReceiveError, MessageReceiveTimeout, InvalidMessageError
        """
        queue_key = self.QUEUE_NAME_PREFIX + queue_name

        try:
            with self._get_timer('receive.get_redis_connection'):
                connection = self.backend_layer.get_connection(queue_key)
            # returns message or None if no new messages within timeout
            with self._get_timer('receive.pop_from_redis_queue'):
                result = connection.blpop(
                    [queue_key],
                    timeout=receive_timeout_in_seconds or self.receive_timeout_in_seconds,
                )
            serialized_message = None
            if result:
                serialized_message = result[1]
        except CannotGetConnectionError as e:
            self._get_counter('receive.error.connection').increment()
            raise MessageReceiveError('Cannot get connection: {}'.format(e.args[0]))
        except Exception as e:
            self._get_counter('receive.error.unknown').increment()
            raise MessageReceiveError(
                'Unknown error receiving message for service {}'.format(self.service_name),
                six.text_type(type(e).__name__),
                *e.args
            )

        if serialized_message is None:
            raise MessageReceiveTimeout('No message received for service {}'.format(self.service_name))

        with self._get_timer('receive.deserialize'):
            serializer = self.default_serializer
            non_default_serializer = False
            if serialized_message.startswith(b'content-type'):
                # TODO: Breaking change: Assume all messages start with a content type. This should not be done until
                # TODO all servers and clients have Step 2 code. This will be a Step 3 breaking change.
                header, serialized_message = serialized_message.split(b';', 1)
                mime_type = header.split(b':', 1)[1].decode('utf-8').strip()
                if mime_type in Serializer.all_supported_mime_types:
                    serializer = Serializer.resolve_serializer(mime_type)
                    non_default_serializer = True

            message = serializer.blob_to_dict(serialized_message)

            if non_default_serializer:
                # TODO: Breaking change: Always add the serializer to the meta. This should not be done until all
                # TODO servers and clients have this Step 1 code. This will be a Step 2 breaking change.
                message.setdefault('meta', {})['serializer'] = serializer

        if self._is_message_expired(message):
            self._get_counter('receive.error.message_expired').increment()
            raise MessageReceiveTimeout('Message expired for service {}'.format(self.service_name))

        request_id = message.get('request_id')
        if request_id is None:
            self._get_counter('receive.error.no_request_id').increment()
            raise InvalidMessageError('No request ID for service {}'.format(self.service_name))

        return request_id, message.get('meta', {}), message.get('body')

    @staticmethod
    def _is_message_expired(message):
        return message.get('meta', {}).get('__expiry__') and message['meta']['__expiry__'] < time.time()

    def _get_metric_name(self, name):
        if self.metrics_prefix:
            return '{prefix}.transport.redis_gateway.{name}'.format(prefix=self.metrics_prefix, name=name)
        else:
            return 'transport.redis_gateway.{}'.format(name)

    def _get_counter(self, name):
        return self.metrics.counter(self._get_metric_name(name))

    def _get_timer(self, name):
        return self.metrics.timer(self._get_metric_name(name), resolution=TimerResolution.MICROSECONDS)
