from __future__ import (
    absolute_import,
    unicode_literals,
)

import unittest

from conformity import fields
import pytest

from pysoa.client.client import Client
from pysoa.client.middleware import ClientMiddleware
from pysoa.client.settings import ClientSettings
from pysoa.common.serializer import (
    JSONSerializer,
    MsgpackSerializer,
)
from pysoa.common.settings import (
    Settings,
    SOASettings,
)
from pysoa.common.transport.redis_gateway.client import RedisClientTransport
from pysoa.common.transport.redis_gateway.constants import REDIS_BACKEND_TYPE_STANDARD
from pysoa.common.transport.redis_gateway.core import RedisTransportCore
from pysoa.common.transport.redis_gateway.server import RedisServerTransport
from pysoa.server.server import Server
from pysoa.server.settings import (
    PolymorphicServerSettings,
    ServerSettings,
)


class SettingsWithSimpleSchema(Settings):
    schema = {
        'required_property': fields.Integer(),
        'property_with_default': fields.Integer(),
    }

    defaults = {
        'property_with_default': 0,
    }


class SettingsWithDefaults(Settings):
    schema = {
        'complex_property': fields.Dictionary({
            'string_property': fields.UnicodeString(),
            'int_property': fields.Integer(),
            'kwargs': fields.Dictionary({
                'foo': fields.Integer(),
                'bar': fields.UnicodeString(),
            }),
        }),
        'simple_property': fields.Integer(),
    }

    defaults = {
        'simple_property': 0,
        'complex_property': {
            'string_property': 'default_string',
            'kwargs': {
                'foo': 1,
            },
        },
    }


class TestSettings(object):
    """Tests for settings class inheritance and initialization behavior."""

    def test_top_level_schema_keys_required(self):
        """All keys in the top level of the schema are required."""
        with pytest.raises(ValueError):
            SettingsWithSimpleSchema({})

        settings = SettingsWithSimpleSchema({
            'required_property': 0,
        })
        assert settings['required_property'] == 0

    def test_extra_top_level_key_fail(self):
        """Any keys not in the top level of the schema cause validation to fail."""
        with pytest.raises(ValueError):
            SettingsWithSimpleSchema({
                'other_property': 'foo',
            })

    def test_incorrect_nested_value_fails(self):
        """Values with incorrect types cause validation to fail."""
        with pytest.raises(ValueError):
            SettingsWithDefaults({})

        with pytest.raises(ValueError):
            SettingsWithDefaults({
                'complex_property': {'kwargs': {'foo': 'asdf'}},
            })

    def test_data_fields_merge_with_defaults(self):
        """Passed data is merged with the class defaults."""
        settings = SettingsWithDefaults({
            'simple_property': 1,
            'complex_property': {
                'int_property': 2,
                'kwargs': {
                    'bar': 'four',
                },
            },
        })
        assert settings['simple_property'] == 1
        assert settings['complex_property']['string_property'] == 'default_string'
        assert settings['complex_property']['kwargs']['foo'] == 1
        assert settings['complex_property']['kwargs']['bar'] == 'four'

    def test_top_level_defaults_inherited(self):
        """Defaults at the top level of the defaults dict are inherited."""
        class MySettings(SettingsWithSimpleSchema):
            defaults = {
                'required_property': 1,
            }

        assert MySettings.defaults['property_with_default'] == 0
        assert MySettings({})['required_property'] == 1

    def test_top_level_schema_inherited(self):
        """Schema items at the top level of the schema dict are inherited."""
        class MySettings(SettingsWithSimpleSchema):
            schema = {
                'another_property': fields.Integer(),
            }

        assert MySettings.schema['another_property']
        with pytest.raises(ValueError):
            MySettings({'required_property': 1})
        assert MySettings({
            'required_property': 1,
            'another_property': 2,
        })['another_property'] == 2

    def test_nested_defaults_not_inherited(self):
        """Defaults nested deeper than the top level of the default dict are not inherited."""
        class MySettings(SettingsWithDefaults):
            defaults = {
                'complex_property': {
                    'int_property': 0,
                }
            }
        with pytest.raises(ValueError):
            # If nested defaults were inherited, only kwargs would be required
            MySettings({
                'complex_property': {
                    'kwargs': {
                        'foo': 1,
                        'bar': 'four',
                    },
                },
            })

    def test_nested_schema_not_inherited(self):
        """Schema items deeper than the top level of the schema dict are not inherited."""
        class MySettings(SettingsWithDefaults):
            schema = {
                'complex_property': fields.Dictionary({
                    'another_property': fields.Integer(),
                }),
            }

        with pytest.raises(ValueError):
            # If nested schema items were inherited, keys from the parent class would
            # not cause validation to fail.
            MySettings({
                'simple_property': 1,
                'complex_property': {
                    'int_property': 2,
                    'kwargs': {
                        'bar': 'four',
                    },
                    'another_property': 1,
                },
            })

        with pytest.raises(ValueError):
            # This happens because the inherited defaults no longer match the new schema.
            MySettings({
                'simple_property': 1,
                'complex_property': {
                    'another_property': 1,
                }
            })

        # If we override the defaults to match the schema, it works
        class MyCorrectSetting(MySettings):
            defaults = {
                'complex_property': {
                    'another_property': 1,
                },
            }

        settings = MyCorrectSetting({})
        assert settings['complex_property']['another_property'] == 1
        assert settings['simple_property'] == 0


