from __future__ import (
    absolute_import,
    unicode_literals,
)

from unittest import TestCase


try:
    import mock
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


if not hasattr(TestCase, 'assertRegex'):
    # In Python 2.7, make sure we have the new method name from Python 3.3+
    TestCase.assertRegex = TestCase.assertRegexpMatches
if not hasattr(TestCase, 'assertNotRegex'):
    # In Python 2.7, make sure we have the new method name from Python 3.3+
    TestCase.assertNotRegex = TestCase.assertNotRegexpMatches
