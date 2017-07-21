from __future__ import unicode_literals

import pytest

from pysoa.common.settings import (
    Settings,
    SOASettings,
)
from pysoa.common.transport.asgi import ASGIClientTransport
from pysoa.common.serializer import MsgpackSerializer
from pysoa.client.middleware import ClientMiddleware

from conformity import fields


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


class TestSettings:
    """Tests for settings class inheritance and initialization behavior."""

    def test_top_level_schema_keys_required(self):
        """All keys in the top level of the schema are required."""
        with pytest.raises(ValueError):
            settings = SettingsWithSimpleSchema({})

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


class TestSOASettings:
    """Tests for the SOASettings class."""

    def test_classes_converted(self):
        """The settings class resolves classes of transport, serializer and middleware."""

        settings_dict = {
            'transport': {
                'path': 'pysoa.common.transport.asgi:ASGIClientTransport',
            },
            'serializer': {
                'path': 'pysoa.common.serializer:MsgpackSerializer',
            },
            'middleware': [
                {
                    'path': 'pysoa.client.middleware:ClientMiddleware',
                },
            ],
        }
        settings = SOASettings(settings_dict)
        assert settings['transport']['object'] == ASGIClientTransport
        assert settings['serializer']['object'] == MsgpackSerializer
        assert settings['middleware'][0]['object'] == ClientMiddleware
