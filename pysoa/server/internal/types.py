from __future__ import (
    absolute_import,
    unicode_literals,
)


def get_switch(item):
    if hasattr(item, '__int__'):
        return item.__int__()
    if hasattr(getattr(item, 'value', None), '__int__'):
        return item.value.__int__()
    raise TypeError('switch does not implement the switch constant interface')


def is_switch(item):
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

    def __new__(cls, switches=None):
        """
        Create a new uninitialized `SwitchSet` instance.

        :param switches: An iterable of integers or objects that implement the switch constant interface (provide
                         `__int__` or provide `value` which is an integer or provides `__int__`)
        :type switches: iterable

        :return: A new `SwitchSet`
        :rtype: SwitchSet

        :raise: TypeError
        """
        return super(SwitchSet, cls).__new__(cls, (get_switch(switch) for switch in switches or []))

    def __contains__(self, switch):
        """
        Determine whether or not a switch is in the `SwitchSet`.

        :param switch: An integer or object that implements the switch constant interface (provides `__int__` or
                       provides `value` which is an integer or provides `__int__`)
        :type: union[int, provides(__int__), provides(value)]

        :return: A boolean indicating whether the switch is active (in the set)
        :rtype: bool

        :raise: TypeError
        """
        return super(SwitchSet, self).__contains__(get_switch(switch))


class RequestSwitchSet(SwitchSet):
    def is_active(self, switch):
        """
        Determine whether or not a switch is active.

        :param switch: An integer or object that implements the switch constant interface (provides `__int__` or
                       provides `value` which is an integer or provides `__int__`)
        :type: union[int, provides(__int__), provides(value)]

        :return: A boolean indicating whether the switch is active (in the set)
        :rtype: bool

        :raise: TypeError
        """
        return switch in self
