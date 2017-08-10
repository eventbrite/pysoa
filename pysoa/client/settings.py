from __future__ import unicode_literals

from pysoa.common.settings import SOASettings


class ClientSettings(SOASettings):
    """Settings specifically for clients."""
    pass


class ASGIClientSettings(ClientSettings):
    """Standard settings class for ASGI Clients."""

    defaults = {
        'transport': {
            'path': 'pysoa.common.transport.asgi:ASGIClientTransport',
        }
    }


class LocalClientSettings(ClientSettings):
    """Standard settings for local Clients."""

    defaults = {
        'transport': {
            'path': 'pysoa.common.transport.local:LocalClientTransport',
        }
    }