class TestSOASettings(unittest.TestCase):
    """Tests for the SOASettings class."""

    def test_classes_converted(self):
        """The settings class resolves classes of transport and middleware."""

        settings_dict = {
            'transport': {
                'path': 'pysoa.common.transport.redis_gateway.client:RedisClientTransport',
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
                        'serializer_config': {
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
        assert isinstance(handler.transport.core.serializer, JSONSerializer)

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
                    'serializer_config': {
                        'path': 'pysoa.common.serializer:JSONSerializer'
                    }
                }
            },
        }

        server = _TestServer(PolymorphicServerSettings(settings_dict))

        assert isinstance(server.transport, RedisServerTransport)
        assert server.transport._receive_queue_name == 'service.geo_tag'
        assert isinstance(server.transport.core, RedisTransportCore)
        assert server.transport.core.backend_type == REDIS_BACKEND_TYPE_STANDARD
        assert isinstance(server.transport.core.serializer, JSONSerializer)

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
        assert isinstance(server.transport.core.serializer, MsgpackSerializer)

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

        with self.assertRaises(Settings.ImproperlyConfigured) as error_context:
            ServerSettings(settings_dict)

        self.assertTrue('should be of type' in error_context.exception.args[0])

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

        with self.assertRaises(Settings.ImproperlyConfigured) as error_context:
            ClientSettings(settings_dict)

        self.assertTrue('should be of type' in error_context.exception.args[0])

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

        with self.assertRaises(Settings.ImproperlyConfigured) as error_context:
            ClientSettings(settings_dict)

        self.assertTrue('Could not resolve path' in error_context.exception.args[0])

    def test_server_settings_fails_with_invalid_serializer(self):
        """The server settings fail to validate with server middleware as serializer"""

        settings_dict = {
            'transport': {
                'path': 'pysoa.common.transport.redis_gateway.server:RedisServerTransport',
                'kwargs': {
                    'backend_type': REDIS_BACKEND_TYPE_STANDARD,
                    'serializer_config': {
                        'path': 'pysoa.server.middleware:ServerMiddleware',
                    }
                },
            },
        }

        with self.assertRaises(Settings.ImproperlyConfigured) as error_context:
            PolymorphicServerSettings(settings_dict)

        self.assertTrue('should be of type' in error_context.exception.args[0])

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

        with self.assertRaises(Settings.ImproperlyConfigured) as error_context:
            PolymorphicServerSettings(settings_dict)

        self.assertTrue('should be of type' in error_context.exception.args[0])

        settings_dict['middleware'][0]['path'] = 'pysoa.server.middleware:ServerMiddleware'

        PolymorphicServerSettings(settings_dict)

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

        with self.assertRaises(Settings.ImproperlyConfigured) as error_context:
            ClientSettings(settings_dict)

        self.assertTrue('should be of type' in error_context.exception.args[0])

        settings_dict['middleware'][0]['path'] = 'pysoa.client.middleware:ClientMiddleware'

        ClientSettings(settings_dict)
