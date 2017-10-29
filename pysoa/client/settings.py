from __future__ import unicode_literals

from conformity import fields

from pysoa.client.middleware import ClientMiddleware
from pysoa.common.settings import (
    BasicClassSchema,
    SOASettings,
)
from pysoa.common.transport.asgi.client import ASGIClientTransport
from pysoa.common.transport.asgi.settings import ASGITransportSchema
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
        'transport': BasicClassSchema(BaseClientTransport),
        'middleware': fields.List(BasicClassSchema(ClientMiddleware))
    }


class ASGIClientSettings(ClientSettings):
    """Settings for an ASGI-only Client."""
    defaults = {
        'transport': {
            'path': 'pysoa.common.transport.asgi:ASGIClientTransport',
        }
    }
    schema = {
        'transport': ASGITransportSchema(),
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
            'path': 'pysoa.common.transport.asgi:ASGIClientTransport',
        }
    }
    schema = {
        'transport': fields.Polymorph(
            switch_field='path',
            contents_map={
                'pysoa.common.transport.asgi:ASGIClientTransport': ASGITransportSchema(ASGIClientTransport),
                'pysoa.common.transport:ASGIClientTransport': ASGITransportSchema(ASGIClientTransport),
                'pysoa.common.transport.local:LocalClientTransport': LocalTransportSchema(LocalClientTransport),
                'pysoa.common.transport:LocalClientTransport': LocalTransportSchema(LocalClientTransport),
                'pysoa.common.transport.redis_gateway.client:RedisClientTransport': RedisTransportSchema(
                    RedisClientTransport,
                ),
                '__default__': BasicClassSchema(BaseClientTransport),
            }
        ),
    }
