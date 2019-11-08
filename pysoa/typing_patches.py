"""isort:skip_file"""
import collections
import sys
import typing


if (3, 5) <= sys.version_info < (3, 5, 3):
    CT_co = typing.TypeVar('CT_co', covariant=True, bound=type)

    # noinspection PyCompatibility
    class PatchedType(typing.Generic[CT_co], extra=type):  # type: ignore # noqa: E999
        """
        Python 3.5.0-3.5.2 contain a bug whereby Type is defined as follows:

        Type(type, Generic[CT_co], extra=type):
            < docs, no methods or anything else >

        This was reported in https://github.com/python/typing/issues/266 and fixed in
        https://github.com/python/typing/pull/267/files, but some Python in the wild is still 3.5.2 or less, so this
        patch backports that fix to 3.5.0-3.5.2.
        """

    typing.Type = PatchedType  # type: ignore


if (3, 5) <= sys.version_info < (3, 5, 4) or (3, 6) <= sys.version_info < (3, 6, 1):
    T = typing.TypeVar('T')

    # noinspection PyCompatibility
    class Deque(collections.deque, typing.MutableSequence[T], extra=collections.deque):  # type: ignore # noqa: E999
        """
        Python 3.5.4 and 3.6.1 added typing.Deque, but some Python in the wild is still 3.5.3 or less or 3.6.0, so this
        patch backports Deque to 3.5.0-3.5.3 and 3.6.0. This code was copied from
        https://github.com/python/cpython/blob/v3.5.4/Lib/typing.py#L1901-L1908 and
        https://github.com/python/cpython/blob/v3.6.1/Lib/typing.py#L1871-L1878.
        """

        __slots__ = ()

        # noinspection PyProtectedMember,PyUnresolvedReferences,PyArgumentList
        def __new__(cls, *args, **kwargs):
            if typing._geqv(cls, Deque):  # type: ignore
                return collections.deque(*args, **kwargs)
            return collections.deque.__new__(cls, *args, **kwargs)  # type: ignore

    typing.Deque = Deque
