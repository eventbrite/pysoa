from __future__ import (
    absolute_import,
    unicode_literals,
)

import abc

import six

from pysoa.server.internal.types import is_switch


__all__ = (
    'SwitchedAction',
)


def _len(item):
    # Safe length that won't raise an error on values that don't support length
    return getattr(item, '__len__', lambda *_: -1)()


class _DefaultAction(object):
    def __int__(self):
        d = id(self)
        return d if d < 0 else -d

    def __eq__(self, other):
        return getattr(other, '__class__', None) == _DefaultAction


class _SwitchedActionMetaClass(abc.ABCMeta):
    def __new__(mcs, name, bases, body):
        """
        Validate the switch_to_action_map when the class is created, instead of doing it every time the class
        is instantiated. This identifies problems earlier (on import) and improves performance by not performing this
        validation every time the action is called.
        """
        cls = super(_SwitchedActionMetaClass, mcs).__new__(mcs, name, bases, body)

        # noinspection PyUnresolvedReferences
        if bases[0] is not object and (
            not cls.switch_to_action_map or
            not hasattr(cls.switch_to_action_map, '__iter__') or
            _len(cls.switch_to_action_map) < 2 or
            any(
                True for i in cls.switch_to_action_map
                if not hasattr(i, '__getitem__') or _len(i) != 2 or not is_switch(i[0]) or not callable(i[1])
            )
        ):
            raise ValueError(
                'Class attribute switch_to_action_map must be an iterable of at least two indexable items, each '
                'with exactly two indexes, where the first element is a switch and the second element is an action '
                '(callable).'
            )

        return cls


@six.add_metaclass(_SwitchedActionMetaClass)
class SwitchedAction(object):
    """
    A specialized action that defers to other, concrete actions based on request switches. Subclasses must not
    override any methods and must override `switch_to_action_map`. `switch_to_action_map` should be some iterable
    object that provides `__len__` (such as a tuple [recommended] or list). Its items must be indexable objects that
    provide `__len__` (such as a tuple [recommended] or list) and have exactly two elements.

    For each item in `switch_to_action_map`, the first element must be a switch that provides `__int__` (such as an
    actual integer) or a switch that provides an attribute `value` which, itself, provides `__int__` (or is an int).
    The second element must be an action, such as an action class (e.g. one that extends `Action`) or any callable
    that accepts a server settings object and returns a new callable that, itself, accepts an `ActionRequest` object
    and returns an `ActionResponse` object or raises an `ActionError`.

    `switch_to_action_map` must have at least two items in it. `SwitchedAction` will iterate over that list, checking
    the first element (switch) of each item to see if it is enabled in the request. If it is, the second element (the
    action) of that item will be deferred to. If it finds no items whose switches are enabled, it will use the very
    last action in `switch_to_action_map`. As such, you can treat the last item as a default, and its switch could
    simply be `SwitchedAction.DEFAULT_ACTION` (although, this is not required: it could also be a valid switch, and
    it would still be treated as the default in the case that no other items matched).

    Example usage:

    .. code-block:: python

        class UserActionV1(Action):
            ...

        class UserActionV2(Action):
            ...

        class UserTransitionAction(SwitchedAction):
            switch_to_action_map = (
                (USER_VERSION_2_ENABLED, UserActionV2),
                (SwitchedAction.DEFAULT_ACTION, UserActionV1),
            )
    """

    DEFAULT_ACTION = _DefaultAction()

    switch_to_action_map = ()

    def __init__(self, settings=None):
        """
        Construct a new action. Concrete classes should not override this.

        :param settings: The server settings object
        :type settings: dict
        """
        if self.__class__ is SwitchedAction:
            raise TypeError('Cannot instantiate abstract SwitchedAction')

        self.settings = settings

    def get_uninitialized_action(self, action_request):
        """
        Get the raw action (such as the action class or the base action callable) without instantiating/calling
        it, based on the switches in the action request, or the default raw action if no switches were present or
        no switches matched.

        :param action_request: The request object
        :type action_request: EnrichedActionRequest

        :return: The action
        :rtype: callable
        """
        last_action = None
        matched_action = None
        default_action = None

        for switch, action in self.switch_to_action_map:
            if switch == self.DEFAULT_ACTION:
                default_action = action
            elif switch and action_request.switches.is_active(switch):
                matched_action = action
                break
            else:
                last_action = action

        return matched_action or default_action or last_action

    def __call__(self, action_request):
        """
        Main entry point for actions from the `Server` (or potentially from tests). Finds the appropriate real action
        to invoke based on the switches enabled in the request, initializes the action with the server settings, and
        then calls the action with the request object, returning its response directly.

        :param action_request: The request object
        :type action_request: EnrichedActionRequest

        :return: The response object
        :rtype: ActionResponse

        :raise: ActionError, ResponseValidationError
        """
        return self.get_uninitialized_action(action_request)(self.settings)(action_request)
