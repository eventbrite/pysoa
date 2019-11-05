from __future__ import (
    absolute_import,
    unicode_literals,
)

from typing import (
    Any,
    Dict,
)

from conformity import fields
from conformity.fields.logging import (
    PYTHON_LOGGING_CONFIG_SCHEMA,
    PythonLogLevel,
)
from conformity.settings import (
    SettingsData,
    SettingsSchema,
)
import six

from pysoa.common.logging import SyslogHandler
from pysoa.common.settings import SOASettings
from pysoa.common.transport.base import ServerTransport as BaseServerTransport
from pysoa.server.middleware import ServerMiddleware


__all__ = (
    'ServerSettings',
)


try:
    from pysoa.server.internal.event_loop import coroutine_middleware_config
except (ImportError, SyntaxError):
    coroutine_middleware_config = None  # type: ignore


extra_schema = {}  # type: Dict[six.text_type, fields.Base]
extra_defaults = {}  # type: Dict[six.text_type, Any]
if coroutine_middleware_config:
    # TODO Python 3 we can just hard-code this
    extra_schema['coroutine_middleware'] = coroutine_middleware_config
    extra_defaults['coroutine_middleware'] = [{'path': 'pysoa.server.coroutine:DefaultCoroutineMiddleware'}]


class ServerSettings(SOASettings):
    """
    Base settings class for all servers, whose `middleware` values are restricted to subclasses of `ServerMiddleware`
    and whose `transport` values are restricted to subclasses of `BaseServerTransport`. Middleware and transport
    configuration settings schemas will automatically switch based on the configuration settings schema for the `path`
    for each.
    """

    schema = dict(
        {
            'transport': fields.ClassConfigurationSchema(base_class=BaseServerTransport),
            'middleware': fields.List(
                fields.ClassConfigurationSchema(base_class=ServerMiddleware),
                description='The list of all `ServerMiddleware` objects that should be applied to requests processed '
                            'by this server',
            ),
            'client_routing': fields.SchemalessDictionary(
                key_type=fields.UnicodeString(),
                value_type=fields.SchemalessDictionary(),
                description='Client settings for sending requests to other services; keys should be service names, and '
                            'values should be the corresponding configuration dicts, which will be validated using the '
                            'ClientSettings schema.',
            ),
            'logging': PYTHON_LOGGING_CONFIG_SCHEMA,
            'harakiri': fields.Dictionary(
                {
                    'timeout': fields.Integer(
                        gte=0,
                        description='Seconds of inactivity before harakiri is triggered; 0 to disable, defaults to 300',
                    ),
                    'shutdown_grace': fields.Integer(
                        gt=0,
                        description='Seconds to forcefully shutdown after harakiri is triggered if shutdown does not '
                                    'occur',
                    ),
                },
                description='Instructions for automatically terminating a server process when request processing takes '
                            'longer than expected.',
            ),
            'request_log_success_level': PythonLogLevel(
                description='The logging level at which full request and response contents will be logged for '
                            'successful requests',
            ),
            'request_log_error_level': PythonLogLevel(
                description='The logging level at which full request and response contents will be logged for requests '
                            'whose responses contain errors (setting this to a more severe level than '
                            '`request_log_success_level` will allow you to easily filter for unsuccessful requests)',
            ),
            'heartbeat_file': fields.Nullable(fields.UnicodeString(
                description='If specified, the server will create a heartbeat file at the specified path on startup, '
                            'update the timestamp in that file after the processing of every request or every time '
                            'idle operations are processed, and delete the file when the server shuts down. The file '
                            'name can optionally contain the specifier {{pid}}, which will be replaced with the '
                            'server process PID. Finally, the file name can optionally contain the specifier {{fid}}, '
                            'which will be replaced with the unique-and-deterministic forked process ID whenever the '
                            'server is started with the --fork option (the minimum value is always 1 and the maximum '
                            'value is always equal to the value of the --fork option).',
            )),
            'extra_fields_to_redact': fields.Set(
                fields.UnicodeString(),
                description='Use this field to supplement the set of fields that are automatically redacted/censored '
                            'in request and response fields with additional fields that your service needs redacted.',
            ),
        },
        **extra_schema
    )  # type: SettingsSchema

    defaults = dict(
        {
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
            'transport': {
                'path': 'pysoa.common.transport.redis_gateway.server:RedisServerTransport',
            }
        },
        **extra_defaults
    )  # type: SettingsData
