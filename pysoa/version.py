from __future__ import (
    absolute_import,
    unicode_literals,
)


__version_info__ = (1, 0, 0, 'rc1')
__version__ = '-'.join(filter(None, ['.'.join(map(str, __version_info__[:3])), (__version_info__[3:] or [None])[0]]))
