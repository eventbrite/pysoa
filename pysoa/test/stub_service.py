from __future__ import absolute_import, unicode_literals

from collections import OrderedDict
from functools import wraps
import re

import mock
import six

from pysoa.client.client import (
    Client,
    ServiceHandler,
)
from pysoa.client.settings import ClientSettings
from pysoa.common.metrics import NoOpMetricsRecorder
from pysoa.common.transport.local import LocalClientTransport
from pysoa.common.types import (
    ActionRequest,
    ActionResponse,
    Error,
    JobResponse,
)
from pysoa.server import Server
from pysoa.server.action import (
    Action,
    ActionError,
)


def _make_stub_action(action_name, body=None, errors=None):
    body = body or {}
    errors = errors or []
    action_class_name = ''.join([part.capitalize() for part in re.split(r'[^a-zA-Z0-9]+', action_name)])
    return type(
        str(action_class_name),
        (_StubAction,),
        dict(body=body, errors=errors),
    )


class _StubAction(Action):
    """An Action that simply returns a preset value or error."""

    body = {}
    errors = []

    def run(self, request):
        if self.errors:
            raise ActionError(
                errors=[
                    Error(
                        code=e['code'],
                        message=e['message'],
                        field=e.get('field'),
                    ) if not isinstance(e, Error) else e for e in self.errors
                ]
            )
        else:
            return self.body

    def __call__(self, action_request):
        response_body = self.run(action_request)

        if response_body is not None:
            return ActionResponse(action=action_request.action, body=response_body)
        else:
            return ActionResponse(action=action_request.action)


class StubClientSettings(ClientSettings):
    defaults = {
        'transport': {
            'path': 'pysoa.test.stub_service:StubClientTransport'
        }
    }


class StubClient(Client):
    """
    A Client for testing code that calls service actions.

    Uses StubClientTransport, which incorporates a server for handling requests. Uses the real Server
    code path, so that developers needing to test their code against particular service responses can
    test against a genuine service in a unit testing environment.
    """

    settings_class = StubClientSettings

    def __init__(self, service_action_map=None, **_):
        """
        Generate settings based on a mapping of service names to actions.

        Args:
            service_action_map: dict of {service_name: <action map>}
        """
        service_action_map = service_action_map or {}
        config = {}
        for service_name, action_map in service_action_map.items():
            config[service_name] = {
                'transport': {
                    'kwargs': {
                        'action_map': action_map,
                    }
                }
            }
        super(StubClient, self).__init__(config)

    def stub_action(self, service_name, action, body=None, errors=None):
        """
        Stub the given action for the given service, configuring a handler and transport for that service if necessary.

        :param service_name: The service name
        :param action: The action name
        :param body: The optional body to return
        :param errors: The optional errors to raise
        """
        if service_name not in self.handlers:
            self.handlers[service_name] = ServiceHandler(service_name, self.settings_class({}))
        self.handlers[service_name].transport.stub_action(action, body=body, errors=errors)


class StubClientTransport(LocalClientTransport):
    """A transport that incorporates an automatically-configured Server for handling requests."""

    def __init__(self, service_name='test', metrics=None, action_map=None):
        """
        Configure a StubServer to handle requests. Creates a new subclass of StubServer using the service name and
        action mapping provided.

        Args:
            service_name: string
            action_map: dict of {action_name: {'body': action_body, 'errors': action_errors}} where action_body is a
                dict and action_errors is a list
        """
        action_map = action_map or {}
        # Build the action_class_map property for the new Server class
        action_class_map = {
            name: _make_stub_action(name, a.get('body', {}), a.get('errors', [])) for name, a in action_map.items()
        }
        # Create the new Server subclass
        server_class_name = ''.join([part.capitalize() for part in re.split(r'[^a-zA-Z0-9]+', service_name)]) + 'Server'
        server_class = type(
            str(server_class_name),
            (StubServer,),
            dict(service_name=service_name, action_class_map=action_class_map),
        )
        super(StubClientTransport, self).__init__(service_name, metrics or NoOpMetricsRecorder(), server_class, {})

    def stub_action(self, action, body=None, errors=None):
        """
        Stub the given action with the configured server.

        :param action: The action name
        :param body: The optional body to return
        :param errors: The optional errors to raise
        """
        self.server.stub_action(action, body=body, errors=errors)


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
        self.action_class_map[action] = _make_stub_action(action, body, errors)


