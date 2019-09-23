from __future__ import (
    absolute_import,
    unicode_literals,
)

import abc
from typing import (  # noqa: F401 TODO Python 3
    Any,
    Callable,
    Dict,
    Iterable,
    Optional,
    SupportsInt,
    Type,
    Union,
)

import attr
import six  # noqa: F401 TODO Python 3

from pysoa.client.client import Client  # noqa: F401 TODO Python 3
from pysoa.common.constants import (
    ERROR_CODE_SERVER_ERROR,
    ERROR_CODE_UNKNOWN,
)
from pysoa.common.types import (
    ActionRequest,
    ActionResponse,
    Error,
)
from pysoa.server.errors import ActionError
from pysoa.server.internal.types import (  # noqa: F401 TODO Python 3
    RequestSwitchSet,
    SupportsIntValue,
)
from pysoa.server.settings import ServerSettings


try:
    import pysoa.server.coroutine
    # noinspection PyCompatibility
    import concurrent.futures

    RunCoroutineType = Callable[[pysoa.server.coroutine.Coroutine], concurrent.futures.Future]
except (ImportError, SyntaxError):
    RunCoroutineType = None  # type: ignore


def _convert_request_switch_set(value):
    # type: (Union[RequestSwitchSet, Iterable[Union[SupportsInt, SupportsIntValue]]]) -> RequestSwitchSet
    if isinstance(value, RequestSwitchSet):
        return value
    return RequestSwitchSet(value)


@attr.s
class EnrichedActionRequest(ActionRequest):
    """
    The action request object that the Server passes to each Action class that it calls. It contains all the information
    from ActionRequest, plus some extra information from the JobRequest, a client that can be used to call other
    services, and a helper for running asyncio coroutines.

    Also contains a helper for easily calling other local service actions from within an action.

    Services and intermediate libraries can subclass this class and change the `Server` attribute `request_class` to
    their subclass in order to use more-advanced request classes. In order for any new attributes such a subclass
    provides to be copied by `call_local_action`, they must be `attr.ib` attributes with a default value.
    """
    switches = attr.ib(
        default=attr.Factory(RequestSwitchSet),
        converter=_convert_request_switch_set,
    )  # type: RequestSwitchSet
    context = attr.ib(default=attr.Factory(dict))  # type: Dict[six.text_type, Any]
    control = attr.ib(default=attr.Factory(dict))  # type: Dict[six.text_type, Any]
    client = attr.ib(default=None)  # type: Client
    run_coroutine = attr.ib(default=None)  # type: RunCoroutineType

    _server = None

    def call_local_action(self, action, body, raise_action_errors=True):
        # type: (six.text_type, Dict[six.text_type, Any], bool) -> ActionResponse
        """
        This helper calls another action, locally, that resides on the same service, using the provided action name
        and body. The called action will receive a copy of this request object with different action and body details.

        The use of this helper differs significantly from using the PySOA client to call an action. Notably:

        * The configured transport is not involved, so no socket activity or serialization/deserialization takes place.
        * PySOA server metrics are not recorded and post-action cleanup activities do not occur.
        * No "job request" is ever created or transacted.
        * No middleware is executed around this action (though, in the future, we might change this decision and add
          middleware execution to this helper).

        :param action: The action to call (must exist within the `action_class_map` from the `Server` class)
        :type action: union[str, unicode]
        :param body: The body to send to the action
        :type body: dict
        :param raise_action_errors: If `True` (the default), all action errors will be raised; otherwise, an
                                    `ActionResponse` containing the errors will be returned.
        :type raise_action_errors: bool

        :return: the action response.
        :rtype: ActionResponse

        :raises: ActionError
        """
        server = getattr(self, '_server', None)
        if not server:
            errors = [Error(
                code=ERROR_CODE_SERVER_ERROR,
                message="No `_server` attribute set on action request object (and can't make request without it)",
            )]
            if raise_action_errors:
                raise ActionError(errors)
            return ActionResponse(action=action, errors=errors)

        if action not in server.action_class_map:
            errors = [Error(
                code=ERROR_CODE_UNKNOWN,
                message='The action "{}" was not found on this server.'.format(action),
                field='action',
            )]
            if raise_action_errors:
                raise ActionError(errors)
            return ActionResponse(action=action, errors=errors)

        action_type = server.action_class_map[action]  # type: ActionType
        action_callable = action_type(server.settings)

        request = self.__class__(
            action=action,
            body=body,
            # Dynamically copy all Attrs attributes so that subclasses introducing other Attrs can still work properly
            **{
                a.name: getattr(self, a.name)
                for a in getattr(self, '__attrs_attrs__')
                if a.name not in ('action', 'body')
            }
        )
        request._server = server

        try:
            response = action_callable(request)
        except ActionError as e:
            if raise_action_errors:
                raise
            return ActionResponse(action=action, errors=e.errors)

        if raise_action_errors and response.errors:
            raise ActionError(response.errors)

        return response


@six.add_metaclass(abc.ABCMeta)
class ActionInterface(object):
    """
    Actions should either be callables that accept a ServerSettings object and return another callable that accepts an
    EnrichedActionRequest and returns an ActionResponse, or they should inherit from this class and implement its
    abstract methods. Most actions, however, will simply extend `pysoa.server.action.base.Action` and implement its
    interface, which is simpler and easier to use.
    """

    # noinspection PyUnusedLocal
    @abc.abstractmethod
    def __init__(self, settings=None):  # type: (Optional[ServerSettings]) -> None
        """
        Constructs a new action class.

        :param settings: The Server settings
        """

    @abc.abstractmethod
    def __call__(self, action_request):  # type: (EnrichedActionRequest) -> ActionResponse
        """
        Execute the action.

        :param action_request: The action request

        :return: The action response
        """


ActionType = Union[
    Type[ActionInterface],
    Callable[[Optional[ServerSettings]], Callable[[EnrichedActionRequest], ActionResponse]],
]
