from __future__ import unicode_literals

import time
import random
from redis import StrictRedis
from asgi_redis import RedisChannelLayer
import attr

from pysoa.common.transport.exceptions import (
    MessageTooLarge,
    MessageReceiveError,
    MessageSendError,
    ConnectionError,
    InvalidMessageError,
    MessageReceiveTimeout,
)

from .constants import (
    ASGI_CHANNEL_TYPES,
    ASGI_CHANNEL_TYPE_LOCAL,
    ASGI_CHANNEL_TYPE_REDIS_SENTINEL,
    ASGI_CHANNEL_TYPES_REDIS,
)


def valid_channel_type(instance, attribute, value):
    if not value or value not in ASGI_CHANNEL_TYPES:
        raise ValueError('asgi_channel_type must be one of {}, got {}'.format(ASGI_CHANNEL_TYPES, value))


@attr.s()
class ASGITransportCore(object):
    """Handles communication with the ASGI channel layer. Supports Redis and local backends."""

    asgi_channel_type = attr.ib(validator=valid_channel_type)
    asgi_channel_redis_host = attr.ib(default='localhost')
    asgi_channel_redis_port = attr.ib(default=6379)
    asgi_channel_redis_db = attr.ib(default=0)
    channel_full_retries = attr.ib(default=10)

    EXPONENTIAL_BACKOFF_FACTOR = 4.0
    BODY_MAX_SIZE = 1024 * 100

    _channel_layer = None

    @property
    def channel_layer(self):
        if self._channel_layer is None:
            try:
                self._channel_layer = self._make_asgi_channel_layer()
            except Exception as e:
                raise ConnectionError(*e.args)
        return self._channel_layer

    def _make_asgi_channel_layer(self):
        """
        Make an ASGI channel layer for either Redis or local backend. In the Redis case, get master
        configuration from Sentinel if it is available.
        """
        if self.asgi_channel_type in ASGI_CHANNEL_TYPES_REDIS:
            redis_host = self.asgi_channel_redis_host
            redis_port = self.asgi_channel_redis_port
            redis_db = self.asgi_channel_redis_db
            if self.asgi_channel_type == ASGI_CHANNEL_TYPE_REDIS_SENTINEL:
                # Get active Redis master host/port from Sentinel
                redis_client = StrictRedis(
                    host=redis_host,
                    port=redis_port,
                )
                master_info = redis_client.execute_command(
                    'SENTINEL',
                    'MASTERS',
                    parse='SENTINEL_INFO',
                )
                redis_host = master_info[0]['ip']
                redis_port = master_info[0]['port']

            redis_uri = 'redis://{}:{}/{}/'.format(
                redis_host,
                redis_port,
                redis_db,
            )
            return RedisChannelLayer(
                hosts=[redis_uri],
            )
        elif self.asgi_channel_type == ASGI_CHANNEL_TYPE_LOCAL:
            from asgiref.inmemory import channel_layer
            return channel_layer

    def send_message(self, channel, request_id, meta, body):
        if request_id is None:
            raise InvalidMessageError('No request ID')
        if len(body) > self.BODY_MAX_SIZE:
            raise MessageTooLarge
        message = {
            'request_id': request_id,
            'meta': meta,
            'body': body,
        }
        # Try at least once, up to channel_full_retries times, then error
        for i in range(-1, self.channel_full_retries):
            if i >= 0:
                time.sleep((2 ** i + random.random()) / self.EXPONENTIAL_BACKOFF_FACTOR)
            try:
                self.channel_layer.send(channel, message)
                return
            except self.channel_layer.ChannelFull:
                continue
        raise MessageSendError('Channel {channel} was full after {retries} retries'.format(
            channel=channel, retries=self.channel_full_retries))

    def receive_message(self, channel):
        try:
            # returns message or None if no new messages within timeout (5s by default)
            _, message = self.channel_layer.receive([channel], block=True)
        except Exception as e:
            raise MessageReceiveError(*e.args)
        if message is None:
            raise MessageReceiveTimeout()
        request_id = message.get('request_id')
        if request_id is None:
            raise InvalidMessageError('No request ID')
        meta = message.get('meta', {})
        body = message.get('body')
        return (request_id, meta, body)
