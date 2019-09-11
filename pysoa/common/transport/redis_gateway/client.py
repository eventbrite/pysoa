from __future__ import (
    absolute_import,
    unicode_literals,
)

from typing import (  # noqa: F401 TODO Python 3
    Any,
    Dict,
    Optional,
)
import uuid

from conformity import fields
import six  # noqa: F401 TODO Python 3

from pysoa.common.metrics import (  # noqa: F401 TODO Python 3
    MetricsRecorder,
    TimerResolution,
)
from pysoa.common.transport.base import (
    ClientTransport,
    ReceivedMessage,
    get_hex_thread_id,
)
from pysoa.common.transport.exceptions import MessageReceiveTimeout
from pysoa.common.transport.redis_gateway.backend.base import BaseRedisClient
from pysoa.common.transport.redis_gateway.constants import ProtocolVersion
from pysoa.common.transport.redis_gateway.core import RedisTransportClientCore
from pysoa.common.transport.redis_gateway.settings import RedisTransportSchema
from pysoa.common.transport.redis_gateway.utils import (
    set_mangled_service_data_route_map,
    get_route_map_server_queue,
    get_route_map_for_token,
    make_redis_queue_name,
)


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
        :type service_name: union[str, unicode]
        :param metrics: The optional metrics recorder
        :type metrics: MetricsRecorder
        """
        super(RedisClientTransport, self).__init__(service_name, metrics)

        self.client_id = uuid.uuid4().hex
        self.service_name = service_name
        self._send_queue_name = make_redis_queue_name(self.service_name)
        self._receive_queue_name = '{send_queue_name}.{client_id}{response_queue_specifier}'.format(
            send_queue_name=self._send_queue_name,
            client_id=self.client_id,
            response_queue_specifier=BaseRedisClient.RESPONSE_QUEUE_SPECIFIER,
        )
        self._requests_outstanding = 0
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
        self._requests_outstanding += 1
        meta['reply_to'] = '{receive_queue_name}{thread_id}'.format(
            receive_queue_name=self._receive_queue_name,
            thread_id=get_hex_thread_id(),
        )

        mangled_service_name = None
        route_map_user = get_route_map_for_token(meta.get('route_key'))
        if route_map_user:
            mangled_service_name = get_route_map_server_queue(self.service_name, route_map_user)

        send_queue_name = self._send_queue_name
        if mangled_service_name:
            send_queue_name = make_redis_queue_name(mangled_service_name)
            set_mangled_service_data_route_map(self.service_name, mangled_service_name)

        with self.metrics.timer('client.transport.redis_gateway.send', resolution=TimerResolution.MICROSECONDS):
            self.core.send_message(send_queue_name, request_id, meta, body, message_expiry_in_seconds)

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
                    self.metrics.counter('client.transport.redis_gateway.receive.error.timeout').increment()
                    raise
            self._requests_outstanding -= 1
            return received_message
        else:
            # This tells Client.get_all_responses to stop waiting for more.
            return ReceivedMessage(None, None, None)
