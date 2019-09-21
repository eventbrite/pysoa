from __future__ import (
    absolute_import,
    unicode_literals,
)

import unittest

from conformity.settings import Settings
import pytest

from pysoa.client.client import Client
from pysoa.client.middleware import ClientMiddleware
from pysoa.client.settings import ClientSettings
from pysoa.common.serializer import (
    JSONSerializer,
    MsgpackSerializer,
)
from pysoa.common.settings import SOASettings
from pysoa.common.transport.redis_gateway.client import RedisClientTransport
from pysoa.common.transport.redis_gateway.constants import REDIS_BACKEND_TYPE_STANDARD
from pysoa.common.transport.redis_gateway.core import RedisTransportCore
from pysoa.common.transport.redis_gateway.server import RedisServerTransport
from pysoa.server.server import Server
from pysoa.server.settings import ServerSettings


class TestSOASettings(unittest.TestCase):
    """Tests for the SOASettings class."""

    def test_classes_converted(self):
        """The settings class resolves classes of transport and middleware."""

        settings_dict = {
            'transport': {
                'path': 'pysoa.common.transport.redis_gateway.client:RedisClientTransport',
                'kwargs': {
                    'backend_type': REDIS_BACKEND_TYPE_STANDARD,
                },
            },
            'middleware': [
                {
                    'path': 'pysoa.client.middleware:ClientMiddleware',
                },
            ],
        }
        settings = SOASettings(settings_dict)
        assert settings['transport']['object'] == RedisClientTransport
        assert settings['middleware'][0]['object'] == ClientMiddleware

    # noinspection PyProtectedMember
    def test_client_settings(self):
        """The client is successfully instantiated with settings, Redis Transport"""

        settings_dict = {
            'test_service': {
                'transport': {
                    'path': 'pysoa.common.transport.redis_gateway.client:RedisClientTransport',
                    'kwargs': {
                        'backend_type': REDIS_BACKEND_TYPE_STANDARD,
                        'default_serializer_config': {
                            'path': 'pysoa.common.serializer:JSONSerializer'
                        }
                    }
                },
            },
        }

        client = Client(settings_dict)
        handler = client._get_handler('test_service')

        assert isinstance(handler.transport, RedisClientTransport)
        assert handler.transport._send_queue_name == 'service.test_service'
        assert isinstance(handler.transport.core, RedisTransportCore)
        assert handler.transport.core.backend_type == REDIS_BACKEND_TYPE_STANDARD
        assert isinstance(handler.transport.core.default_serializer, JSONSerializer)

    # noinspection PyProtectedMember
    def test_server_settings(self):
        """The server is successfully instantiated with settings, Redis Transport"""

        class _TestServer(Server):
            service_name = 'geo_tag'

        settings_dict = {
            'transport': {
                'path': 'pysoa.common.transport.redis_gateway.server:RedisServerTransport',
                'kwargs': {
                    'backend_type': REDIS_BACKEND_TYPE_STANDARD,
                    'default_serializer_config': {
                        'path': 'pysoa.common.serializer:JSONSerializer'
                    }
                }
            },
        }

        server = _TestServer(ServerSettings(settings_dict))

        assert isinstance(server.transport, RedisServerTransport)
        assert server.transport._receive_queue_name == 'service.geo_tag'
        assert isinstance(server.transport.core, RedisTransportCore)
        assert server.transport.core.backend_type == REDIS_BACKEND_TYPE_STANDARD
        assert isinstance(server.transport.core.default_serializer, JSONSerializer)

    # noinspection PyProtectedMember
    def test_server_settings_generic_with_defaults(self):
        """The server is successfully instantiated with generic settings, Redis Transport"""

        class _TestServer(Server):
            service_name = 'tag_geo'

        settings_dict = {
            'transport': {
                'path': 'pysoa.common.transport.redis_gateway.server:RedisServerTransport',
                'kwargs': {
                    'backend_type': REDIS_BACKEND_TYPE_STANDARD,
                }
            },
        }

        server = _TestServer(ServerSettings(settings_dict))

        assert isinstance(server.transport, RedisServerTransport)
        assert server.transport._receive_queue_name == 'service.tag_geo'
        assert isinstance(server.transport.core, RedisTransportCore)
        assert server.transport.core.backend_type == REDIS_BACKEND_TYPE_STANDARD
        assert isinstance(server.transport.core.default_serializer, MsgpackSerializer)

    def test_server_settings_fails_with_client_transport(self):
        """The server settings fail to validate with client transport"""

        settings_dict = {
            'transport': {
                'path': 'pysoa.common.transport.redis_gateway.client:RedisClientTransport',
                'kwargs': {
                    'backend_type': REDIS_BACKEND_TYPE_STANDARD,
                }
            },
        }

        with pytest.raises(Settings.ImproperlyConfigured) as error_context:
            ServerSettings(settings_dict)

        assert 'is not one of or a subclass of one of' in error_context.value.args[0]

    def test_client_settings_fails_with_server_transport(self):
        """The client settings fail to validate with server transport"""

        settings_dict = {
            'transport': {
                'path': 'pysoa.common.transport.redis_gateway.server:RedisServerTransport',
                'kwargs': {
                    'backend_type': REDIS_BACKEND_TYPE_STANDARD,
                }
            },
        }

        with pytest.raises(Settings.ImproperlyConfigured) as error_context:
            ClientSettings(settings_dict)

        assert 'is not one of or a subclass of one of' in error_context.value.args[0]
        assert 'RedisServerTransport' in error_context.value.args[0]

    def test_client_settings_fails_with_invalid_path(self):
        """The client settings fail to validate with non-existent transport"""

        settings_dict = {
            'transport': {
                'path': 'pysoa.common.transport.redis_gateway.server:NonExistentTransport',
                'kwargs': {
                    'backend_type': REDIS_BACKEND_TYPE_STANDARD,
                }
            },
        }

        with pytest.raises(Settings.ImproperlyConfigured) as error_context:
            ClientSettings(settings_dict)

        assert 'has no attribute' in error_context.value.args[0]
        assert 'NonExistentTransport' in error_context.value.args[0]

    def test_server_settings_fails_with_invalid_serializer(self):
        """The server settings fail to validate with server middleware as serializer"""

        settings_dict = {
            'transport': {
                'path': 'pysoa.common.transport.redis_gateway.server:RedisServerTransport',
                'kwargs': {
                    'backend_type': REDIS_BACKEND_TYPE_STANDARD,
                    'default_serializer_config': {
                        'path': 'pysoa.server.middleware:ServerMiddleware',
                    }
                },
            },
        }

        with pytest.raises(Settings.ImproperlyConfigured) as error_context:
            ServerSettings(settings_dict)

        assert 'is not one of or a subclass of one of' in error_context.value.args[0]
        assert 'ServerMiddleware' in error_context.value.args[0]

    def test_server_settings_fails_with_client_middleware(self):
        """The server settings fail to validate with client middleware"""

        settings_dict = {
            'transport': {
                'path': 'pysoa.common.transport.redis_gateway.server:RedisServerTransport',
                'kwargs': {
                    'backend_type': REDIS_BACKEND_TYPE_STANDARD,
                },
            },
            'middleware': [
                {'path': 'pysoa.client.middleware:ClientMiddleware'}
            ],
        }

        with pytest.raises(Settings.ImproperlyConfigured) as error_context:
            ServerSettings(settings_dict)

        assert 'is not one of or a subclass of one of' in error_context.value.args[0]
        assert 'ClientMiddleware' in error_context.value.args[0]

        settings_dict['middleware'][0]['path'] = 'pysoa.server.middleware:ServerMiddleware'  # type: ignore

        ServerSettings(settings_dict)

    def test_client_settings_fails_with_server_middleware(self):
        """The client settings fail to validate with server middleware"""

        settings_dict = {
            'transport': {
                'path': 'pysoa.common.transport.redis_gateway.client:RedisClientTransport',
                'kwargs': {
                    'backend_type': REDIS_BACKEND_TYPE_STANDARD,
                }
            },
            'middleware': [
                {'path': 'pysoa.server.middleware:ServerMiddleware'}
            ],
        }

        with pytest.raises(Settings.ImproperlyConfigured) as error_context:
            ClientSettings(settings_dict)

        assert 'is not one of or a subclass of one of' in error_context.value.args[0]
        assert 'ServerMiddleware' in error_context.value.args[0]

        settings_dict['middleware'][0]['path'] = 'pysoa.client.middleware:ClientMiddleware'  # type: ignore

        ClientSettings(settings_dict)
