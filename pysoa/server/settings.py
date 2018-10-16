from __future__ import (
    absolute_import,
    unicode_literals,
)

import functools

from conformity import fields

from pysoa.common.logging import SyslogHandler
from pysoa.common.schemas import (
    BasicClassSchema,
    PolymorphClassSchema,
)
from pysoa.common.settings import SOASettings
from pysoa.common.transport.base import ServerTransport as BaseServerTransport
from pysoa.common.transport.local import LocalServerTransportSchema
from pysoa.common.transport.redis_gateway.settings import RedisTransportSchema
from pysoa.server.middleware import ServerMiddleware


_logger_schema = fields.Dictionary(
    {
        'level': fields.UnicodeString(),
        'propagate': fields.Boolean(),
        'filters': fields.List(fields.UnicodeString()),
        'handlers': fields.List(fields.UnicodeString()),
    },
    optional_keys=('level', 'propagate', 'filters', 'handlers'),
)

log_level_schema = functools.partial(fields.Constant, 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')


class ServerSettings(SOASettings):
    """
    Settings specific to servers
    """

    schema = {
        'transport': BasicClassSchema(BaseServerTransport),
        'middleware': fields.List(
            BasicClassSchema(ServerMiddleware),
            description='The list of all `ServerMiddleware` objects that should be applied to requests processed by '
                        'this server',
        ),
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
            description='Instructions for automatically terminating a server process when request processing takes '
                        'longer than expected.',
        ),
        'request_log_success_level': log_level_schema(
            description='The logging level at which full request and response contents will be logged for successful '
                        'requests',
        ),
        'request_log_error_level': log_level_schema(
            description='The logging level at which full request and response contents will be logged for requests '
                        'whose responses contain errors (setting this to a more severe level than '
                        '`request_log_success_level` will allow you to easily filter for unsuccessful requests)',
        ),
        'heartbeat_file': fields.Nullable(fields.UnicodeString(
            description='If specified, the server will create a heartbeat file at the specified path on startup, '
                        'update the timestamp in that file after the processing of every request or every time '
                        'idle operations are processed, and delete the file when the server shuts down. The file name '
                        'can optionally contain the specifier {{pid}}, which will be replaced with the server process '
                        'PID.',
        )),
        'extra_fields_to_redact': fields.Set(
            fields.UnicodeString(),
            description='Use this field to supplement the set of fields that are automatically redacted/censored in '
                        'request and response fields with additional fields that your service needs redacted.',
        ),
    }

    defaults = {
        'client_routing': {},
        'logging': {
            'version': 1,
            'formatters': {
                'console': {
                    'format': '%(asctime)s %(levelname)7s %(correlation_id)s %(request_id)s: %(message)s'
                },
                'syslog': {
                    'format': (
                        '%(service_name)s_service: %(name)s %(levelname)s %(module)s %(process)d '
                        'correlation_id %(correlation_id)s request_id %(request_id)s %(message)s'
                    ),
                },
            },
            'filters': {
                'pysoa_logging_context_filter': {
                    '()': 'pysoa.common.logging.PySOALogContextFilter',
                },
            },
            'handlers': {
                'console': {
                    'level': 'INFO',
                    'class': 'logging.StreamHandler',
                    'formatter': 'console',
                    'filters': ['pysoa_logging_context_filter'],
                },
                'syslog': {
                    'level': 'INFO',
                    'class': 'pysoa.common.logging.SyslogHandler',
                    'facility': SyslogHandler.LOG_LOCAL7,
                    'address': ('localhost', 514),
                    'formatter': 'syslog',
                    'filters': ['pysoa_logging_context_filter'],
                },
            },
            'loggers': {},
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
        'heartbeat_file': None,
        'extra_fields_to_redact': set(),
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
        'transport': LocalServerTransportSchema(),
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
        'transport': PolymorphClassSchema(
            contents_map={
                '__default__': BasicClassSchema(BaseServerTransport),
            },
            enforce_object_type_subclass_of=BaseServerTransport,
        ),
    }
