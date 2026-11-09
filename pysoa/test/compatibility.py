from __future__ import (
    absolute_import,
    unicode_literals,
)


try:
    from unittest import mock  # type: ignore # noqa
    # On Python 3, prefer the standard-library mock. The standalone backport
    # uses a different DEFAULT sentinel, so a stub_action appended to a
    # unittest.mock.patch patchings list would not have its argument injected.
except ImportError as e:
    try:
        import mock
        # Python 2 only: use the backport library of Mock.
    except ImportError:
        # We can get here only on Python 2, only if Mock isn't installed, so we raise the original import error for Mock
        raise e


__all__ = (
    'mock'
)
