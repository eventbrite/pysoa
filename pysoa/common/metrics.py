from __future__ import (
    absolute_import,
    unicode_literals,
)

import warnings

from conformity import fields
from pymetrics.instruments import (  # noqa: F401
    Counter,
    Histogram,
    Timer,
    TimerResolution,
)
from pymetrics.recorders.base import MetricsRecorder  # noqa: F401
from pymetrics.recorders.noop import NonOperationalMetricsRecorder as NoOpMetricsRecorder  # noqa: F401


__all__ = ()


warnings.warn(
    '`pysoa.common.metrics.*` is deprecated. Use PyMetrics, instead. See https://github.com/eventbrite/pymetrics.',
    DeprecationWarning,
)


class MetricsSchema(fields.ClassConfigurationSchema):
    base_class = MetricsRecorder
    description = 'Configuration for defining a usage and performance metrics recorder.'
