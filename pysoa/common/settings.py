from __future__ import (
    absolute_import,
    unicode_literals,
)

import warnings

from conformity import fields
from conformity.settings import (  # noqa: F401 TODO Python 3
    Settings as ConformitySettings,
    SettingsData,
    SettingsSchema,
)

from pysoa.common.metrics import MetricsSchema


class Settings(ConformitySettings):
    """
    Deprecated. Use `conformity.settings.Settings`, instead.
    """
    def __init__(self, data):
        warnings.warn(
            'pysoa.common.settings.Settings is deprecated. Use conformity.settings.ConformitySettings, instead.',
            DeprecationWarning,
        )
        super(Settings, self).__init__(data)


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
        'metrics': MetricsSchema(),
    }  # type: SettingsSchema

    defaults = {
        'middleware': [],
        'metrics': {'path': 'pysoa.common.metrics:NoOpMetricsRecorder'},
    }  # type: SettingsData
