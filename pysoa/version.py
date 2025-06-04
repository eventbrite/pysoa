from __future__ import (
    absolute_import,
    unicode_literals,
)


__version_info__ = (1, 5, 0)  # Updated for Python 3.12 compatibility
__version__ = '-'.join(filter(None, ['.'.join(map(str, __version_info__[:3])), (__version_info__[3:] or [None])[0]]))
