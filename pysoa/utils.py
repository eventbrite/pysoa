# coding=utf-8
from __future__ import (
    absolute_import,
    unicode_literals,
)

import six


__all__ = (
    'dict_to_hashable',
)


def dict_to_hashable(d):
    """
    Takes a dict and returns an immutable, hashable version of that dict that can be used as a key in dicts or as a
    set value. Any two dicts passed in with the same content are guaranteed to return the same value. Any two dicts
    passed in with different content are guaranteed to return different values. Performs comparatively to `repr`.

    >> %timeit repr(d1)
    The slowest run took 5.76 times longer than the fastest. This could mean that an intermediate result is being cached
    100000 loops, best of 3: 3.48 µs per loop

    >> %timeit dict_to_hashable(d1)
    The slowest run took 4.16 times longer than the fastest. This could mean that an intermediate result is being cached
    100000 loops, best of 3: 4.07 µs per loop

    :param d: The dict
    :return: The hashable representation of the dict
    """
    return frozenset(
        (k, tuple(v) if isinstance(v, list) else (dict_to_hashable(v) if isinstance(v, dict) else v))
        for k, v in six.iteritems(d)
    )
