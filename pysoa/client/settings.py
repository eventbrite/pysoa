from __future__ import (
    absolute_import,
    unicode_literals,
)

import warnings

from conformity import fields

from pysoa.client.middleware import ClientMiddleware
from pysoa.common.settings import SOASettings
from pysoa.common.transport.base import ClientTransport as BaseClientTransport
from pysoa.common.transport.local import LocalClientTransport
from pysoa.common.transport.redis_gateway.client import RedisClientTransport


class ClientSettings(SOASettings):
    """
    Base settings class for all clients, whose `middleware` values are restricted to subclasses of `ClientMiddleware`
    and whose `transport` values are restricted to subclasses of `BaseClientTransport`. Middleware and transport
    configuration settings schemas will automatically switch based on the configuration settings schema for the `path`
    for each.
    """

    schema = {
        'middleware': fields.List(
            fields.ClassConfigurationSchema(base_class=ClientMiddleware),
            description='The list of all `ClientMiddleware` objects that should be applied to requests made from this '
                        'client to the associated service',
        ),
        'transport': fields.ClassConfigurationSchema(base_class=BaseClientTransport),
        'transport_cache_time_in_seconds': fields.Anything(
            description='This field is deprecated. The transport cache is no longer supported. This settings field '
                        'will remain in place until 2018-06-15 to give a safe period for people to remove it from '
                        'settings, but its value will always be ignored.',
        ),
    }
    defaults = {
        'transport': {
            'path': 'pysoa.common.transport.redis_gateway.client:RedisClientTransport',
        },
        'transport_cache_time_in_seconds': 0,
    }


ClientSettings.schema['transport'].initiate_cache_for(
    'pysoa.common.transport.redis_gateway.client:RedisClientTransport',
)
ClientSettings.schema['transport'].initiate_cache_for(
    'pysoa.common.transport.local:LocalClientTransport',
)


class RedisClientSettings(ClientSettings):
    defaults = {
        'transport': {
            'path': 'pysoa.common.transport.redis_gateway.client:RedisClientTransport',
        }
    }
    schema = {
        'transport': fields.ClassConfigurationSchema(base_class=RedisClientTransport),
    }


RedisClientSettings.schema['transport'].initiate_cache_for(
    'pysoa.common.transport.redis_gateway.client:RedisClientTransport',
)


class LocalClientSettings(ClientSettings):
    defaults = {
        'transport': {
            'path': 'pysoa.common.transport.local:LocalClientTransport',
        }
    }
    schema = {
        'transport': fields.ClassConfigurationSchema(base_class=LocalClientTransport),
    }


LocalClientSettings.schema['transport'].initiate_cache_for(
    'pysoa.common.transport.local:LocalClientTransport',
)


class PolymorphicClientSettings(ClientSettings):
    """
    DEPRECATED. Use `ClientSettings`, whose settings are polymorphic already.
    """

    def __init__(self, *args, **kwargs):
        super(PolymorphicClientSettings, self).__init__(*args, **kwargs)

        warnings.warn('PolymorphicClientSettings is deprecated; use ClientSettings instead', DeprecationWarning)
