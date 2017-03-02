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
    }

    defaults = {
        "client_routing": {},
    }

    def convert_client_routing(self, value):
        return self.client_router_class(value)
