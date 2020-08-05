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
from pysoa.common.transport.redis_gateway.settings import RedisServerTransportSchema
from pysoa.common.transport.redis_gateway.utils import make_redis_queue_name


@fields.ClassConfigurationSchema.provider(RedisServerTransportSchema)
class RedisServerTransport(ServerTransport):

    def __init__(self, service_name, metrics, instance_index, **kwargs):
        # type: (six.text_type, MetricsRecorder, int, **Any) -> None
        """
        In addition to the named positional arguments, this constructor expects keyword arguments abiding by the
        Redis transport settings schema.

        :param service_name: The name of the service for which this transport will receive requests and send responses
        :param metrics: The optional metrics recorder
        :param instance_index: The 1-based index of this process among multiple forks
        """
        super(RedisServerTransport, self).__init__(service_name, metrics, instance_index)

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
