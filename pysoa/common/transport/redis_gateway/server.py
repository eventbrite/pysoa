from __future__ import absolute_import, unicode_literals

from pysoa.common.transport.base import ServerTransport
from pysoa.common.transport.exceptions import InvalidMessageError
from pysoa.common.transport.redis_gateway.core import RedisTransportCore
from pysoa.common.transport.redis_gateway.utils import make_redis_queue_name


class RedisServerTransport(ServerTransport):

    def __init__(self, service_name, metrics, **kwargs):
        super(RedisServerTransport, self).__init__(service_name, metrics)

        self._receive_queue_name = make_redis_queue_name(service_name)
        self.core = RedisTransportCore(metrics=metrics, metrics_prefix='server', **kwargs)

    def receive_request_message(self):
        with self.metrics.timer('server.transport.redis_gateway.receive'):
            return self.core.receive_message(self._receive_queue_name)

    def send_response_message(self, request_id, meta, body):
        try:
            queue_name = meta['reply_to']
        except KeyError:
            self.metrics.counter('server.transport.redis_gateway.send.error.missing_reply_queue')
            raise InvalidMessageError('Missing reply queue name')

        with self.metrics.timer('server.transport.redis_gateway.send'):
            self.core.send_message(queue_name, request_id, meta, body)
