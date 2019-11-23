from __future__ import (
    absolute_import,
    unicode_literals,
)

from collections import (
    OrderedDict,
    defaultdict,
)
from functools import wraps
import re
import sys
from types import TracebackType
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
)

from conformity import fields
from conformity.settings import SettingsData
from pymetrics.recorders.base import MetricsRecorder
from pymetrics.recorders.noop import noop_metrics
import six
from typing_extensions import Literal

from pysoa.client.client import (
    Client,
    ServiceHandler,
)
from pysoa.client.settings import ClientSettings
from pysoa.common.errors import Error
from pysoa.common.transport.errors import (
    MessageReceiveError,
    MessageReceiveTimeout,
)
from pysoa.common.transport.local import LocalClientTransport
from pysoa.common.types import (
    ActionRequest,
    ActionResponse,
    Body,
    JobResponse,
)
from pysoa.server.action import Action
from pysoa.server.errors import (
    ActionError,
    JobError,
)
from pysoa.server.server import Server
from pysoa.server.types import (
    ActionType,
    EnrichedActionRequest,
)
from pysoa.test.compatibility import mock


__all__ = (
    'Errors',
    'stub_action',
    'StubClient',
    'StubClientSettings',
    'StubClientTransport',
    'StubClientTransportSchema',
    'StubServer',
)


Errors = Union[Iterable[Mapping[six.text_type, Any]], Iterable[Error]]


class _StubAction(Action):
    """An Action that simply returns a preset value or error."""

    body = {}  # type: Body
    errors = []  # type: Errors

    def run(self, request):
        if self.errors:
            raise ActionError(errors=[e if isinstance(e, Error) else Error(**e) for e in self.errors])
        return self.body

    def __call__(self, action_request):  # type: (EnrichedActionRequest) -> ActionResponse
        response_body = self.run(action_request)

        if response_body is not None:
            return ActionResponse(action=action_request.action, body=response_body)
        else:
            return ActionResponse(action=action_request.action)


def _make_stub_action(
    action_name,  # type: six.text_type
    body=None,  # type: Optional[Body]
    errors=None,  # type: Errors
):  # type: (...) -> Type[_StubAction]
    body = body or {}
    errors = errors or []
    action_class_name = ''.join([part.capitalize() for part in re.split(r'[^a-zA-Z0-9]+', action_name)])
    return cast(Type[_StubAction], type(
        str(action_class_name),
        (_StubAction,),
        dict(body=body, errors=errors),
    ))


class StubClientSettings(ClientSettings):
    defaults = {
        'transport': {
            'path': 'pysoa.test.stub_service:StubClientTransport',
        },
    }  # type: SettingsData


class StubClient(Client):
    """
    A Client for testing code that calls service actions.

    Uses StubClientTransport, which incorporates a server for handling requests. Uses the real Server
    code path, so that developers needing to test their code against particular service responses can
    test against a genuine service in a unit testing environment.
    """

    settings_class = StubClientSettings

    def __init__(self, service_action_map=None, **_):
        # type: (Optional[Mapping[six.text_type, Mapping[six.text_type, Mapping[six.text_type, Any]]]], **Any) -> None
        """
        Generate settings based on a mapping of service names to actions.

        :param service_action_map: Dictionary of `{service_name: {action_name: {'body': ..., 'errors': ...}}}`
        """
        service_action_map = service_action_map or {}
        config = {}
        for service_name, action_map in service_action_map.items():
            config[service_name] = {
                'transport': {
                    'kwargs': {
                        'action_map': action_map,
                    },
                },
            }
        super(StubClient, self).__init__(config)

    def stub_action(self, service_name, action, body=None, errors=None):
        # type: (six.text_type, six.text_type, Optional[Body], Optional[Errors]) -> None
        """
        Stub the given action for the given service, configuring a handler and transport for that service if necessary.

        :param service_name: The service name
        :param action: The action name
        :param body: The optional body to return
        :param errors: The optional errors to raise
        """
        if service_name not in self.handlers:
            self.handlers[service_name] = ServiceHandler(service_name, self.settings_class({}))
        cast(StubClientTransport, self.handlers[service_name].transport).stub_action(action, body=body, errors=errors)


