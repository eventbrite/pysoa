from __future__ import unicode_literals

import random
import six
import time
import logging

import attr
from asgi_redis import RedisChannelLayer
import redis

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
        validator=attr.validators.instance_of((list, tuple)),
    )
    redis_port = attr.ib(
        default=6379,
        convert=int,
    )
    sentinel_refresh_interval = attr.ib(
        default=30,
        convert=int,
    )
    redis_db = attr.ib(
        default=0,
        convert=int,
    )
    channel_full_retries = attr.ib(
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
        self.channel_layer = None
        self._last_sentinel_refresh = 0
        self._last_sentinel_ring_size = None

    def _get_masters_from_sentinel(self):
        """
        Get a list of Redis masters from Sentinel. Tries Sentinel hosts until one succeeds; if none succeed,
        raises a ConnectionError.

        Returns: list of tuples of (host, port)
        """
        master_info_list = []
        connection_errors = []
        for host in random.shuffle(self.hosts):
            try:
                redis_client = redis.StrictRedis(
                    host=host[0],
                    port=host[1],
                )
                master_info_list = redis_client.sentinel_masters()
                break
            except redis.ConnectionError as e:
                connection_errors.append(
                    'Failed to connect to redis://%s:%d: %s' %
                    (host[0], host[1], str(e))
                )
                continue
        if not master_info_list:
            raise ConnectionError('Could not get master info from sentinel\n{}.'.format('\n'.join(connection_errors)))
        if self._last_sentinel_ring_size is None:
            self._last_sentinel_ring_size = len(master_info_list)
        elif self._last_sentinel_ring_size != len(master_info_list):
            # If this happens, you have an Ops problem
            logger.warning('Number of Redis masters changed since last refresh! Messages may be lost.')
        # Sort the masters just in case the order changes
        return sorted([(info['ip'], info['port']) for info in master_info_list])

    def _should_refresh_channel_layer(self):
        if self.channel_layer is None:
            return True
        elif self.asgi_channel_type == ASGI_CHANNEL_TYPE_REDIS_SENTINEL:
            return (time.time() - self._last_sentinel_refresh) > self.sentinel_refresh_interval
        return False

    def _refresh_channel_layer(self):
        """Make an ASGI channel layer for either Redis or local backend."""
        if self._should_refresh_channel_layer():
            if self.asgi_channel_type in ASGI_CHANNEL_TYPES_REDIS:
                if self.asgi_channel_type == ASGI_CHANNEL_TYPE_REDIS_SENTINEL:
                    hosts = self._get_masters_from_sentinel()
                else:
                    hosts = self.hosts
                host_urls = ['redis://{}:{}/{}'.format(h[0], h[1], self.redis_db) for h in hosts]
                self.channel_layer = RedisChannelLayer(hosts=host_urls)

            elif self.asgi_channel_type == ASGI_CHANNEL_TYPE_LOCAL:
                from asgiref.inmemory import channel_layer
                self.channel_layer = channel_layer

    def send_message(self, channel, request_id, meta, body):
        self._refresh_channel_layer()
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
        self._refresh_channel_layer()
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
