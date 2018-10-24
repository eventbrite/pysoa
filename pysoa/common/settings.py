from __future__ import (
    absolute_import,
    unicode_literals,
)

import copy
import itertools

from conformity import fields
from conformity.validator import validate
import six

from pysoa.common.metrics import MetricsSchema
from pysoa.common.schemas import BasicClassSchema
from pysoa.utils import resolve_python_path


class _SettingsMetaclass(type):
    """
    Metaclass that gathers fields defined on settings objects into a single
    variable to access them.
    """

    def __new__(mcs, name, bases, body):
        # Don't allow multiple inheritance as it mucks up schema collecting
        if len(bases) != 1:
            raise ValueError('You cannot use multiple inheritance with Settings')
        # Make the new class
        cls = super(_SettingsMetaclass, mcs).__new__(mcs, name, bases, body)
        # Merge the schema and defaults objects with their parents
        if bases[0] is not object:
            cls.schema = dict(itertools.chain(bases[0].schema.items(), cls.schema.items()))
            cls.defaults = dict(itertools.chain(bases[0].defaults.items(), cls.defaults.items()))
        return cls


@six.add_metaclass(_SettingsMetaclass)
class Settings(object):
    """
    Represents settings that can be passed to either a Client or a Server, and
    then trickle down into lower levels, passed explicitly each time (no globals)

    The base classes are designed to be inherited from and have their schema
    extended, first into a Client and Server variant, and then into
    implementation-specific variants to match subclasses of Client and Server.

    Subclasses may define defaults as a dictionary. Defaults defined on a subclass
    will be merged with the defaults of its parent, but only to a depth of 1. For
    example:

        class BaseSettings(Settings):
            defaults = {
                'foo': 1,
                'bar': {'baz': 2},
            }

        class MySettings(BaseSettings):
            defaults = {
                'bar': {'baz': 3}
            }

    The class MySettings will have the defaults {'foo': 1, 'bar': {'baz': 3}}. This
    provides a measure of convenience while discouraging deep inheritance structures.

    To use Settings, instantiate the class with the raw settings value, and then
    access the items using dict syntax - e.g. settings_instance['transport']. The class
    will merge any passed values into its defaults.

    You can override how certain fields are set by defining a method called
    `convert_{field_name}`.
    """

    schema = {}
    defaults = {}

    class ImproperlyConfigured(Exception):
        """Raised when a configuration value cannot be resolved."""
        pass

    def __init__(self, data):
        self._data = {}
        self.set(data)

    def _merge_dicts(self, data, defaults):
        for key, value in data.items():
            if key in defaults and isinstance(value, dict) and isinstance(defaults[key], dict):
                self._merge_dicts(value, defaults[key])
            else:
                defaults[key] = value

    def set(self, data):
        """
        Sets the value of this settings object in its entirety.
        """
        settings = copy.deepcopy(self.defaults)
        data = copy.deepcopy(data)
        self._merge_dicts(data, settings)
        # Make sure all values were populated
        unpopulated_keys = set(self.schema.keys()) - set(settings.keys())
        if unpopulated_keys:
            raise ValueError('No value provided for required setting(s): {}'.format(', '.join(unpopulated_keys)))
        unconsumed_keys = set(settings.keys()) - set(self.schema.keys())
        if unconsumed_keys:
            raise ValueError('Unknown setting(s): {}'.format(', '.join(unconsumed_keys)))
        for key, value in settings.items():
            # Validate the value
            validate(self.schema[key], value, "setting '{}'".format(key))
            self._data[key] = value

        self._convert_class_schemas(self, self._data, self.schema)

    @staticmethod
    def _convert_class_schemas(root, settings, schema=None):
        """
        Converts all top-level settings with defined converters and converts all `BasicClassSchema` types recursively,
        with optional type checking for settings values defined with `BasicClassSchema`s.

        :param root: The `Settings` object (only pass to topmost call, recursive calls pass None)
        :param settings: The settings dict
        :param schema: The discovered schema for this settings dict
        """
        for key, value in settings.items():
            class_schema_value = schema_value = None
            if schema:
                schema_value = schema.get(key)
                if isinstance(schema_value, BasicClassSchema):
                    class_schema_value = schema_value
                    Settings.standard_convert_path(value, class_schema_value)
                elif (
                    isinstance(schema_value, fields.List) and
                    isinstance(schema_value.contents, BasicClassSchema)
                ):
                    class_schema_value = schema_value.contents
                    for item in value:
                        Settings.standard_convert_path(item, class_schema_value)
                elif isinstance(schema_value, fields.Polymorph):
                    _schema_value = (
                        schema_value.contents_map.get(value[schema_value.switch_field]) or
                        schema_value.contents_map.get('__default__')
                    )
                    if isinstance(_schema_value, BasicClassSchema):
                        class_schema_value = _schema_value
                        Settings.standard_convert_path(value, class_schema_value)

            _converter = getattr(root, 'convert_%s' % key, None)
            if _converter:
                value = _converter(value)
                settings[key] = value

            if isinstance(value, dict):
                if class_schema_value:
                    Settings._convert_class_schemas(None, value, class_schema_value.contents)
                elif isinstance(schema_value, fields.Dictionary):
                    Settings._convert_class_schemas(None, value, schema_value.contents)
                else:
                    Settings._convert_class_schemas(None, value)

    @staticmethod
    def standard_convert_path(value, class_schema_value):
        """
        Imports the object for the 'path' value in a class specifier, or raises ImproperlyConfigured if not found. If a
        `BasicClassSchema` value is supplied and it has an `object_type`, checks that the imported object equals or
        is a subclass of that `object_type`.

        :param value: The value dict to convert
        :param class_schema_value: The `BasicClassSchema` instance that matches this value, if any
        """
        if 'object' not in value:
            try:
                value['object'] = resolve_python_path(value['path'])
            except (ImportError, AttributeError):
                raise Settings.ImproperlyConfigured(
                    "Could not resolve path '{path}' for configuration:\n{config}".format(
                        path=value['path'],
                        config=value,
                    )
                )

        if class_schema_value.object_type and not issubclass(value['object'], class_schema_value.object_type):
            # If the schema includes type information, the resolved path should equal or be a subclass of that type
            raise Settings.ImproperlyConfigured(
                "Path '{path}' should be of type '{object_type}' for configuration:\n{config}".format(
                    path=value['path'],
                    object_type=class_schema_value.object_type,
                    config=value,
                )
            )

    def __getitem__(self, key):
        return self._data[key]

    def __contains__(self, key):
        return key in self._data


class SOASettings(Settings):
    """
    Settings shared between client and server.
    """
    schema = {
        # Paths to the classes to use and then kwargs to pass
        'transport': BasicClassSchema(),
        'middleware': fields.List(
            BasicClassSchema(),
            description='The list of all middleware objects that should be applied to this server or client',
        ),
        'metrics': MetricsSchema(),
    }

    defaults = {
        'middleware': [],
        'metrics': {'path': 'pysoa.common.metrics:NoOpMetricsRecorder'},
    }
