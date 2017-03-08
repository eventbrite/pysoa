import importlib
import six
from conformity import fields
from conformity.validator import validate


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
            cls.schema = dict(bases[0].schema.items() + cls.schema.items())
            cls.defaults = dict(bases[0].defaults.items() + cls.defaults.items())
        return cls


@six.add_metaclass(SettingsMetaclass)
class Settings(object):
    """
    Represents settings that can be passed to either a Client or a Server, and
    then trickle down into lower levels, passed explicitly each time (no globals)

    The base classes are designed to be inherited from and have their schema
    extended, first into a Client and Server variant, and then into
    implementation-specific variants to match subclasses of Client and Server.

    To use Settings, instantiate the class with the raw settings value, and then
    access the items using dict syntax - e.g. settings_instance["transport"]

    You can override how certain fields are set by defining a method called
    `convert_fieldname`.
    """

    schema = {}
    defaults = {}

    def __init__(self, data):
        self._data = {}
        self.set(data)

    def set(self, data):
        """
        Sets the value of this settings object in its entirety.
        """
        for key, value in data.items():
            if key in self.schema:
                # Validate the value
                validate(self.schema[key], value, "setting '%s'" % key)
                # See if it has a custom setting method
                converter = getattr(self, "convert_%s" % key, None)
                if converter:
                    value = converter(value)
                self._data[key] = value
        # Make sure all values were populated
        unpopulated_keys = set(self.schema.keys()) - set(data.keys())
        for key in unpopulated_keys:
            if key in self.defaults:
                self._data[key] = self.defaults[key]
            else:
                raise ValueError("No value was provided for required setting %s" % key)
        # See if any keys were not consumed
        unconsumed_keys = set(data.keys()) - set(self.schema.keys())
        if unconsumed_keys:
            raise ValueError("Unknown setting(s): %s" % (", ".join(unconsumed_keys)))

    def __getitem__(self, key):
        return self._data[key]


class SOASettings(Settings):
    """
    Settings shared between client and server.
    """
    schema = {
        # Paths to the classes to use and then kwargs to pass
        "transport": fields.Dictionary(
            {
                "path": fields.UnicodeString(),
                "kwargs": fields.SchemalessDictionary(key_type=fields.UnicodeString()),
            },
            optional_keys="kwargs",
        ),
        "serializer": fields.Dictionary(
            {
                "path": fields.UnicodeString(),
                "kwargs": fields.SchemalessDictionary(key_type=fields.UnicodeString()),
            },
            optional_keys="kwargs",
        ),

        # Middleware is a list of ("path.to.class", {"setting_name": ...}) tuples
        # The same format is applied for both server and client, though the middleware
        # classes they use are different
        "middleware": fields.List(
            fields.Tuple(
                fields.UnicodeString(),
                fields.SchemalessDictionary(key_type=fields.UnicodeString()),
            ),
        ),
    }

    defaults = {
        "middleware": [],
    }

    def resolve_python_path(self, path):
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

    def convert_transport(self, value):
        value["object"] = self.resolve_python_path(value["path"])
        return value

    def convert_serializer(self, value):
        value["object"] = self.resolve_python_path(value["path"])
        return value

    def convert_middleware(self, value):
        return [
            (self.resolve_python_path(path), kwargs)
            for path, kwargs in value
        ]
