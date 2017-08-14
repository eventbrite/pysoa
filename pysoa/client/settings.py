from __future__ import unicode_literals

from pysoa.common.settings import SOASettings
from pysoa.common.transport.asgi.settings import ASGITransportSchema
from pysoa.common.transport.local import LocalTransportSchema
from pysoa.common.settings import BasicClassSchema

from conformity import fields


class ClientSettings(SOASettings):
    """Generic settings for a Client."""


class ASGIClientSettings(ClientSettings):
    """Settings for an ASGI-only Client."""
    defaults = {
        'transport': {
            'path': 'pysoa.common.transport.asgi:ASGIClientTransport',
        }
    }
    schema = {
        'transport': ASGITransportSchema(),
    }


class LocalClientSettings(ClientSettings):
    defaults = {
        'transport': {
            'path': 'pysoa.common.transport.local:LocalClientTransport',
        }
    }
    schema = {
        'transport': LocalTransportSchema(),
    }


class PolymorphicClientSettings(ClientSettings):
    """Settings for Clients that can use any type of transport, while performing validation on certain transport types."""
    defaults = {
        'transport': {
            'path': 'pysoa.common.transport.asgi:ASGIClientTransport',
        }
    }
    schema = {
        'transport': fields.Polymorph(
            switch_field='path',
            contents_map={
                'pysoa.common.transport.asgi:ASGIClientTransport': ASGITransportSchema(),
                'pysoa.common.transport:ASGIClientTransport': ASGITransportSchema(),
                'pysoa.common.transport.local:LocalClientTransport': LocalTransportSchema(),
                'pysoa.common.transport:LocalClientTransport': LocalTransportSchema(),
                '__default__': BasicClassSchema(),
            }
        ),
    }
