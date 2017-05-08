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
    ASGI_CHANNEL_TYPE_REDIS,
)

logger = logging.getLogger('pysoa.common.transport')


def valid_channel_type(instance, attribute, value):
    if not value or value not in ASGI_CHANNEL_TYPES:
        raise ValueError('asgi_channel_type must be one of {}, got {}'.format(ASGI_CHANNEL_TYPES, value))


class SentinelMasterConnectionList(object):

    def __init__(self, hosts, redis_kwargs=None, sentinel_refresh_interval=30):
        self.hosts = hosts
        self.sentinel_refresh_interval = sentinel_refresh_interval
        if redis_kwargs is None:
            redis_kwargs = {}
        self.redis_kwargs = redis_kwargs
        self._master_connection_list = []
        self._last_sentinel_refresh = 0
        self._maybe_refresh_masters()

    def _maybe_refresh_masters(self):
        if self._should_refresh_masters():
            hosts = self._get_master_info()
            self._master_connection_list = [redis.Redis.from_url(host, **self.redis_kwargs) for host in hosts]

    def _should_refresh_masters(self):
        return (time.time() - self._last_sentinel_refresh) > self.sentinel_refresh_interval

    def _get_master_info(self):
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
        self._last_sentinel_refresh = time.time()
        # Check that the number of hosts returned by Sentinel is the same as last time
        if self._master_connection_list and len(self._master_connection_list) != len(master_info_list):
            # If this happens, you have an Ops problem
            logger.warning('Number of Redis masters changed since last refresh! Messages may be lost.')
        self._master_connection_list = sorted(
            ['redis://{}:{}/0'.format(info['ip'], info['port']) for info in master_info_list])
        self.ring_size = len(master_info_list)

    def __iter__(self):
        self._maybe_refresh_masters()
        return iter(self._master_connection_list)

    def __getitem__(self, key):
        self._maybe_refresh_masters()
        return self._master_connection_list[key]

    def __len__(self):
        self._maybe_refresh_masters()
        return len(self._master_connection_list)


class SentinelRedisChannelLayer(RedisChannelLayer):

    def _generate_connections(self, redis_kwargs):
        return SentinelMasterConnectionList(self.hosts, redis_kwargs)


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
        self._channel_layer = None

    @property
    def channel_layer(self):
        if self._channel_layer is None:
            self._make_channel_layer()
        return self._channel_layer

    def _make_channel_layer(self):
        """Make an ASGI channel layer for either Redis or local backend."""
        if self.asgi_channel_type == ASGI_CHANNEL_TYPE_REDIS_SENTINEL:
            self._channel_layer = SentinelRedisChannelLayer(self.hosts)
        elif self.asgi_channel_type == ASGI_CHANNEL_TYPE_REDIS:
            host_urls = ['redis://{}:{}/{}'.format(h[0], h[1], self.redis_db) for h in self.hosts]
            self._channel_layer = RedisChannelLayer(host_urls)
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
