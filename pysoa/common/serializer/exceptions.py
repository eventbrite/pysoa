from __future__ import (
    absolute_import,
    unicode_literals,
)

import warnings

from pysoa.common.serializer.errors import (  # noqa: F401
    InvalidField,
    InvalidMessage,
)


warnings.warn(
    '`pysoa.common.serializer.exceptions` is deprecated. Import from `pysoa.common.serializer.errors`, instead.',
    DeprecationWarning,
)