class stub_action(object):  # noqa
    """
    Stub an action temporarily. This is useful for things like unit testing, where you really need to test the code
    calling a service, but you don't want to test the actual service along with it, or the actual service isn't easily
    available from the automated test process.

    You can use this as a context manager or as a decorator, but you can only decorate classes, instance methods, and
    class methods. Decorating static methods and functions will cause it to barf on argument order.

    Some example uses cases:

        @stub_action('user', 'get_user', body={'user': {'id': 1234, 'username': 'John', 'email': 'john@example.org'}})
        class TestSomeCode(unittest.TestCase):
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

    def __init__(self, service, action, body=None, errors=None):
        assert isinstance(service, six.text_type), 'Stubbed service name "{}" must be unicode'.format(service)
        assert isinstance(action, six.text_type), 'Stubbed action name "{}" must be unicode'.format(action)

        self.service = service
        self.action = action
        self.body = body or {}
        self.errors = errors or []
        self.enabled = False

        # Play nice with @mock.patch
        self.attribute_name = None
        self.new = mock.DEFAULT

    def __enter__(self):
        self._wrapped_client_call_actions_method = Client.call_actions

        mock_action = self._MockAction(name='{}.{}'.format(self.service, self.action))

        if self.body or self.errors:
            mock_client = StubClient()
            mock_client.stub_action(self.service, self.action, body=self.body, errors=self.errors)
            mock_action.side_effect = lambda body: self._wrapped_client_call_actions_method(
                mock_client,
                self.service,
                [ActionRequest(self.action, body=body)],
                raise_action_errors=False,
            )

        @wraps(Client.call_actions)
        def wrapped(client, service_name, actions, *args, **kwargs):
            assert isinstance(service_name, six.text_type), 'Called service name "{}" must be unicode'.format(
                service_name,
            )

            requests_to_send_to_mock_client = OrderedDict()
            requests_to_send_to_wrapped_client = []
            for i, action_request in enumerate(actions):
                action_name = getattr(action_request, 'action', None) or action_request['action']
                assert isinstance(action_name, six.text_type), 'Called action name "{}" must be unicode'.format(
                    action_name,
                )

                if service_name == self.service and action_name == self.action:
                    # If the service AND action name match, we should send the request to our mocked client
                    if not isinstance(action_request, ActionRequest):
                        action_request = ActionRequest(action_request)
                    requests_to_send_to_mock_client[i] = action_request
                else:
                    # If the service OR action name DO NOT match, we should delegate the request to the wrapped client
                    requests_to_send_to_wrapped_client.append(action_request)

            # Hold off on raising action errors until both mock and real responses are merged
            raise_action_errors = kwargs.get('raise_action_errors', True)
            kwargs['raise_action_errors'] = False
            # Run the real and mocked jobs and merge the results, to simulate a single job
            if requests_to_send_to_wrapped_client:
                job_response = self._wrapped_client_call_actions_method(
                    client,
                    service_name,
                    requests_to_send_to_wrapped_client,
                    *args,
                    **kwargs
                )
            else:
                job_response = JobResponse()
            for i, action_request in requests_to_send_to_mock_client.items():
                try:
                    mock_response = mock_action(action_request.body or {})
                    if isinstance(mock_response, JobResponse):
                        mock_response = mock_response.actions[0]
                    elif isinstance(mock_response, dict):
                        mock_response = ActionResponse(self.action, body=mock_response)
                    elif not isinstance(mock_response, ActionResponse):
                        mock_response = ActionResponse(self.action)
                except ActionError as e:
                    mock_response = ActionResponse(self.action, errors=e.errors)
                job_response.actions.insert(i, mock_response)
            if kwargs.get('continue_on_error', False) is False:
                # Simulate the server job halting on the first action error
                first_error_index = -1
                for i, action_result in enumerate(job_response.actions):
                    if action_result.errors:
                        first_error_index = i
                        break
                if first_error_index >= 0:
                    job_response.actions = job_response.actions[:first_error_index + 1]
            if raise_action_errors:
                error_actions = [action for action in job_response.actions if action.errors]
                if error_actions:
                    raise Client.CallActionError(error_actions)

            return job_response
        wrapped.description = '<stub {service}.{action} wrapper around {wrapped}>'.format(
            service=self.service,
            action=self.action,
            wrapped=getattr(Client.call_actions, 'description', Client.call_actions.__repr__()),
        )  # This description is a helpful debugging tool

        # Wrap Client.call_actions whose original version was saved in self._wrapped_client_call_actions_method (which
        # itself might be another wrapper if we have stubbed multiple actions).
        Client.call_actions = wrapped
        self.enabled = True
        return mock_action

    def __exit__(self, *args):
        # Unwrap Client.call_actions to its previous version (which might itself be another wrapper if we have
        # stubbed multiple actions).
        Client.call_actions = self._wrapped_client_call_actions_method
        self.enabled = False

    def __call__(self, func):
        # This code inspired by mock.patch
        if isinstance(func, type):
            return self.decorate_class(func)
        return self.decorate_callable(func)

    def decorate_class(self, _class):
        # This code inspired by mock.patch
        for attr in dir(_class):
            # noinspection PyUnresolvedReferences
            if not attr.startswith(mock.patch.TEST_PREFIX):
                continue

            attr_value = getattr(_class, attr)
            if not hasattr(attr_value, '__call__'):
                continue

            stubber = self.__class__(self.service, self.action, self.body, self.errors)
            setattr(_class, attr, stubber(attr_value))
        return _class

    def decorate_callable(self, func):
        # This code inspired by mock.patch
        if hasattr(func, 'patchings'):
            func.patchings.append(self)
            return func

        @wraps(func)
        def wrapped(*args, **kwargs):
            try:
                mock_arg = self.__enter__()
                args = args[:1] + (mock_arg, ) + args[1:]
                value = func(*args, **kwargs)
            finally:
                self.__exit__()
            return value

        return wrapped

    @property
    def is_local(self):
        # Play nice with @mock.patch
        return self.enabled

    def start(self):
        return self.__enter__()

    def stop(self):
        self.__exit__()
