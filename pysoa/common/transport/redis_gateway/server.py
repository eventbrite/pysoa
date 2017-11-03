from __future__ import absolute_import, unicode_literals

from pysoa.common.transport.base import ServerTransport
from pysoa.common.transport.exceptions import InvalidMessageError
from pysoa.common.transport.redis_gateway.core import RedisTransportCore
from pysoa.common.transport.redis_gateway.utils import make_redis_queue_name


class RedisServerTransport(ServerTransport):

    def __init__(self, service_name, **kwargs):
        super(RedisServerTransport, self).__init__(service_name)

        self._receive_queue_name = make_redis_queue_name(service_name)
        self.core = RedisTransportCore(**kwargs)

    def receive_request_message(self):
        return self.core.receive_message(self._receive_queue_name)

    def send_response_message(self, request_id, meta, body):
        try:
            queue_name = meta['reply_to']
        except KeyError:
            raise InvalidMessageError('Missing reply queue name')
        self.core.send_message(queue_name, request_id, meta, body)
