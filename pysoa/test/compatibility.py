from __future__ import absolute_import

try:
    from unittest import mock  # noqa
    # On this end, we won't require consumers to have mock 3rd-party library installed in Python 3
except ImportError:
    import mock  # noqa
    # On this other end, we can still support Python 2


__all__ = (
    'mock'
)
