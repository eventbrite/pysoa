from __future__ import (
    absolute_import,
    unicode_literals,
)

from pysoa.common.metrics import TimerResolution
from pysoa.common.transport.base import ServerTransport
from pysoa.common.transport.exceptions import (
    InvalidMessageError,
    MessageReceiveTimeout,
)
from pysoa.common.transport.redis_gateway.constants import DEFAULT_MAXIMUM_MESSAGE_BYTES_SERVER
from pysoa.common.transport.redis_gateway.core import RedisTransportCore
from pysoa.common.transport.redis_gateway.settings import RedisTransportSchema
from pysoa.common.transport.redis_gateway.utils import make_redis_queue_name


class RedisServerTransport(ServerTransport):

    def __init__(self, service_name, metrics, **kwargs):
        """
        In addition to the two named positional arguments, this constructor expects keyword arguments abiding by the
        Redis transport settings schema.

        :param service_name: The name of the service for which this transport will receive requests and send responses
        :type service_name: union[str, unicode]
        :param metrics: The optional metrics recorder
        :type metrics: MetricsRecorder
        """
        super(RedisServerTransport, self).__init__(service_name, metrics)

        if 'maximum_message_size_in_bytes' not in kwargs:
            kwargs['maximum_message_size_in_bytes'] = DEFAULT_MAXIMUM_MESSAGE_BYTES_SERVER

        self._receive_queue_name = make_redis_queue_name(service_name)
        self.core = RedisTransportCore(service_name=service_name, metrics=metrics, metrics_prefix='server', **kwargs)

    def receive_request_message(self):
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
        try:
            queue_name = meta['reply_to']
        except KeyError:
            self.metrics.counter('server.transport.redis_gateway.send.error.missing_reply_queue')
            raise InvalidMessageError('Missing reply queue name')

        with self.metrics.timer('server.transport.redis_gateway.send', resolution=TimerResolution.MICROSECONDS):
            self.core.send_message(queue_name, request_id, meta, body)


RedisServerTransport.settings_schema = RedisTransportSchema(RedisServerTransport)
