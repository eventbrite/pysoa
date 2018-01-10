from __future__ import unicode_literals

from conformity import fields

from pysoa.client.middleware import ClientMiddleware
from pysoa.common.settings import (
    BasicClassSchema,
    SOASettings,
)
from pysoa.common.transport.base import ClientTransport as BaseClientTransport
from pysoa.common.transport.local import (
    LocalClientTransport,
    LocalTransportSchema,
)
from pysoa.common.transport.redis_gateway.client import RedisClientTransport
from pysoa.common.transport.redis_gateway.settings import RedisTransportSchema


class ClientSettings(SOASettings):
    """Generic settings for a Client."""
    schema = {
        'middleware': fields.List(BasicClassSchema(ClientMiddleware)),
        'transport': BasicClassSchema(BaseClientTransport),
        'transport_cache_time_in_seconds': fields.Integer(
            gte=0,
            description='If enabled, uses a per-service transport cache that is keyed off the service name and '
                        'transport settings, persists across all clients in memory, and expires after this number of '
                        'seconds. By default, a new transport is created for every new client.',
        ),
    }
    defaults = {
        'transport_cache_time_in_seconds': 0,
    }


class RedisClientSettings(ClientSettings):
    defaults = {
        'transport': {
            'path': 'pysoa.common.transport.redis_gateway.client:RedisClientTransport',
        }
    }
    schema = {
        'transport': RedisTransportSchema(),
    }


class LocalClientSettings(ClientSettings):
    defaults = {
        'transport': {
            'path': 'pysoa.common.transport.local:LocalClientTransport',
        }
    }
    schema = {
        'transport': LocalTransportSchema(),
    }


class PolymorphicClientSettings(ClientSettings):
    """
    Settings for Clients that can use any type of transport, while performing validation on certain transport types.
    """
    defaults = {
        'transport': {
            'path': 'pysoa.common.transport.redis_gateway.client:RedisClientTransport',
        }
    }
    schema = {
        'transport': fields.Polymorph(
            switch_field='path',
            contents_map={
                'pysoa.common.transport.local:LocalClientTransport': LocalTransportSchema(LocalClientTransport),
                'pysoa.common.transport:LocalClientTransport': LocalTransportSchema(LocalClientTransport),
                'pysoa.common.transport.redis_gateway.client:RedisClientTransport': RedisTransportSchema(
                    RedisClientTransport,
                ),
                '__default__': BasicClassSchema(BaseClientTransport),
            }
        ),
    }
