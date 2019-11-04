from __future__ import (
    absolute_import,
    unicode_literals,
)

from typing import (
    Any,
    Dict,
)

from conformity import fields
from pymetrics.instruments import TimerResolution
from pymetrics.recorders.base import MetricsRecorder
import six

from pysoa.common.transport.base import (
    ReceivedMessage,
    ServerTransport,
)
from pysoa.common.transport.errors import (
    InvalidMessageError,
    MessageReceiveTimeout,
)
from pysoa.common.transport.redis_gateway.core import RedisTransportServerCore
from pysoa.common.transport.redis_gateway.settings import RedisTransportSchema
from pysoa.common.transport.redis_gateway.utils import make_redis_queue_name


@fields.ClassConfigurationSchema.provider(RedisTransportSchema().extend(
    contents={
        'chunk_messages_larger_than_bytes': fields.Integer(
            description='If set, responses larger than this setting will be chunked and sent back to the client in '
                        'pieces, to prevent blocking single-threaded Redis for long periods of time to handle large '
                        'responses. When set, this value must be greater than or equal to 102400, and '
                        '`maximum_message_size_in_bytes` must also be set and must be at least 5 times greater than '
                        'this value (because `maximum_message_size_in_bytes` is still enforced).',
        ),
    },
    optional_keys=('chunk_messages_larger_than_bytes', ),
    description='The constructor kwargs for the Redis server transport.',
))
class RedisServerTransport(ServerTransport):

    def __init__(self, service_name, metrics, **kwargs):
        # type: (six.text_type, MetricsRecorder, **Any) -> None
        """
        In addition to the two named positional arguments, this constructor expects keyword arguments abiding by the
        Redis transport settings schema.

        :param service_name: The name of the service for which this transport will receive requests and send responses
        :param metrics: The optional metrics recorder
        """
        super(RedisServerTransport, self).__init__(service_name, metrics)

        self._receive_queue_name = make_redis_queue_name(service_name)
        # noinspection PyArgumentList
        self.core = RedisTransportServerCore(service_name=service_name, metrics=metrics, **kwargs)

    def receive_request_message(self):
        # type: () -> ReceivedMessage
        timer = self.metrics.timer('server.transport.redis_gateway.receive', resolution=TimerResolution.MICROSECONDS)
        timer.start()
        stop_timer = True
        try:
            return self.core.receive_message(self._receive_queue_name)
        except MessageReceiveTimeout:
            stop_timer = False
            raise
        finally:
            if stop_timer:
                timer.stop()

    def send_response_message(self, request_id, meta, body):
        # type: (int, Dict[six.text_type, Any], Dict[six.text_type, Any]) -> None
        try:
            queue_name = meta['reply_to']
        except KeyError:
            self.metrics.counter('server.transport.redis_gateway.send.error.missing_reply_queue')
            raise InvalidMessageError('Missing reply queue name')

        with self.metrics.timer('server.transport.redis_gateway.send', resolution=TimerResolution.MICROSECONDS):
            self.core.send_message(queue_name, request_id, meta, body)
