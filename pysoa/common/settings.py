from __future__ import (
    absolute_import,
    unicode_literals,
)

import copy
import itertools

from conformity import fields
from conformity.error import ValidationError
from conformity.validator import validate
import six

from pysoa.common.metrics import MetricsSchema


class _SettingsMetaclass(type):
    """
    Metaclass that gathers fields defined on settings objects into a single
    variable to access them.
    """

    def __new__(mcs, name, bases, body):
        # Don't allow multiple inheritance as it mucks up schema collecting
        if len(bases) != 1:
            raise TypeError('You cannot use multiple inheritance with Settings')
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
    """

    schema = {}
    defaults = {}

    class ImproperlyConfigured(Exception):
        """Raised when a configuration validation fails."""
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
            raise self.ImproperlyConfigured(
                'No value provided for required setting(s): {}'.format(', '.join(unpopulated_keys))
            )
        unconsumed_keys = set(settings.keys()) - set(self.schema.keys())
        if unconsumed_keys:
            raise self.ImproperlyConfigured('Unknown setting(s): {}'.format(', '.join(unconsumed_keys)))
        for key, value in settings.items():
            # Validate the value
            try:
                validate(self.schema[key], value, "setting '{}'".format(key))
            except ValidationError as e:
                raise self.ImproperlyConfigured(*e.args)
            self._data[key] = value

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
        'transport': fields.ClassConfigurationSchema(),
        'middleware': fields.List(
            fields.ClassConfigurationSchema(),
            description='The list of all middleware objects that should be applied to this server or client',
        ),
        'metrics': MetricsSchema(),
    }

    defaults = {
        'middleware': [],
        'metrics': {'path': 'pysoa.common.metrics:NoOpMetricsRecorder'},
    }
