from conformity import fields
from pysoa.common.settings import SOASettings
from pysoa.client.router import ClientRouter


class ServerSettings(SOASettings):
    """
    Settings specific to servers
    """

    client_router_class = ClientRouter

    schema = {
        "client_routing": fields.SchemalessDictionary(),
        "logging": fields.SchemalessDictionary(),
    }

    defaults = {
        "client_routing": {},
        "logging": {
            "version": 1,
            "formatters": {
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
        }
    }

    def convert_client_routing(self, value):
        return self.client_router_class(value)
