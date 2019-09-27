from __future__ import (
    absolute_import,
    unicode_literals,
)

from typing import (
    Any,
    Iterable,
    Optional,
    SupportsInt,
    Type,
    TypeVar,
    Union,
)


try:
    from typing import Protocol
    try:
        # Py3.8, Py2.7 backport
        from typing import runtime_checkable
    except ImportError:
        # Some Py3.7
        from typing import runtime as runtime_checkable  # type: ignore
except ImportError:
    # Some Py3.7, all Py3<3.7
    from typing_extensions import (  # type: ignore
        Protocol,
        runtime_checkable,
    )


__all__ = (
    'get_switch',
    'is_switch',
    'RequestSwitchSet',
    'SupportsIntValue',
    'SwitchSet',
)


@runtime_checkable
class SupportsIntValue(Protocol):
    value = 0  # type: SupportsInt


def get_switch(item):  # type: (Union[SupportsInt, SupportsIntValue]) -> int
    if hasattr(item, '__int__'):
        return item.__int__()  # type: ignore
    if hasattr(getattr(item, 'value', None), '__int__'):
        return item.value.__int__()  # type: ignore
    raise TypeError('switch does not implement the switch constant interface')


def is_switch(item):  # type: (Any) -> bool
    try:
        get_switch(item)
        return True
    except TypeError:
        return False


class SwitchSet(frozenset):
    """
    Immutable set subtype for interacting with switches, which might be integers or might be int-like objects that
    provide integers in some way.
    """

    def __new__(
        cls,  # type: Type[_S]
        switches=None,  # type: Optional[Iterable[Union[SupportsInt, SupportsIntValue]]]
    ):  # type: (...) -> _S
        """
        Create a new uninitialized `SwitchSet` instance.

        :param switches: An iterable of integers or objects that implement the switch constant interface (provide
                         `__int__` or provide `value` which is an integer or provides `__int__`)

        :return: A new `SwitchSet`
        """
        return super(SwitchSet, cls).__new__(cls, (get_switch(switch) for switch in switches or []))  # type: ignore

    def __contains__(self, switch):  # type: (Any) -> bool
        """
        Determine whether or not a switch is in the `SwitchSet`.

        :param switch: An integer or object that implements the switch constant interface (provides `__int__` or
                       provides `value` which is an integer or provides `__int__`)

        :return: A boolean indicating whether the switch is active (in the set)
        """
        return super(SwitchSet, self).__contains__(get_switch(switch))  # type: ignore


_S = TypeVar('_S', bound=SwitchSet)


class RequestSwitchSet(SwitchSet):
    def is_active(self, switch):  # type: (Union[SupportsInt, SupportsIntValue]) -> bool
        """
        Determine whether or not a switch is active.

        :param switch: An integer or object that implements the switch constant interface (provides `__int__` or
                       provides `value` which is an integer or provides `__int__`)

        :return: A boolean indicating whether the switch is active (in the set)
        """
        return switch in self
