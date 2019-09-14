from __future__ import (
    absolute_import,
    unicode_literals,
)

import sys

from pysoa.version import (
    __version__,
    __version_info__,
)


__all__ = (
    '__version__',
    '__version_info__',
)


if (3, 5) <= sys.version_info < (3, 7):
    # We have some typing patches that we might need to apply in Python 3.5 and 3.6. We won't need to apply them in
    # 2.7 because the `typing` backport in PyPi already has the fixes, and we won't need to apply them in 3.7 because
    # that version has the fixes.
    # noinspection PyUnresolvedReferences
    import pysoa.typing_patches  # noqa: F401
