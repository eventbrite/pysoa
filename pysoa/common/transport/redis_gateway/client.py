from __future__ import (
    absolute_import,
    unicode_literals,
)

from typing import (
    Any,
    Dict,
    Optional,
)
import uuid

from conformity import fields
from pymetrics.instruments import TimerResolution
from pymetrics.recorders.base import MetricsRecorder
import six

from pysoa.common.transport.base import (
    ClientTransport,
    ReceivedMessage,
    get_hex_thread_id,
)
from pysoa.common.transport.errors import (
    MessageReceiveTimeout,
    TransientPySOATransportError,
)
from pysoa.common.transport.redis_gateway.backend.base import BaseRedisClient
from pysoa.common.transport.redis_gateway.constants import ProtocolVersion
from pysoa.common.transport.redis_gateway.core import RedisTransportClientCore
from pysoa.common.transport.redis_gateway.settings import RedisTransportSchema
from pysoa.common.transport.redis_gateway.utils import make_redis_queue_name


@fields.ClassConfigurationSchema.provider(RedisTransportSchema().extend(
    contents={
        'protocol_version': fields.Any(
            fields.Integer(),
            fields.ObjectInstance(valid_type=ProtocolVersion),
            description='The default protocol version between clients and servers was Version 1 prior to PySOA '
                        '0.67.0, Version 2 as of 0.67.0, and will be Version 3 as of 1.0.0. The server can only '
                        'detect what protocol the client is speaking and respond with the same protocol. However, '
                        'the client cannot pre-determine what protocol the server is speaking. So, if you need to '
                        'differ from the default (currently Version 2), use this setting to tell the client which '
                        'protocol to speak.',
        ),
    },
    optional_keys=('protocol_version', ),
    description='The constructor kwargs for the Redis client transport.',
))
class RedisClientTransport(ClientTransport):

    def __init__(self, service_name, metrics, **kwargs):
        # type: (six.text_type, MetricsRecorder, **Any) -> None
        """
        In addition to the two named positional arguments, this constructor expects keyword arguments abiding by the
        Redis transport settings schema.

        :param service_name: The name of the service to which this transport will send requests (and from which it will
                             receive responses)
        :param metrics: The optional metrics recorder
        """
        super(RedisClientTransport, self).__init__(service_name, metrics)

        self.client_id = uuid.uuid4().hex
        self._send_queue_name = make_redis_queue_name(service_name)
        self._receive_queue_name = '{send_queue_name}.{client_id}{response_queue_specifier}'.format(
            send_queue_name=self._send_queue_name,
            client_id=self.client_id,
            response_queue_specifier=BaseRedisClient.RESPONSE_QUEUE_SPECIFIER,
        )
        self._requests_outstanding = 0
        self._previous_error_was_transport_problem = False
        # noinspection PyArgumentList
        self.core = RedisTransportClientCore(service_name=service_name, metrics=metrics, **kwargs)

    @property
    def requests_outstanding(self):  # type: () -> int
        """
        Indicates the number of requests currently outstanding, which still need to be received. If this value is less
        than 1, calling `receive_response_message` will result in a return value of `(None, None, None)` instead of
        raising a `MessageReceiveTimeout`.
        """
        return self._requests_outstanding

    def send_request_message(self, request_id, meta, body, message_expiry_in_seconds=None):
        # type: (int, Dict[six.text_type, Any], Dict[six.text_type, Any], Optional[int]) -> None
        meta['reply_to'] = '{receive_queue_name}{thread_id}'.format(
            receive_queue_name=self._receive_queue_name,
            thread_id=get_hex_thread_id(),
        )

        with self.metrics.timer('client.transport.redis_gateway.send', resolution=TimerResolution.MICROSECONDS):
            try:
                self.core.send_message(self._send_queue_name, request_id, meta, body, message_expiry_in_seconds)
                # If we increment this before sending and sending fails, the client will be broken forever, so only
                # increment when sending succeeds.
                self._requests_outstanding += 1
            except TransientPySOATransportError:
                self._previous_error_was_transport_problem = True
                self.metrics.counter('client.transport.redis_gateway.send.error.transient').increment()
                raise

    def receive_response_message(self, receive_timeout_in_seconds=None):
        # type: (Optional[int]) -> ReceivedMessage
        if self._requests_outstanding > 0:
            with self.metrics.timer('client.transport.redis_gateway.receive', resolution=TimerResolution.MICROSECONDS):
                try:
                    received_message = self.core.receive_message(
                        '{receive_queue_name}{thread_id}'.format(
                            receive_queue_name=self._receive_queue_name,
                            thread_id=get_hex_thread_id(),
                        ),
                        receive_timeout_in_seconds,
                    )
                except MessageReceiveTimeout:
                    if self._previous_error_was_transport_problem:
                        # We're almost certainly recovering from a failover
                        self._requests_outstanding = 0
                        self._previous_error_was_transport_problem = False
                    self.metrics.counter('client.transport.redis_gateway.receive.error.timeout').increment()
                    raise
                except TransientPySOATransportError:
                    self._previous_error_was_transport_problem = True
                    self.metrics.counter('client.transport.redis_gateway.receive.error.transient').increment()
                    raise
            self._requests_outstanding -= 1
            return received_message
        else:
            self._previous_error_was_transport_problem = False
            # This tells Client.get_all_responses to stop waiting for more.
            return ReceivedMessage(None, None, None)
