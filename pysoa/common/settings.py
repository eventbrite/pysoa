from __future__ import (
    absolute_import,
    unicode_literals,
)

from conformity import fields
from conformity.settings import (
    Settings as ConformitySettings,
    SettingsData,
    SettingsSchema,
)
from pymetrics.recorders.base import MetricsRecorder


__all__ = (
    'SOASettings',
)


class SOASettings(ConformitySettings):
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
        'metrics': fields.ClassConfigurationSchema(
            base_class=MetricsRecorder,
            description='Configuration for defining a usage and performance metrics recorder.',
        ),
    }  # type: SettingsSchema

    defaults = {
        'middleware': [],
        'metrics': {'path': 'pymetrics.recorders.noop:NonOperationalMetricsRecorder'},
    }  # type: SettingsData
