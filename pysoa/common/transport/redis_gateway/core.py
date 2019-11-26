from __future__ import (
    absolute_import,
    division,
    unicode_literals,
)

import abc
from copy import deepcopy
import logging
import math
import random
import re
import time
from typing import (
    Any,
    Dict,
    FrozenSet,
    Hashable,
    List,
    Optional,
    Tuple,
    Union,
    cast,
)

import attr
from pymetrics.instruments import (
    Counter,
    Histogram,
    Timer,
    TimerResolution,
)
from pymetrics.recorders.base import MetricsRecorder
from pymetrics.recorders.noop import noop_metrics
import redis
import six

from pysoa.common.logging import RecursivelyCensoredDictWrapper
from pysoa.common.serializer.base import Serializer
from pysoa.common.serializer.msgpack_serializer import MsgpackSerializer
from pysoa.common.transport.base import ReceivedMessage
from pysoa.common.transport.errors import (
    InvalidMessageError,
    MessageReceiveError,
    MessageReceiveTimeout,
    MessageSendError,
    MessageTooLarge,
)
from pysoa.common.transport.redis_gateway.backend.base import (
    BaseRedisClient,
    CannotGetConnectionError,
)
from pysoa.common.transport.redis_gateway.backend.sentinel import SentinelRedisClient
from pysoa.common.transport.redis_gateway.backend.standard import StandardRedisClient
from pysoa.common.transport.redis_gateway.constants import (
    DEFAULT_MAXIMUM_MESSAGE_BYTES_CLIENT,
    DEFAULT_MAXIMUM_MESSAGE_BYTES_SERVER,
    MINIMUM_CHUNKED_MESSAGE_BYTES,
    REDIS_BACKEND_TYPE_SENTINEL,
    REDIS_BACKEND_TYPES,
    ProtocolFeature,
    ProtocolVersion,
)
from pysoa.utils import dict_to_hashable


__all__ = (
    'RedisTransportCore',
    'RedisTransportClientCore',
    'RedisTransportServerCore',
)


_oversized_message_logger = logging.getLogger('pysoa.transport.oversized_message')


def _valid_backend_type(_, __, value):
    if not value or value not in REDIS_BACKEND_TYPES:
        raise ValueError('backend_type must be one of {}, got {}'.format(REDIS_BACKEND_TYPES, value))


def _valid_chunk_threshold(_, __, value):
    if 0 <= value < MINIMUM_CHUNKED_MESSAGE_BYTES:
        # Negative values are fine; that just means "disabled."
        raise ValueError(
            'If chunk_messages_larger_than_bytes is enabled (non-negative), it must be >= {}, '
            'got {}'.format(MINIMUM_CHUNKED_MESSAGE_BYTES, value),
        )


_DEFAULT_METRICS_RECORDER = noop_metrics  # type: MetricsRecorder