class StubClientTransportSchema(fields.Dictionary):
    contents = {
        'action_map': fields.SchemalessDictionary(
            key_type=fields.UnicodeString(
                description='The name of the action to stub',
            ),
            value_type=fields.Dictionary(
                {
                    'body': fields.SchemalessDictionary(
                        description='The body with which the action should respond, if no errors',
                    ),
                    'errors': fields.List(
                        fields.Any(
                            fields.ObjectInstance(Error),
                            fields.Dictionary(
                                {
                                    'code': fields.UnicodeString(),
                                    'message': fields.UnicodeString(),
                                    'field': fields.UnicodeString(),
                                    'traceback': fields.UnicodeString(),
                                    'variables': fields.SchemalessDictionary(),
                                    'denied_permissions': fields.List(fields.UnicodeString()),
                                },
                                optional_keys=('field', 'traceback', 'variables', 'denied_permissions'),
                            ),
                        ),
                        description='The errors with which the action should respond, if no body',
                    ),
                },
                description='A dictionary containing either a body dict or an errors list, providing an '
                            'instruction on how the stub action should respond to requests',
                optional_keys=('body', 'errors'),
            ),
        ),
    }

    optional_keys = ('action_map', )

    description = 'The settings for the local transport'


@fields.ClassConfigurationSchema.provider(StubClientTransportSchema())
class StubClientTransport(LocalClientTransport):
    """A transport that incorporates an automatically-configured StubServer for handling requests."""

    def __init__(
        self,
        service_name='test',  # type: six.text_type
        metrics=None,  # type: Optional[MetricsRecorder]
        action_map=None,  # type: Optional[Mapping[six.text_type, Mapping[six.text_type, Any]]]
    ):
        # type: (...) -> None
        """
        Configure a StubServer to handle requests. Creates a new subclass of StubServer using the service name and
        action mapping provided.

        :param service_name: The service name.
        :param metrics: You can omit this, but if you really want, override the default `NoOpMetricsRecorder`.
        :param action_map: Dictionary of `{action_name: {'body': action_body, 'errors': action_errors}}` where
                           `action_body` is a dictionary and `action_errors` is a list.
        """
        action_map = action_map or {}
        # Build the action_class_map property for the new Server class
        action_class_map = {
            name: _make_stub_action(name, a.get('body', {}), a.get('errors', [])) for name, a in action_map.items()
        }
        # Create the new Server subclass
        server_class_name = ''.join([part.capitalize() for part in re.split(r'[^a-zA-Z0-9]+', service_name)]) + 'Server'
        server_class = cast(Type[StubServer], type(
            str(server_class_name),
            (StubServer,),
            dict(service_name=service_name, action_class_map=action_class_map),
        ))
        super(StubClientTransport, self).__init__(service_name, metrics or noop_metrics, server_class, {})

    def stub_action(self, action, body=None, errors=None):
        # type: (six.text_type, Optional[Body], Optional[Errors]) -> None
        """
        Stub the given action with the configured server.

        :param action: The action name
        :param body: The optional body to return
        :param errors: The optional errors to raise
        """
        cast(StubServer, self.server).stub_action(action, body=body, errors=errors)


class StubServer(Server):
    """A Server that provides an interface to stub actions, i.e. define actions inline, for testing purposes."""

    def stub_action(self, action, body=None, errors=None):
        """
        Make a new StubAction class with the given body and errors, and add it to the action_class_map.

        The name of the action class is the action name converted to camel case. For example, an action
        called 'update_foo' will have an action class called UpdateFoo.

        :param action: The action name
        :param body: The optional body to return
        :param errors: The optional errors to raise
        """
        cast(Dict[six.text_type, ActionType], self.action_class_map)[action] = _make_stub_action(action, body, errors)


class _StubActionRequestCounter(object):
    def __init__(self):  # type: () -> None
        self._counter = 0

    def get_next(self):  # type: () -> int
        value = self._counter
        self._counter += 1
        return value


_global_stub_action_request_counter = _StubActionRequestCounter()

