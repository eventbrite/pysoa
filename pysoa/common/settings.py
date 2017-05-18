from __future__ import unicode_literals

import importlib
import itertools
import six
import copy

from conformity import fields
from conformity.validator import validate


class BasicClassSchema(fields.Dictionary):
    contents = {
        "path": fields.UnicodeString(),
        "kwargs": fields.SchemalessDictionary(key_type=fields.UnicodeString()),
    }
    optional_keys = ["kwargs"]


def resolve_python_path(path):
    """
    Turns a python path like module.name.here:ClassName.SubClass into an object
    """
    # Get the module
    module_path, local_path = path.split(":", 1)
    thing = importlib.import_module(module_path)
    # Traverse the local sections
    local_bits = local_path.split(".")
    for bit in local_bits:
        thing = getattr(thing, bit)
    return thing


class SettingsMetaclass(type):
    """
    Metaclass that gathers fields defined on settings objects into a single
    variable to access them.
    """

    def __new__(mcs, name, bases, body):
        # Don't allow multiple inheritance as it mucks up schema collecting
        if len(bases) != 1:
            raise ValueError("You cannot use multiple inheritance with Settings")
        # Make the new class
        cls = type.__new__(mcs, name, bases, body)
        # Merge the schema and defaults objects with their parents
        if bases[0] is not object:
            cls.schema = dict(itertools.chain(bases[0].schema.items(), cls.schema.items()))
            cls.defaults = dict(itertools.chain(bases[0].defaults.items(), cls.defaults.items()))
        return cls


@six.add_metaclass(SettingsMetaclass)
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
                'bar': {'quas': 3}
            }

    The class MySettings will have the defaults {'foo': 1, 'bar': {'quas': 3}}. This
    provides a measure of convenience while discouraging deep inheritance structures.

    To use Settings, instantiate the class with the raw settings value, and then
    access the items using dict syntax - e.g. settings_instance["transport"]. The class
    will merge any passed values into its defaults.

    You can override how certain fields are set by defining a method called
    `convert_fieldname`.
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
            raise ValueError("No value provided for required setting(s) %s" % unpopulated_keys)
        unconsumed_keys = set(settings.keys()) - set(self.schema.keys())
        if unconsumed_keys:
            raise ValueError("Unknown setting(s): %s" % (", ".join(unconsumed_keys)))
        for key, value in settings.items():
            # Validate the value
            validate(self.schema[key], value, "setting '%s'" % key)
            # See if it has a custom setting method
            converter = getattr(self, "convert_%s" % key, None)
            if converter:
                value = converter(value)
            self._data[key] = value

    def standard_convert_path(self, value):
        """Import the object the 'path' value in a class specifier, or raise ImproperlyConfigured."""
        if "object" not in value:
            try:
                value["object"] = resolve_python_path(value["path"])
            except ImportError:
                raise self.ImproperlyConfigured(
                    "Could not resolve path '{}' for configuration:\n{}".format(value["path"], value))
        return value

    def __getitem__(self, key):
        return self._data[key]


class SOASettings(Settings):
    """
    Settings shared between client and server.
    """
    schema = {
        # Paths to the classes to use and then kwargs to pass
        "transport": BasicClassSchema(),
        "serializer": BasicClassSchema(),
        "middleware": fields.List(BasicClassSchema()),
    }

    defaults = {
        'serializer': {'path': 'pysoa.common.serializer:MsgpackSerializer'},
        "middleware": [],
    }

    def convert_transport(self, value):
        return self.standard_convert_path(value)

    def convert_serializer(self, value):
        return self.standard_convert_path(value)

    def convert_middleware(self, value):
        return [self.standard_convert_path(item) for item in value]
