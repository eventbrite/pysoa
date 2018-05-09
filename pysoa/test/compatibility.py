from __future__ import absolute_import

try:
    import mock  # noqa
    # First we try to import the Python 2 backport library of Mock, because if the project is using it, we should use it
except ImportError as e:
    try:
        from unittest import mock  # noqa
        # Next we try to import the built-in unittest.mock, which is only available on Python 3
    except ImportError:
        # We can get here only on Python 2, only if Mock isn't installed, so we raise the original import error for Mock
        raise e


__all__ = (
    'mock'
)
