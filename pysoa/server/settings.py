from __future__ import unicode_literals

from conformity import fields

from pysoa.common.settings import (
    BasicClassSchema,
    SOASettings,
)
from pysoa.common.transport.asgi.server import ASGIServerTransport
from pysoa.common.transport.asgi.settings import ASGITransportSchema
from pysoa.common.transport.base import ServerTransport as BaseServerTransport
from pysoa.common.transport.local import (
    LocalServerTransport,
    LocalTransportSchema,
)
from pysoa.common.transport.redis_gateway.server import RedisServerTransport
from pysoa.common.transport.redis_gateway.settings import RedisTransportSchema
from pysoa.server.middleware import ServerMiddleware


class ServerSettings(SOASettings):
    """
    Settings specific to servers
    """

    schema = {
        'transport': BasicClassSchema(BaseServerTransport),
        'middleware': fields.List(BasicClassSchema(ServerMiddleware)),
        'client_routing': fields.SchemalessDictionary(),
        'logging': fields.SchemalessDictionary(),
        'harakiri': fields.Dictionary({
            'timeout': fields.Integer(gte=0),  # seconds of inactivity before harakiri is triggered, 0 to disable
            'shutdown_grace': fields.Integer(gte=0),   # seconds to gracefully shutdown after harakiri is triggered
        }),
    }

    defaults = {
        'client_routing': {},
        'logging': {
            'version': 1,
            'formatters': {
                'console': {
                    'format': '%(asctime)s %(levelname)7s: %(message)s'
                },
            },
            'handlers': {
                'console': {
                    'level': 'INFO',
                    'class': 'logging.StreamHandler',
                    'formatter': 'console',
                },
            },
            'root': {
                'handlers': ['console'],
                'level': 'INFO',
            },
        },
        'harakiri': {
            'timeout': 300,
            'shutdown_grace': 30,
        },
    }


class ASGIServerSettings(ServerSettings):
    """Settings for an ASGI-only Server."""
    defaults = {
        'transport': {
            'path': 'pysoa.common.transport.asgi:ASGIServerTransport',
        }
    }
    schema = {
        'transport': ASGITransportSchema(),
    }


class RedisServerSettings(ServerSettings):
    defaults = {
        'transport': {
            'path': 'pysoa.common.transport.redis_gateway.server:RedisServerTransport',
        }
    }
    schema = {
        'transport': RedisTransportSchema(),
    }


class LocalServerSettings(ServerSettings):
    defaults = {
        'transport': {
            'path': 'pysoa.common.transport.local:LocalServerTransport',
        }
    }
    schema = {
        'transport': LocalTransportSchema(),
    }


class PolymorphicServerSettings(ServerSettings):
    """
    Settings for Servers that can use any type of transport, while performing validation on certain transport types.
    """
    defaults = {
        'transport': {
            'path': 'pysoa.common.transport.asgi:ASGIServerTransport',
        }
    }
    schema = {
        'transport': fields.Polymorph(
            switch_field='path',
            contents_map={
                'pysoa.common.transport.asgi:ASGIServerTransport': ASGITransportSchema(ASGIServerTransport),
                'pysoa.common.transport:ASGIServerTransport': ASGITransportSchema(ASGIServerTransport),
                'pysoa.common.transport.local:LocalServerTransport': LocalTransportSchema(LocalServerTransport),
                'pysoa.common.transport:LocalServerTransport': LocalTransportSchema(LocalServerTransport),
                'pysoa.common.transport.redis_gateway.server:RedisServerTransport': RedisTransportSchema(
                    RedisServerTransport,
                ),
                '__default__': BasicClassSchema(BaseServerTransport),
            }
        ),
    }
