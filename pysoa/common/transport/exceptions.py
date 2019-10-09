from __future__ import (
    absolute_import,
    unicode_literals,
)

import warnings

from pysoa.common.transport.errors import (  # noqa: F401
    ConnectionError,
    InvalidMessageError,
    MessageReceiveError,
    MessageReceiveTimeout,
    MessageSendError,
    MessageSendTimeout,
    MessageTooLarge,
)


warnings.warn(
    '`pysoa.common.transport.exceptions` is deprecated. Import from `pysoa.common.transport.errors`, instead.',
    DeprecationWarning,
)
