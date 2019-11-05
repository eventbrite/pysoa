from __future__ import (
    absolute_import,
    unicode_literals,
)

from conformity import fields
from conformity.settings import (
    SettingsData,
    SettingsSchema,
)

from pysoa.client.middleware import ClientMiddleware
from pysoa.common.settings import SOASettings
from pysoa.common.transport.base import ClientTransport as BaseClientTransport


__all__ = (
    'ClientSettings',
)


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
    }  # type: SettingsSchema

    defaults = {
        'transport': {
            'path': 'pysoa.common.transport.redis_gateway.client:RedisClientTransport',
        },
    }  # type: SettingsData
