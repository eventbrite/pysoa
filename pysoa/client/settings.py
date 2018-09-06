from __future__ import (
    absolute_import,
    unicode_literals,
)

from conformity import fields

from pysoa.client.middleware import ClientMiddleware
from pysoa.common.schemas import (
    BasicClassSchema,
    PolymorphClassSchema,
)
from pysoa.common.settings import SOASettings
from pysoa.common.transport.base import ClientTransport as BaseClientTransport
from pysoa.common.transport.local import LocalClientTransportSchema
from pysoa.common.transport.redis_gateway.settings import RedisTransportSchema


class ClientSettings(SOASettings):
    """Generic settings for a Client."""
    schema = {
        'middleware': fields.List(
            BasicClassSchema(ClientMiddleware),
            description='The list of all `ClientMiddleware` objects that should be applied to requests made from this '
                        'client to the associated service',
        ),
        'transport': BasicClassSchema(BaseClientTransport),
        'transport_cache_time_in_seconds': fields.Anything(
            description='This field is deprecated. The transport cache is no longer supported. This settings field '
                        'will remain in place until 2018-06-15 to give a safe period for people to remove it from '
                        'settings, but its value will always be ignored.',
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
        'transport': LocalClientTransportSchema(),
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
        'transport': PolymorphClassSchema(
            contents_map={
                '__default__': BasicClassSchema(BaseClientTransport),
            },
            enforce_object_type_subclass_of=BaseClientTransport,
        ),
    }