_CT = TypeVar('_CT', Type[Any], Callable)
_CT_T = TypeVar('_CT_T', bound=Type[Any])
_CT_C = TypeVar('_CT_C', bound=Callable)

_ExcInfo = Union[Tuple[Type[BaseException], BaseException, TracebackType], Tuple[None, None, None]]
_StubActionSideEffectSimple = Union[Body, Exception, Type[Exception], Callable[[Body], Body]]
_StubActionSideEffect = Union[_StubActionSideEffectSimple, Iterable[_StubActionSideEffectSimple]]


# noinspection PyProtectedMember
class stub_action(object):
    """
    Stub an action temporarily. This is useful for things like unit testing, where you really need to test the code
    calling a service, but you don't want to test the actual service along with it, or the actual service isn't easily
    available from the automated test process.

    You can use this as a context manager or as a decorator, but you can only decorate classes, instance methods, and
    class methods. Decorating static methods and functions will cause it to barf on argument order.

    Some example uses cases:

    .. code-block:: python

        @stub_action('user', 'get_user', body={'user': {'id': 1234, 'username': 'John', 'email': 'john@example.org'}})
        class TestSomeCode(object):
            '''
            This class is decorated to stub an action that the tested code ends up calling for all or most of these
            tests.
            '''

            def test_simple_user_helper(self, stub_get_user):
                user = UserHelper().get_user_from_service(user_id=5678)

                # This shows all the various assertions that can be made:
                #  - stub_get_user.called: a simple boolean, yes or no it was or wasn't called at least once
                #  - stub_get_user.call_count: the number of times it was called
                #  - stub_get_user.call_body: the request body for the last time the stub action was called
                #  - stub_get_user.call_bodies: a tuple of all request bodies for all times the action was called
                #  - stub_get_user extends MagicMock, so you can use things like `assert_called_once_with` and
                #    `assert_has_calls` like you would with any MagicMock (the value passed to the mock is always
                #    the request body), but many will find `call_body` and `call_bodies` easier to use.
                self.assertTrue(stub_get_user.called)
                self.assertEqual(1, stub_get_user.call_count)
                self.assertEqual({'id': 5678}, stub_get_user.call_body)
                self.assertEqual(({'id': 5678}, ), stub_get_user.call_bodies)
                stub_get_user.assert_called_once_with({'id': 5678})
                stub_get_user.assert_has_calls(
                    mock.call({'id': 5678}),
                )

            @stub_action('settings', 'get_user_setting')
            def test_complex_user_helper(self, stub_get_user_setting, stub_get_user):
                # You can combine class and method decorators. As with `mock.patch`, the order of the arguments is the
                # reverse of that which you would expect. You can combine class and/or function stub decorators with
                # `mock.patch` decorators, and the order of the various stubs and mocks will likewise follow the order
                # they are mixed together.

                # Instead of passing a body or errors to the stub decorator or context manager, you can add it to the
                # stub after creation (but before use). Since action stubs extend `MagicMock`, you can use
                # `return_value` (it should be the response body dict) or `side_effect` (it should be ActionError(s) or
                # response body dict(s)). We use `side_effect` here to demonstrate expecting multiple calls.

                stub_get_user_setting.side_effect = (
                    {'value': 'This is the first setting value response'},
                    {'value': 'This is the second setting value response'},
                    ActionError(errors=[Error(code='NO_SUCH_SETTING', message='The setting does not exist')]),
                )

                settings = UserHelper().get_user_settings(user_id=1234)

                self.assertEqual(
                    {
                        'setting1', 'This is the first setting value response',
                        'setting2', 'This is the second setting value response',
                    },
                    settings,
                )

                self.assertEqual(3, stub_get_user_setting.call_count)
                self.assertEqual(
                    (
                        {'user_id': 1234, 'setting_id': 'setting1'},
                        {'user_id': 1234, 'setting_id': 'setting2'},
                        {'user_id': 1234, 'setting_id': 'setting3'}
                    ),
                    stub_get_user_setting.call_bodies,
                )

                stub_user.assert_called_once_with({'id': 1234})

            def test_another_user_helper_with_context_manager(self, stub_get_user):
                # Using a context manager is intuitive and works essentially the same as using a decorator

                with stub_action('payroll', 'get_salary') as stub_get_salary:
                    stub_get_salary.return_value = {'salary': 75950}

                    salary = UserHelper().get_user_salary(user_id=1234)

                self.assertEqual(75950, salary)

                self.assertEqual(1, stub_get_salary.call_count)
                self.assertEqual({'user_id': 1234}, stub_get_salary.call_body)

                stub_user.assert_called_once_with({'id': 1234})
    """

    class _MockAction(mock.MagicMock):
        @property
        def call_body(self):
            return self.call_args[0][0] if self.called else None

        @property
        def call_bodies(self):
            return tuple(args[0][0] for args in self.call_args_list)

    def __init__(
        self,
        service,  # type: six.text_type
        action,  # type: six.text_type
        body=None,  # type: Optional[Body]
        errors=None,  # type: Optional[Errors]
        side_effect=None,  # type: _StubActionSideEffect
    ):  # type: (...) -> None
        assert isinstance(service, six.text_type), 'Stubbed service name "{}" must be unicode'.format(service)
        assert isinstance(action, six.text_type), 'Stubbed action name "{}" must be unicode'.format(action)

        self.service = service
        self.action = action
        self.body = body or {}
        self.errors = errors or []
        self.side_effect = side_effect
        self.enabled = False

        # Play nice with @mock.patch
        self.attribute_name = None  # type: Optional[six.text_type]
        self.new = mock.DEFAULT

        # noinspection PyProtectedMember
        self._current_mock_action = None  # type: Optional[stub_action._MockAction]
        self._stub_action_responses_outstanding = defaultdict(
            dict,
        )  # type: Dict[six.text_type, Dict[int, Union[Exception, JobResponse]]]
        self._stub_action_responses_to_merge = defaultdict(
            dict,
        )  # type: Dict[six.text_type, Dict[int, Tuple[int, bool]]]

    def __enter__(self):  # type: () -> stub_action._MockAction
        if self.enabled:
            assert self._current_mock_action is not None, (
                'Enabled stub_action with no current mock is in an inconsistent state'
            )
            return self._current_mock_action

        self._current_mock_action = self._MockAction(name='{}.{}'.format(self.service, self.action))

        self._wrapped_client_send_request = Client.send_request
        self._wrapped_client_get_all_responses = Client.get_all_responses
        self._services_with_calls_sent_to_wrapped_client = set()  # type: Set[six.text_type]

        if self.body or self.errors:
            self._current_mock_action.return_value = ActionResponse(self.action, errors=self.errors, body=self.body)

        if self.side_effect:
            self._current_mock_action.side_effect = self.side_effect

        @wraps(Client.send_request)
        def wrapped_send_request(client, service_name, actions, *args, **kwargs):
            assert isinstance(service_name, six.text_type), 'Called service name "{}" must be unicode'.format(
                service_name,
            )

            actions_to_send_to_mock = OrderedDict()  # type: OrderedDict[int, ActionRequest]
            actions_to_send_to_wrapped_client = []  # type: List[ActionRequest]
            for i, action_request in enumerate(actions):
                action_name = getattr(action_request, 'action', None) or action_request['action']
                assert isinstance(action_name, six.text_type), 'Called action name "{}" must be unicode'.format(
                    action_name,
                )

                if not isinstance(action_request, ActionRequest):
                    action_request = ActionRequest(**action_request)

                if service_name == self.service and action_name == self.action:
                    # If the service AND action name match, we should send the request to our mocked client
                    actions_to_send_to_mock[i] = action_request
                else:
                    # If the service OR action name DO NOT match, we should delegate the request to the wrapped client
                    actions_to_send_to_wrapped_client.append(action_request)

            request_id = _global_stub_action_request_counter.get_next()

            continue_on_error = kwargs.get('continue_on_error', False)

            if actions_to_send_to_wrapped_client:
                # If any un-stubbed actions need to be sent to the original client, send them
                self._services_with_calls_sent_to_wrapped_client.add(service_name)
                # noinspection PyArgumentList,PyTypeChecker
                unwrapped_request_id = self._wrapped_client_send_request(
                    client,
                    service_name,
                    actions_to_send_to_wrapped_client,
                    *args,
                    **kwargs
                )
                if not actions_to_send_to_mock:
                    # If there are no stubbed actions to mock, just return the un-stubbed request ID
                    return unwrapped_request_id

                self._stub_action_responses_to_merge[service_name][unwrapped_request_id] = (
                    request_id,
                    continue_on_error,
                )

            ordered_actions_for_merging = OrderedDict()  # type: OrderedDict[int, ActionResponse]
            job_response_transport_exception = None  # type: Optional[Exception]
            job_response = JobResponse()
            for i, action_request_obj in actions_to_send_to_mock.items():
                mock_response = None
                try:
                    assert self._current_mock_action is not None, (
                        'Enabled stub_action with no current mock is in an inconsistent state'
                    )
                    # noinspection PyCallingNonCallable
                    mock_response = self._current_mock_action(action_request_obj.body or {})
                    if isinstance(mock_response, JobResponse):
                        job_response.errors.extend(mock_response.errors)
                        if mock_response.actions:
                            mock_response = mock_response.actions[0]
                    elif isinstance(mock_response, dict):
                        mock_response = ActionResponse(self.action, body=mock_response)
                    elif not isinstance(mock_response, ActionResponse):
                        mock_response = ActionResponse(self.action)
                except ActionError as e:
                    mock_response = ActionResponse(self.action, errors=e.errors)
                except JobError as e:
                    job_response.errors.extend(e.errors)
                except (MessageReceiveError, MessageReceiveTimeout) as e:
                    job_response_transport_exception = e

                if mock_response:
                    ordered_actions_for_merging[i] = mock_response
                    job_response.actions.append(mock_response)
                    if not continue_on_error and mock_response.errors:
                        break

                if job_response.errors:
                    break

            if actions_to_send_to_wrapped_client:
                # If the responses will have to be merged by get_all_responses, replace the list with the ordered dict
                job_response.actions = ordered_actions_for_merging  # type: ignore

            self._stub_action_responses_outstanding[service_name][request_id] = (
                job_response_transport_exception or job_response
            )
            return request_id
        wrapped_send_request.description = (  # type: ignore
            '<stub {service}.{action} wrapper around {wrapped}>'.format(
                service=self.service,
                action=self.action,
                wrapped=getattr(Client.send_request, 'description', Client.send_request.__repr__()),
            )
        )  # This description is a helpful debugging tool

        @wraps(Client.get_all_responses)
        def wrapped_get_all_responses(client, service_name, *args, **kwargs):
            if service_name in self._services_with_calls_sent_to_wrapped_client:
                # Check if the any requests were actually sent wrapped client for this service; we do this because
                # the service may exist solely as a stubbed service, and calling the wrapped get_all_responses
                # will result in an error in this case.
                # noinspection PyArgumentList,PyTypeChecker
                for request_id, response in self._wrapped_client_get_all_responses(
                    client,
                    service_name,
                    *args,
                    **kwargs
                ):
                    if request_id in self._stub_action_responses_to_merge[service_name]:
                        request_id, continue_on_error = self._stub_action_responses_to_merge[service_name].pop(
                            request_id,
                        )
                        response_to_merge = self._stub_action_responses_outstanding[service_name].pop(request_id)

                        if isinstance(response_to_merge, Exception):
                            raise response_to_merge

                        # response_to_merge.actions here is actually an ordered dict of number to action response
                        # noinspection PyTypeChecker
                        for i, action_response in six.iteritems(response_to_merge.actions):  # type: ignore
                            response.actions.insert(i, action_response)

                        if not continue_on_error:
                            # Simulate the server job halting on the first action error
                            first_error_index = -1
                            for i, action_result in enumerate(response.actions):
                                if action_result.errors:
                                    first_error_index = i
                                    break
                            if first_error_index >= 0:
                                response.actions = response.actions[:first_error_index + 1]

                        response.errors.extend(response_to_merge.errors)
                    yield request_id, response

            if self._stub_action_responses_to_merge[service_name]:
                raise Exception('Something very bad happened, and there are still stubbed responses to merge!')

            for request_id, response_or_e in six.iteritems(self._stub_action_responses_outstanding[service_name]):
                if isinstance(response_or_e, Exception):
                    raise response_or_e
                yield request_id, response_or_e

            self._stub_action_responses_outstanding[service_name] = {}
        wrapped_get_all_responses.description = (  # type: ignore
            '<stub {service}.{action} wrapper around {wrapped}>'.format(
                service=self.service,
                action=self.action,
                wrapped=getattr(Client.get_all_responses, 'description', Client.get_all_responses.__repr__()),
            )
        )  # This description is a helpful debugging tool

        # Wrap Client.send_request, whose original version was saved in self._wrapped_client_send_request (which itself
        # might be another wrapper if we have stubbed multiple actions).
        Client.send_request = wrapped_send_request  # type: ignore

        # Wrap Client.get_all_responses, whose original version was saved in self._wrapped_client_get_all_responses
        # (which itself might be another wrapper if we have stubbed multiple actions).
        Client.get_all_responses = wrapped_get_all_responses  # type: ignore

        self.enabled = True
        return self._current_mock_action

    def __exit__(self, exc_type=None, exc_value=None, traceback=None):  # type: (Any, Any, Any) -> Literal[False]
        if not self.enabled:
            # noinspection PyTypeChecker
            return False

        # Unwrap Client.send_request and Client.get_all_responses to their previous versions (which might themselves be
        # other wrappers if we have stubbed multiple actions).
        Client.send_request = self._wrapped_client_send_request  # type: ignore
        Client.get_all_responses = self._wrapped_client_get_all_responses  # type: ignore
        self.enabled = False
        # noinspection PyTypeChecker
        return False

    def __call__(self, func):  # type: (_CT) -> _CT
        # This code inspired by mock.patch
        if isinstance(func, type):
            return self.decorate_class(func)
        return self.decorate_callable(func)

    def decorate_class(self, _class):  # type: (_CT_T) -> _CT_T
        # This code copied almost verbatim from unittest.mock.patch in Python 3.7
        for attr in dir(_class):
            # noinspection PyUnresolvedReferences
            if not attr.startswith(mock.patch.TEST_PREFIX):
                continue

            attr_value = getattr(_class, attr)
            if not hasattr(attr_value, '__call__'):
                continue

            stubber = self.__class__(self.service, self.action, self.body, self.errors, self.side_effect)
            setattr(_class, attr, stubber(attr_value))
        return _class

    def decorate_callable(self, func):  # type: (_CT_C) -> _CT_C
        # This code copied almost verbatim from unittest.mock.patch in Python 3.7
        if hasattr(func, 'patchings'):
            getattr(func, 'patchings').append(self)
            return func

        @wraps(func)
        def wrapped(*args, **kwargs):
            patching = None
            extra_args = []
            entered_patchers = []
            exc_info = ()  # type: Union[Tuple[()], _ExcInfo]
            try:
                for patching in getattr(wrapped, 'patchings'):
                    arg = patching.__enter__()
                    entered_patchers.append(patching)
                    if patching.attribute_name is not None:
                        kwargs.update(arg)
                    elif patching.new is mock.DEFAULT:
                        extra_args.append(arg)

                args += tuple(extra_args)
                return func(*args, **kwargs)
            except:  # noqa: E722
                if patching not in entered_patchers:
                    # the patcher may have been started, but an exception
                    # raised whilst entering one of its additional_patchers
                    entered_patchers.append(patching)
                # Pass the exception to __exit__
                exc_info = sys.exc_info()
                # re-raise the exception
                raise
            finally:
                for patching in reversed(entered_patchers):
                    patching.__exit__(*exc_info)

        setattr(wrapped, 'patchings', [self])
        return cast(_CT_C, wrapped)

    @property
    def is_local(self):  # type: () -> bool
        # Play nice with @mock.patch
        return self.enabled

    def start(self):  # type: () -> stub_action._MockAction
        return self.__enter__()

    def stop(self):  # type: () -> None
        self.__exit__()
