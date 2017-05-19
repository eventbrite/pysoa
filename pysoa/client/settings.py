from __future__ import unicode_literals

from pysoa.common.settings import (
    SOASettings,
    BasicClassSchema,
)
from pysoa.common.transport.asgi.settings import ASGITransportSchema

from conformity import fields


class ClientSettings(SOASettings):
    """Settings specifically for clients."""

    schema = {
        'client': BasicClassSchema(),
        'cacheable': fields.Boolean(),
    }
    defaults = {
        'client': {'path': 'pysoa.client:Client'},
        'cacheable': False,
    }

    def convert_client(self, value):
        return self.standard_convert_path(value)


class ASGIClientSettings(ClientSettings):
    """Standard settings class for ASGI Clients."""

    schema = {
        'transport': ASGITransportSchema(),
    }
    defaults = {
        'transport': {
            'path': 'pysoa.common.transport.asgi:ASGIClientTransport',
        }
    }
