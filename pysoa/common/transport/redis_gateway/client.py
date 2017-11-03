from __future__ import absolute_import, unicode_literals

import uuid

from pysoa.common.transport.base import ClientTransport
from pysoa.common.transport.redis_gateway.backend.base import BaseRedisClient
from pysoa.common.transport.redis_gateway.core import RedisTransportCore
from pysoa.common.transport.redis_gateway.utils import make_redis_queue_name


class RedisClientTransport(ClientTransport):

    def __init__(self, service_name, metrics, **kwargs):
        super(RedisClientTransport, self).__init__(service_name, metrics)

        self.client_id = uuid.uuid4().hex
        self._send_queue_name = make_redis_queue_name(service_name)
        self._receive_queue_name = '{send_queue_name}.{client_id}{response_queue_specifier}'.format(
            send_queue_name=self._send_queue_name,
            client_id=self.client_id,
            response_queue_specifier=BaseRedisClient.RESPONSE_QUEUE_SPECIFIER,
        )
        self._requests_outstanding = 0
        self.core = RedisTransportCore(metrics=metrics, metrics_prefix='client', **kwargs)

    @property
    def requests_outstanding(self):
        return self._requests_outstanding

    def send_request_message(self, request_id, meta, body):
        self._requests_outstanding += 1
        meta['reply_to'] = self._receive_queue_name

        with self.metrics.timer('client.transport.redis_gateway.send'):
            self.core.send_message(self._send_queue_name, request_id, meta, body)

    def receive_response_message(self):
        if self._requests_outstanding > 0:
            with self.metrics.timer('client.transport.redis_gateway.receive'):
                request_id, meta, response = self.core.receive_message(self._receive_queue_name)
            self._requests_outstanding -= 1
            return request_id, meta, response
        else:
            # This tells Client.get_all_responses to stop waiting for more.
            return None, None, None
