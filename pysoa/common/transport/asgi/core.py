from __future__ import unicode_literals

import random
import six
import time
import logging
from copy import deepcopy

import attr
from asgi_redis import (
    RedisChannelLayer,
    RedisSentinelChannelLayer,
)

from pysoa.common.transport.exceptions import (
    MessageTooLarge,
    MessageReceiveError,
    MessageSendError,
    InvalidMessageError,
    MessageReceiveTimeout,
)

from .constants import (
    ASGI_CHANNEL_TYPES,
    ASGI_CHANNEL_TYPE_LOCAL,
    ASGI_CHANNEL_TYPE_REDIS_SENTINEL,
    ASGI_CHANNEL_TYPE_REDIS,
)

logger = logging.getLogger('pysoa.common.transport')


def valid_channel_type(instance, attribute, value):
    if not value or value not in ASGI_CHANNEL_TYPES:
        raise ValueError('asgi_channel_type must be one of {}, got {}'.format(ASGI_CHANNEL_TYPES, value))


@attr.s()
class ASGITransportCore(object):
    """Handles communication with the ASGI channel layer. Supports Redis and local backends."""

    asgi_channel_type = attr.ib(validator=valid_channel_type)
    redis_hosts = attr.ib(
        default=['localhost'],
        validator=attr.validators.instance_of(list),
    )
    redis_port = attr.ib(
        default=6379,
        convert=int,
    )
    sentinel_refresh_interval = attr.ib(
        # Number of seconds to wait between refreshing masters from Sentinel (Sentinel mode only)
        default=30,
        convert=int,
    )
    sentinel_services = attr.ib(
        # List of Sentinel service names to use (Sentinel mode only)
        default=[],
        validator=attr.validators.instance_of(list),
    )
    redis_db = attr.ib(
        # Redis db to use for all master connections (Redis and Sentinel modes)
        default=0,
        convert=int,
    )
    channel_capacities = attr.ib(
        # Mapping of channel name regex to max capacity (Redis and Sentinel modes)
        default={},
        convert=dict,
    )
    channel_layer_kwargs = attr.ib(
        # Keyword args for the ASGI channel layer (Redis and Sentinel modes)
        default={},
        validator=attr.validators.instance_of(dict),
    )
    channel_full_retries = attr.ib(
        # Number of times to retry when the backend raises ChannelFull (all modes)
        default=10,
        convert=int,
    )

    EXPONENTIAL_BACKOFF_FACTOR = 4.0
    BODY_MAX_SIZE = 1024 * 100

    def __attrs_post_init__(self):
        # set the hosts property after all attrs are validated
        final_hosts = []
        for host in self.redis_hosts:
            if isinstance(host, tuple) and len(host) == 2:
                final_hosts.append(host)
            elif isinstance(host, six.string_types):
                final_hosts.append((host, self.redis_port))
            else:
                raise Exception('redis_hosts must be a list of strings or tuples of (host, port)')
        self.hosts = final_hosts
        self._channel_layer = None

    @property
    def channel_layer(self):
        if self._channel_layer is None:
            self._make_channel_layer()
        return self._channel_layer

    def _make_channel_layer(self):
        """Make an ASGI channel layer for either Redis or local backend."""
        channel_layer_kwargs = deepcopy(self.channel_layer_kwargs)
        channel_layer_kwargs.setdefault('connection_kwargs', {}).update({'db': self.redis_db})
        channel_layer_kwargs['hosts'] = self.hosts
        channel_layer_kwargs['channel_capacity'] = self.channel_capacities
        if self.asgi_channel_type == ASGI_CHANNEL_TYPE_REDIS_SENTINEL:
            channel_layer_kwargs['services'] = self.sentinel_services
            channel_layer_kwargs['sentinel_refresh_interval'] = self.sentinel_refresh_interval
            self._channel_layer = RedisSentinelChannelLayer(**channel_layer_kwargs)
        elif self.asgi_channel_type == ASGI_CHANNEL_TYPE_REDIS:
            self._channel_layer = RedisChannelLayer(**channel_layer_kwargs)
        elif self.asgi_channel_type == ASGI_CHANNEL_TYPE_LOCAL:
            from asgiref.inmemory import channel_layer
            self._channel_layer = channel_layer

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
