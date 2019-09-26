# coding=utf-8
from __future__ import (
    absolute_import,
    unicode_literals,
)

import ctypes
import sys
from typing import (
    Any,
    Dict,
    FrozenSet,
    Hashable,
    List,
    Tuple,
)

import six


__all__ = (
    'dict_to_hashable',
    'get_python_interpreter_arguments',
)


def dict_to_hashable(d):  # type: (Dict[Hashable, Any]) -> FrozenSet[Tuple[Hashable, ...]]
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


def get_python_interpreter_arguments():  # type: () -> List[six.text_type]
    """
    Returns a list of all the arguments passed to the Python interpreter, up to but not including the arguments
    present in `sys.argv`.

    :return: The Python interpreter arguments, such as the path to the Python binary, -m, -c, -W, etc.
    """
    argc = ctypes.c_int()
    argv = ctypes.POINTER(ctypes.c_wchar_p if sys.version_info >= (3, ) else ctypes.c_char_p)()
    ctypes.pythonapi.Py_GetArgcArgv(ctypes.byref(argc), ctypes.byref(argv))

    # Ctypes are weird. They can't be used in collection comprehensions, you can't use `in` with them, and you can't
    # use a for-each loop on them. We have to do an old-school for-i loop.
    arguments = list()
    for i in range(argc.value - len(sys.argv) + 1):
        arguments.append(six.text_type(argv[i]))

    return arguments
