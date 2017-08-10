from conformity import fields
from pysoa.common.settings import SOASettings


class ServerSettings(SOASettings):
    """
    Settings specific to servers
    """

    schema = {
        'client_routing': fields.SchemalessDictionary(),
        'logging': fields.SchemalessDictionary(),
        'harakiri': fields.Dictionary({
            'timeout': fields.Integer(gte=0),  # seconds of inactivity before harakiri is triggered, 0 to disable
            'shutdown_grace': fields.Integer(gte=0),   # seconds to gracefuly shutdown after hararki is triggered
        }),
    }

    defaults = {
        'client_routing': {},
        'logging': {
            'version': 1,
            'formatters': {
                'console': {
                    'format': ('%(asctime)s %(levelname)7s: %(message)s')
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
