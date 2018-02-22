from __future__ import unicode_literals

from conformity import fields

from pysoa.common.settings import (
    BasicClassSchema,
    SOASettings,
)
from pysoa.common.transport.base import ServerTransport as BaseServerTransport
from pysoa.common.transport.local import (
    LocalServerTransport,
    LocalTransportSchema,
)
from pysoa.common.transport.redis_gateway.server import RedisServerTransport
from pysoa.common.transport.redis_gateway.settings import RedisTransportSchema
from pysoa.server.middleware import ServerMiddleware


_logger_schema = fields.Dictionary(
    {
        'level': fields.UnicodeString(),
        'propagate': fields.Any(fields.Boolean(), fields.UnicodeString()),  # TODO change to just Boolean() > 2018-03-01
        'filters': fields.List(fields.UnicodeString()),
        'handlers': fields.List(fields.UnicodeString()),
    },
    optional_keys=('level', 'propagate', 'filters', 'handlers'),
)

log_level_schema = fields.Constant('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')


class ServerSettings(SOASettings):
    """
    Settings specific to servers
    """

    schema = {
        'transport': BasicClassSchema(BaseServerTransport),
        'middleware': fields.List(BasicClassSchema(ServerMiddleware)),
        'client_routing': fields.SchemalessDictionary(
            key_type=fields.UnicodeString(),
            value_type=fields.SchemalessDictionary(),
            description='Client settings for sending requests to other services; keys should be service names, and '
                        'values should be the corresponding configuration dicts, which will be validated using the '
                        'PolymorphicClientSettings schema',
        ),
        'logging': fields.Dictionary(
            {
                'version': fields.Integer(gte=1, lte=1),
                'formatters': fields.SchemalessDictionary(
                    key_type=fields.UnicodeString(),
                    value_type=fields.Dictionary(
                        {
                            'format': fields.UnicodeString(),
                            'datefmt': fields.UnicodeString(),
                        },
                        optional_keys=('datefmt', ),
                    ),
                ),
                'filters': fields.SchemalessDictionary(
                    key_type=fields.UnicodeString(),
                    value_type=fields.Dictionary(
                        {
                            '()': fields.Anything(description='The optional filter class'),
                            'name': fields.UnicodeString(description='The optional filter name'),
                        },
                        optional_keys=('()', 'name'),
                    ),
                ),
                'handlers': fields.SchemalessDictionary(
                    key_type=fields.UnicodeString(),
                    value_type=fields.Dictionary(
                        {
                            'class': fields.UnicodeString(),
                            'level': fields.UnicodeString(),
                            'formatter': fields.UnicodeString(),
                            'filters': fields.List(fields.UnicodeString()),
                        },
                        optional_keys=('level', 'formatter', 'filters'),
                        allow_extra_keys=True,
                    ),
                ),
                'loggers': fields.SchemalessDictionary(
                    key_type=fields.UnicodeString(),
                    value_type=_logger_schema,
                ),
                'root': _logger_schema,
                'incremental': fields.Boolean(),
                'disable_existing_loggers': fields.Boolean(),
            },
            optional_keys=(
                'version',
                'formatters',
                'filters',
                'handlers',
                'root',
                'loggers',
                'incremental',
            ),
            description='Settings for service logging, which should follow the standard Python logging configuration',
        ),
        'harakiri': fields.Dictionary(
            {
                'timeout': fields.Integer(
                    gte=0,
                    description='Seconds of inactivity before harakiri is triggered; 0 to disable, defaults to 300',
                ),
                'shutdown_grace': fields.Integer(
                    gt=0,
                    description='Seconds to forcefully shutdown after harakiri is triggered if shutdown does not occur',
                ),
            },
        ),
        'request_log_success_level': log_level_schema,
        'request_log_error_level': log_level_schema,
    }

    defaults = {
        'client_routing': {},
        'logging': {
            'version': 1,
            'formatters': {
                'console': {
                    'format': '%(asctime)s %(levelname)7s %(correlation_id)s %(request_id)s: %(message)s'
                },
            },
            'filters': {
                'pysoa_logging_context_filter': {
                    '()': 'pysoa.server.logging.PySOALogContextFilter',
                }
            },
            'handlers': {
                'console': {
                    'level': 'INFO',
                    'class': 'logging.StreamHandler',
                    'formatter': 'console',
                    'filters': ['pysoa_logging_context_filter'],
                },
            },
            'root': {
                'handlers': ['console'],
                'level': 'INFO',
            },
            'disable_existing_loggers': False,
        },
        'harakiri': {
            'timeout': 300,
            'shutdown_grace': 30,
        },
        'request_log_success_level': 'INFO',
        'request_log_error_level': 'INFO',
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
            'path': 'pysoa.common.transport.redis_gateway.server:RedisServerTransport',
        }
    }
    schema = {
        'transport': fields.Polymorph(
            switch_field='path',
            contents_map={
                'pysoa.common.transport.local:LocalServerTransport': LocalTransportSchema(LocalServerTransport),
                'pysoa.common.transport:LocalServerTransport': LocalTransportSchema(LocalServerTransport),
                'pysoa.common.transport.redis_gateway.server:RedisServerTransport': RedisTransportSchema(
                    RedisServerTransport,
                ),
                '__default__': BasicClassSchema(BaseServerTransport),
            }
        ),
    }
