from __future__ import absolute_import, unicode_literals

import random
import six
import time
import logging
from copy import deepcopy

import attr
import redis

from pysoa.common.metrics import (
    MetricsRecorder,
    NoOpMetricsRecorder,
)
from pysoa.common.serializer.msgpack_serializer import MsgpackSerializer
from pysoa.common.transport.exceptions import (
    MessageTooLarge,
    MessageReceiveError,
    MessageSendError,
    InvalidMessageError,
    MessageReceiveTimeout,
)
from pysoa.common.transport.redis_gateway.backend.sentinel import SentinelRedisClient
from pysoa.common.transport.redis_gateway.backend.standard import StandardRedisClient
from pysoa.common.transport.redis_gateway.constants import (
    REDIS_BACKEND_TYPE_SENTINEL,
    REDIS_BACKEND_TYPES,
)


logger = logging.getLogger('pysoa.common.transport')


def valid_backend_type(_, __, value):
    if not value or value not in REDIS_BACKEND_TYPES:
        raise ValueError('backend_type must be one of {}, got {}'.format(REDIS_BACKEND_TYPES, value))


@attr.s()
class RedisTransportCore(object):
    """Handles communication with Redis."""

    backend_type = attr.ib(validator=valid_backend_type)

    backend_layer_kwargs = attr.ib(
        # Keyword args for the backend layer (Standard Redis and Sentinel Redis modes)
        default={},
        validator=attr.validators.instance_of(dict),
    )

    message_expiry_in_seconds = attr.ib(
        # How long after a message is sent before it's considered "expired" and not received
        default=60,
        convert=int,
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
        convert=int,
    )

    queue_full_retries = attr.ib(
        # Number of times to retry when the send queue is full
        default=10,
        convert=int,
    )

    receive_timeout_in_seconds = attr.ib(
        # How long to block when waiting to receive a message
        default=5,
        convert=int,
    )

    serializer_config = attr.ib(
        # Configuration for which serializer should be used by this transport
        default={'object': MsgpackSerializer, 'kwargs': {}},
        convert=dict,
    )

    EXPONENTIAL_BACK_OFF_FACTOR = 4.0
    MAXIMUM_MESSAGE_BYTES = 1024 * 100
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
        self._serializer = None

    # noinspection PyAttributeOutsideInit
    @property
    def backend_layer(self):
        if self._backend_layer is None:
            backend_layer_kwargs = deepcopy(self.backend_layer_kwargs)
            with self._get_timer('backend.initialize'):
                if self.backend_type == REDIS_BACKEND_TYPE_SENTINEL:
                    self._backend_layer = SentinelRedisClient(**backend_layer_kwargs)
                else:
                    self._backend_layer = StandardRedisClient(**backend_layer_kwargs)

        return self._backend_layer

    # noinspection PyAttributeOutsideInit
    @property
    def serializer(self):
        if self._serializer is None:
            self._serializer = self.serializer_config['object'](**self.serializer_config.get('kwargs', {}))

        return self._serializer

    def send_message(self, queue_name, request_id, meta, body):
        """
        Send a message to the specified queue in Redis.

        :param queue_name: The name of the queue to which to send the message
        :param request_id: The message's request ID
        :param meta: The meta information, if any (should be an empty dict if no metadata)
        :param body: The message body (should be a dict)
        :raise
        """
        if request_id is None:
            raise InvalidMessageError('No request ID')

        meta['__expiry__'] = self._get_message_expiry()

        message = {'request_id': request_id, 'meta': meta, 'body': body}

        with self._get_timer('send.serialize'):
            serialized_message = self.serializer.dict_to_blob(message)

        if len(serialized_message) > self.MAXIMUM_MESSAGE_BYTES:
            self._get_counter('send.error.message_too_large').increment()
            raise MessageTooLarge()

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
                        expiry=self.message_expiry_in_seconds,
                        capacity=self.queue_capacity,
                        connection=connection,
                    )
                return
            except redis.exceptions.ResponseError as e:
                # The Lua script handles capacity checking and sends the "full" error back
                if e.args[0] == 'queue full':
                    continue
                self._get_counter('send.error.unknown').increment()
                raise MessageSendError(*e.args)
            except Exception as e:
                self._get_counter('send.error.unknown').increment()
                raise MessageSendError(*e.args)

        self._get_counter('send.error.redis_queue_full').increment()

        raise MessageSendError(
            'Redis queue {queue_name} was full after {retries} retries'.format(
                queue_name=queue_name,
                retries=self.queue_full_retries,
            )
        )

    def receive_message(self, queue_name):
        queue_key = self.QUEUE_NAME_PREFIX + queue_name

        try:
            with self._get_timer('receive.get_redis_connection'):
                connection = self.backend_layer.get_connection(queue_key)
            # returns message or None if no new messages within timeout
            with self._get_timer('receive.pop_from_redis_queue'):
                result = connection.blpop([queue_key], timeout=self.receive_timeout_in_seconds)
            serialized_message = None
            if result:
                serialized_message = result[1]
        except Exception as e:
            self._get_counter('receive.error.unknown').increment()
            raise MessageReceiveError(*e.args)

        if serialized_message is None:
            raise MessageReceiveTimeout('No message received')

        with self._get_timer('receive.deserialize'):
            message = self.serializer.blob_to_dict(serialized_message)

        if self._is_message_expired(message):
            self._get_counter('receive.error.message_expired').increment()
            raise MessageReceiveTimeout('Message expired')

        request_id = message.get('request_id')
        if request_id is None:
            self._get_counter('receive.error.no_request_id').increment()
            raise InvalidMessageError('No request ID')

        return request_id, message.get('meta', {}), message.get('body')

    def _get_message_expiry(self):
        return time.time() + self.message_expiry_in_seconds

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
        return self.metrics.timer(self._get_metric_name(name))
