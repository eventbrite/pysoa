from __future__ import (
    absolute_import,
    unicode_literals,
)

import uuid

from pysoa.common.metrics import TimerResolution
from pysoa.common.transport.base import (
    ClientTransport,
    get_hex_thread_id,
)
from pysoa.common.transport.exceptions import MessageReceiveTimeout
from pysoa.common.transport.redis_gateway.backend.base import BaseRedisClient
from pysoa.common.transport.redis_gateway.constants import DEFAULT_MAXIMUM_MESSAGE_BYTES_CLIENT
from pysoa.common.transport.redis_gateway.core import RedisTransportCore
from pysoa.common.transport.redis_gateway.settings import RedisTransportSchema
from pysoa.common.transport.redis_gateway.utils import make_redis_queue_name


class RedisClientTransport(ClientTransport):

    def __init__(self, service_name, metrics, **kwargs):
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

        if 'maximum_message_size_in_bytes' not in kwargs:
            kwargs['maximum_message_size_in_bytes'] = DEFAULT_MAXIMUM_MESSAGE_BYTES_CLIENT

        self.client_id = uuid.uuid4().hex
        self._send_queue_name = make_redis_queue_name(service_name)
        self._receive_queue_name = '{send_queue_name}.{client_id}{response_queue_specifier}'.format(
            send_queue_name=self._send_queue_name,
            client_id=self.client_id,
            response_queue_specifier=BaseRedisClient.RESPONSE_QUEUE_SPECIFIER,
        )
        self._requests_outstanding = 0
        self.core = RedisTransportCore(service_name=service_name, metrics=metrics, metrics_prefix='client', **kwargs)

    @property
    def requests_outstanding(self):
        """
        Indicates the number of requests currently outstanding, which still need to be received. If this value is less
        than 1, calling `receive_response_message` will result in a return value of `(None, None, None)` instead of
        raising a `MessageReceiveTimeout`.
        """
        return self._requests_outstanding

    def send_request_message(self, request_id, meta, body, message_expiry_in_seconds=None):
        self._requests_outstanding += 1
        meta['reply_to'] = '{receive_queue_name}{thread_id}'.format(
            receive_queue_name=self._receive_queue_name,
            thread_id=get_hex_thread_id(),
        )

        with self.metrics.timer('client.transport.redis_gateway.send', resolution=TimerResolution.MICROSECONDS):
            self.core.send_message(self._send_queue_name, request_id, meta, body, message_expiry_in_seconds)

    def receive_response_message(self, receive_timeout_in_seconds=None):
        if self._requests_outstanding > 0:
            with self.metrics.timer('client.transport.redis_gateway.receive', resolution=TimerResolution.MICROSECONDS):
                try:
                    request_id, meta, response = self.core.receive_message(
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
            return request_id, meta, response
        else:
            # This tells Client.get_all_responses to stop waiting for more.
            return None, None, None


RedisClientTransport.settings_schema = RedisTransportSchema(RedisClientTransport)