@attr.s
@six.add_metaclass(abc.ABCMeta)
class RedisTransportCore(object):
    """Handles communication with Redis."""

    # The backend layer holds Redis connections and should be reused as much as possible to reduce Redis connections.
    # Given identical input settings, two given backend layer instances will operate identically, and so we cash using
    # input variables as a key. This applies even across services--backend layers have no service-specific code, so
    # a single backend can be used for multiple services if those services' backend settings are the same.
    _backend_layer_cache = {}  # type: Dict[Tuple[six.text_type, FrozenSet[Tuple[Hashable, ...]]], BaseRedisClient]

    SUPPORTED_HEADERS_RE = re.compile(
        b'(?P<header_name>content-type|chunk-count|chunk-id)\\s*:\\s*(?P<header_value>[a-zA-Z0-9_/.-]+)\\s*;',
    )

    backend_type = attr.ib(validator=_valid_backend_type)  # type: six.text_type

    backend_layer_kwargs = attr.ib(
        # Keyword args for the backend layer (Standard Redis and Sentinel Redis modes)
        default=attr.Factory(dict),
        validator=attr.validators.instance_of(dict),
    )  # type: Dict[six.text_type, Any]

    log_messages_larger_than_bytes = attr.ib(
        default=DEFAULT_MAXIMUM_MESSAGE_BYTES_CLIENT,
        converter=int,
    )  # type: int

    maximum_message_size_in_bytes = attr.ib(
        default=DEFAULT_MAXIMUM_MESSAGE_BYTES_CLIENT,
        converter=int,
    )  # type: int

    chunk_messages_larger_than_bytes = -1

    message_expiry_in_seconds = attr.ib(
        # How long after a message is sent before it's considered "expired" and not received by default, unless
        # overridden in the send_message argument `message_expiry_in_seconds`
        default=60,
        converter=int,
    )  # type: int

    metrics = attr.ib(
        default=_DEFAULT_METRICS_RECORDER,
        validator=attr.validators.instance_of(MetricsRecorder),  # type: ignore
    )  # type: MetricsRecorder

    queue_capacity = attr.ib(
        # The capacity for queues to which messages are sent
        default=10000,
        converter=int,
    )  # type: int

    queue_full_retries = attr.ib(
        # Number of times to retry when the send queue is full
        default=10,
        converter=int,
    )  # type: int

    receive_timeout_in_seconds = attr.ib(
        # How long to block when waiting to receive a message by default, unless overridden in the receive_message
        # argument `receive_timeout_in_seconds`
        default=5,
        converter=int,
    )  # type: int

    default_serializer_config = attr.ib(
        # Configuration for which serializer should be used by this transport
        default={'object': MsgpackSerializer, 'kwargs': {}},
    )  # type: Dict[six.text_type, Any]

    service_name = attr.ib(
        # Service name used for error messages
        default='',
        validator=attr.validators.instance_of(six.text_type),
    )  # type: six.text_type

    protocol_version = ProtocolVersion.VERSION_3

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
                    raise ValueError("connection_kwargs['hosts'] must be a list of tuples of (host, port), or strings")
            self.backend_layer_kwargs['hosts'] = final_hosts

        if self.backend_layer_kwargs.get('redis_db') is not None:
            self.backend_layer_kwargs.setdefault('connection_kwargs', {})['db'] = self.backend_layer_kwargs['redis_db']

        self.backend_layer_kwargs.pop('redis_db', None)
        self.backend_layer_kwargs.pop('redis_port', None)

        self._backend_layer = None  # type: Optional[BaseRedisClient]
        self._default_serializer = None  # type: Optional[Serializer]

    @property
    @abc.abstractmethod
    def is_server(self):  # type: () -> bool
        """
        Indicates whether this is a server or a client.
        """

    # noinspection PyAttributeOutsideInit
    @property
    def backend_layer(self):  # type: () -> BaseRedisClient
        if self._backend_layer is None:
            cache_key = (self.backend_type, dict_to_hashable(cast(Dict[Hashable, Any], self.backend_layer_kwargs)))
            if cache_key not in self._backend_layer_cache:
                with self._get_timer('backend.initialize'):
                    backend_layer_kwargs = deepcopy(self.backend_layer_kwargs)
                    if self.backend_type == REDIS_BACKEND_TYPE_SENTINEL:
                        self._backend_layer_cache[cache_key] = SentinelRedisClient(**backend_layer_kwargs)
                    else:
                        self._backend_layer_cache[cache_key] = StandardRedisClient(**backend_layer_kwargs)

            self._backend_layer = self._backend_layer_cache[cache_key]

        # Each time the backend layer is accessed, use _this_ transport's metrics recorder for the backend layer
        self._backend_layer.metrics_counter_getter = self._get_counter
        return self._backend_layer

    # noinspection PyAttributeOutsideInit
    @property
    def default_serializer(self):  # type: () -> Serializer
        if self._default_serializer is None:
            self._default_serializer = cast(
                Serializer,
                self.default_serializer_config['object'](**self.default_serializer_config.get('kwargs', {})),
            )

        return self._default_serializer

    def _get_redis_connection(self, for_send, queue_key):
        # type: (bool, six.text_type) -> redis.StrictRedis
        try:
            with self._get_timer('{}.get_redis_connection'.format('send' if for_send else 'receive')):
                return self.backend_layer.get_connection(queue_key)
        except CannotGetConnectionError as e:
            self._get_counter('{}.error.connection'.format('send' if for_send else 'receive')).increment()
            raise (MessageSendError if for_send else MessageReceiveError)('Cannot get connection: {}'.format(e.args[0]))

    def _serialize_check_and_chunk_message(
        self,
        protocol_version,  # type: ProtocolVersion
        message,  # type: Dict[six.text_type, Any]
        serializer,  # type: Serializer
    ):
        # type: (...) -> List[six.binary_type]
        with self._get_timer('send.serialize'):
            serialized_message = serializer.dict_to_blob(message)

            message_size_in_bytes = len(serialized_message)
            self._get_histogram('send.message_size').set(message_size_in_bytes)

            if message_size_in_bytes > self.maximum_message_size_in_bytes:
                self._get_counter('send.error.message_too_large').increment()
                raise MessageTooLarge(message_size_in_bytes, 'Message exceeds maximum message size')

            if self.log_messages_larger_than_bytes and message_size_in_bytes > self.log_messages_larger_than_bytes:
                _oversized_message_logger.warning(
                    'Oversized message sent for PySOA service {}'.format(self.service_name),
                    extra={'data': {
                        'message': RecursivelyCensoredDictWrapper(message),
                        'serialized_length_in_bytes': message_size_in_bytes,
                        'threshold': self.log_messages_larger_than_bytes,
                    }},
                )

            content_type_header = 'content-type:{};'.format(serializer.mime_type).encode('utf-8')

            if self.is_server and 0 < self.chunk_messages_larger_than_bytes < message_size_in_bytes:
                # chunking is enabled on the server and the message is big enough to chunk
                if not ProtocolFeature.CHUNKED_RESPONSES.supported_in(protocol_version):
                    self._get_counter('send.error.message_too_large').increment()
                    raise MessageTooLarge(
                        message_size_in_bytes,
                        'Message exceeds chunking threshold but client does not support chunking',
                    )

                chunk_count = int(math.ceil(message_size_in_bytes / self.chunk_messages_larger_than_bytes))
                self._get_histogram('send.chunk_count').set(chunk_count)
                headers = protocol_version.prefix + content_type_header + (b'chunk-count:%d;' % (chunk_count, ))
                return [
                    headers + (b'chunk-id:%d;' % (i + 1, )) + serialized_message[
                         i * self.chunk_messages_larger_than_bytes:
                         (i + 1) * self.chunk_messages_larger_than_bytes
                    ]
                    for i in range(chunk_count)
                ]

            if ProtocolFeature.CONTENT_TYPE_HEADER.supported_in(protocol_version):
                serialized_message = content_type_header + serialized_message
            if ProtocolFeature.VERSION_MARKER.supported_in(protocol_version):
                serialized_message = protocol_version.prefix + serialized_message
            return [serialized_message]

    def send_message(
        self,
        queue_name,  # type: six.text_type
        request_id,  # type: int
        meta,  # type: Dict[six.text_type, Any]
        body,  # type: Dict[six.text_type, Any]
        message_expiry_in_seconds=None,  # type: Optional[int]
    ):
        # type: (...) -> None
        """
        Send a message to the specified queue in Redis.

        :param queue_name: The name of the queue to which to send the message
        :param request_id: The message's request ID
        :param meta: The message meta information, if any (should be an empty dict if no metadata)
        :param body: The message body (should be a dict)
        :param message_expiry_in_seconds: The optional message expiry, which defaults to the setting with the same name

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
        protocol_version = meta.pop('protocol_version', self.protocol_version)  # type: ProtocolVersion

        message = {'request_id': request_id, 'meta': meta, 'body': body}

        messages_to_send = self._serialize_check_and_chunk_message(
            protocol_version,
            message,
            cast(Serializer, meta.pop('serializer', self.default_serializer)),
        )

        queue_key = self.QUEUE_NAME_PREFIX + queue_name

        connection = self._get_redis_connection(for_send=True, queue_key=queue_key)

        for message_to_send in messages_to_send:
            # Try at least once, up to queue_full_retries times, then error
            for i in range(-1, self.queue_full_retries):
                if i >= 0:
                    time.sleep((2 ** i + random.random()) / self.EXPONENTIAL_BACK_OFF_FACTOR)
                    self._get_counter('send.queue_full_retry').increment()
                    self._get_counter('send.queue_full_retry.retry_{}'.format(i + 1)).increment()
                try:
                    with self._get_timer('send.send_message_to_redis_queue'):
                        self.backend_layer.send_message_to_queue(
                            queue_key=queue_key,
                            message=message_to_send,
                            expiry=redis_expiry,
                            capacity=self.queue_capacity,
                            connection=connection,
                        )
                    break
                except redis.exceptions.ResponseError as e:
                    # The Lua script handles capacity checking and sends the "full" error back
                    if e.args[0] == 'queue full':
                        continue
                    if isinstance(self.backend_layer, SentinelRedisClient):
                        self.backend_layer.reset_clients()
                    self._get_counter('send.error.response').increment()
                    raise MessageSendError(
                        'Redis error sending message for service {}'.format(self.service_name), *e.args
                    )
                except Exception as e:
                    if isinstance(self.backend_layer, SentinelRedisClient):
                        self.backend_layer.reset_clients()
                    self._get_counter('send.error.unknown').increment()
                    raise MessageSendError(
                        'Unknown error sending message for service {}'.format(self.service_name),
                        six.text_type(type(e).__name__),
                        *e.args
                    )
            else:
                # The loop (number of retries) was exhausted; it was not terminated with break / successful send.
                self._get_counter('send.error.redis_queue_full').increment()
                raise MessageSendError(
                    'Redis queue {queue_name} was full after {retries} retries'.format(
                        queue_name=queue_name,
                        retries=self.queue_full_retries,
                    )
                )

    @classmethod
    def _extract_supported_headers(cls, serialized_message):
        # type: (six.binary_type) -> Tuple[Dict[six.text_type, six.text_type], six.binary_type]
        headers = {}  # type: Dict[six.text_type, six.text_type]
        match = cls.SUPPORTED_HEADERS_RE.match(serialized_message)
        while match:
            headers[match.group('header_name').decode('utf-8')] = match.group('header_value').decode('utf-8')

            # Using lstrip() instead of strip() is important here. It's possible for the last bytes in a msgpack packet
            # to be interpreted as whitespace, and removing it causes msgpack to fail.
            serialized_message = serialized_message[match.end():].lstrip()
            match = cls.SUPPORTED_HEADERS_RE.match(serialized_message)

        return headers, serialized_message

    def _receive_message(self, connection, queue_key, receive_timeout_in_seconds):
        # type: (redis.StrictRedis, six.text_type, int) -> six.binary_type
        try:
            # returns message or None if no new messages within timeout
            with self._get_timer('receive.pop_from_redis_queue'):
                result = connection.blpop([queue_key], timeout=receive_timeout_in_seconds)
            serialized_message = None  # type: Optional[six.binary_type]
            if result:
                serialized_message = cast(six.binary_type, result[1])
        except Exception as e:
            if isinstance(self.backend_layer, SentinelRedisClient):
                self.backend_layer.reset_clients()
            self._get_counter('receive.error.unknown').increment()
            raise MessageReceiveError(
                'Unknown error receiving message for service {}'.format(self.service_name),
                six.text_type(type(e).__name__),
                *e.args
            )

        if serialized_message is None:
            raise MessageReceiveTimeout('No message received for service {}'.format(self.service_name))

        return serialized_message

    def receive_message(self, queue_name, receive_timeout_in_seconds=None):
        # type: (six.text_type, Optional[int]) -> ReceivedMessage
        """
        Receive a message from the specified queue in Redis.

        :param queue_name: The name of the queue to which to send the message
        :param receive_timeout_in_seconds: The optional timeout, which defaults to the setting with the same name

        :return: A tuple of request ID, message meta-information dict, and message body dict

        :raise: MessageReceiveError, MessageReceiveTimeout, InvalidMessageError
        """
        queue_key = self.QUEUE_NAME_PREFIX + queue_name
        receive_timeout_in_seconds = receive_timeout_in_seconds or self.receive_timeout_in_seconds

        connection = self._get_redis_connection(for_send=False, queue_key=queue_key)
        serialized_message = self._receive_message(connection, queue_key, receive_timeout_in_seconds)

        with self._get_timer('receive.deserialize') as deserialize_timer:
            protocol_version, serialized_message = ProtocolVersion.extract_version(serialized_message)
            headers, serialized_message = self._extract_supported_headers(serialized_message)

            serializer = self.default_serializer
            if 'content-type' in headers and headers['content-type'] in Serializer.all_supported_mime_types:
                serializer = Serializer.resolve_serializer(headers['content-type'])

        if 'chunk-count' in headers:
            if self.is_server:
                raise InvalidMessageError('Unsupported chunked request on server Redis backend')
            if 'chunk-id' not in headers:
                raise InvalidMessageError(
                    'Invalid chunked response missing chunk ID for service {}'.format(self.service_name),
                )

            chunk_headers = headers
            chunk_id, chunk_count = int(chunk_headers['chunk-id']), int(chunk_headers['chunk-count'])
            while chunk_id < chunk_count:
                expected_chunk = chunk_id + 1
                next_chunk = self._receive_message(connection, queue_key, receive_timeout_in_seconds)

                with deserialize_timer:
                    protocol_version, next_chunk = ProtocolVersion.extract_version(next_chunk)
                    chunk_headers, next_chunk = self._extract_supported_headers(next_chunk)
                    serialized_message += next_chunk

                if 'chunk-count' not in chunk_headers or 'chunk-id' not in chunk_headers:
                    raise InvalidMessageError(
                        'Invalid chunked response missing chunk headers expecting chunk {} of {} for service '
                        '{}.'.format(expected_chunk, chunk_count, self.service_name)
                    )
                if int(chunk_headers['chunk-count']) != chunk_count:
                    raise InvalidMessageError(
                        'Invalid chunked response has different chunk count {} expecting chunk {} of {} for service '
                        '{}.'.format(chunk_headers['chunk-count'], expected_chunk, chunk_count, self.service_name)
                    )
                if int(chunk_headers['chunk-id']) != expected_chunk:
                    raise InvalidMessageError(
                        'Invalid chunked response has incorrect chunk ID {} expected {} of {} for service '
                        '{}.'.format(chunk_headers['chunk-id'], expected_chunk, chunk_count, self.service_name)
                    )

                chunk_id, chunk_count = int(chunk_headers['chunk-id']), int(chunk_headers['chunk-count'])

        with deserialize_timer:
            message = serializer.blob_to_dict(serialized_message)
            message.setdefault('meta', {})['serializer'] = serializer
            message['meta']['protocol_version'] = protocol_version

        if self._is_message_expired(message):
            self._get_counter('receive.error.message_expired').increment()
            raise MessageReceiveTimeout('Message expired for service {}'.format(self.service_name))

        request_id = message.get('request_id')
        if request_id is None:
            self._get_counter('receive.error.no_request_id').increment()
            raise InvalidMessageError('No request ID for service {}'.format(self.service_name))

        return ReceivedMessage(request_id, message.get('meta', {}), message.get('body'))

    @staticmethod
    def _is_message_expired(message):  # type: (Dict[six.text_type, Any]) -> bool
        return message.get('meta', {}).get('__expiry__') and message['meta']['__expiry__'] < time.time()

    @abc.abstractmethod
    def _get_metric_name(self, name):  # type: (six.text_type) -> six.text_type
        """
        Get a suitable full metric name including appropriate client or server prefix.
        """

    def _get_counter(self, name):  # type: (six.text_type) -> Counter
        return self.metrics.counter(self._get_metric_name(name))

    def _get_histogram(self, name):  # type: (six.text_type) -> Histogram
        return self.metrics.histogram(self._get_metric_name(name))

    def _get_timer(self, name):  # type: (six.text_type) -> Timer
        return self.metrics.timer(self._get_metric_name(name), resolution=TimerResolution.MICROSECONDS)


def _convert_protocol_version(value):  # type: (Union[ProtocolVersion, int]) -> ProtocolVersion
    if isinstance(value, ProtocolVersion):
        return value
    return ProtocolVersion(value)


@attr.s
class RedisTransportClientCore(RedisTransportCore):
    protocol_version = attr.ib(
        default=ProtocolVersion.VERSION_3,
        converter=_convert_protocol_version,
    )  # type: ProtocolVersion

    @property
    def is_server(self):  # type: () -> bool
        return False

    def _get_metric_name(self, name):  # type: (six.text_type) -> six.text_type
        return 'client.transport.redis_gateway.{name}'.format(name=name)


@attr.s
class RedisTransportServerCore(RedisTransportCore):
    log_messages_larger_than_bytes = attr.ib(
        default=DEFAULT_MAXIMUM_MESSAGE_BYTES_SERVER,
        converter=int,
    )  # type: int

    maximum_message_size_in_bytes = attr.ib(
        default=DEFAULT_MAXIMUM_MESSAGE_BYTES_SERVER,
        converter=int,
    )  # type: int

    chunk_messages_larger_than_bytes = attr.ib(
        default=-1,
        converter=int,
        validator=_valid_chunk_threshold,
    )  # type: int

    def __attrs_post_init__(self):
        super(RedisTransportServerCore, self).__attrs_post_init__()

        if self.maximum_message_size_in_bytes < self.chunk_messages_larger_than_bytes * 5:
            raise ValueError(
                'If chunk_messages_larger_than_bytes is enabled (non-negative), maximum_message_size_in_bytes must '
                'be at least 5 times larger to allow for multiple chunks to be sent.',
            )

    @property
    def is_server(self):  # type: () -> bool
        return True

    def _get_metric_name(self, name):  # type: (six.text_type) -> six.text_type
        return 'server.transport.redis_gateway.{name}'.format(name=name)
