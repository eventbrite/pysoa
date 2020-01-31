from __future__ import (
    absolute_import,
    unicode_literals,
)

import copy
import random
from typing import (
    Any,
    Dict,
    List,
)
from unittest import TestCase

import attr
from conformity.settings import SettingsData
from parameterized import parameterized
import pytest
import six

from pysoa.client.client import Client
from pysoa.common.constants import (
    ERROR_CODE_INVALID,
    ERROR_CODE_NOT_AUTHORIZED,
)
from pysoa.common.errors import Error
from pysoa.common.transport.errors import MessageReceiveTimeout
from pysoa.common.types import (
    ActionRequest,
    ActionResponse,
    JobResponse,
    UnicodeKeysDict,
)
from pysoa.server.action import Action
from pysoa.server.errors import (
    ActionError,
    JobError,
)
from pysoa.server.server import Server
from pysoa.test.compatibility import mock
from pysoa.test.factories import ActionFactory
from pysoa.test.server import (
    PyTestServerTestCase,
    UnitTestServerTestCase,
)
from pysoa.test.stub_service import (
    StubClient,
    stub_action,
)


STUB_CLIENT_SERVICE_NAME = 'test_stub_client_service'


class TestStubClient(TestCase):

    def setUp(self):
        self.client = StubClient()

    def test_init_with_action_map(self):
        get_foo_body = {
            'foo': {
                'id': 1,
            },
        }
        get_bar_error = {
            'code': 'invalid',
            'message': 'Invalid value for bar.id',
            'field': 'id',
        }

        client = StubClient(service_action_map={
            'foo_service': {
                'get_foo': {
                    'body': get_foo_body
                },
            },
            'bar_service': {
                'get_bar': {
                    'errors': [get_bar_error],
                },
            },
        })
        foo_rsp = client.call_action('foo_service', 'get_foo')
        self.assertEqual(foo_rsp.body, get_foo_body)
        with self.assertRaises(client.CallActionError) as e:
            client.call_action('bar_service', 'get_bar')

        error_response = e.exception.actions[0].errors
        self.assertEqual(len(error_response), 1)
        self.assertEqual(error_response[0].code, get_bar_error['code'])
        self.assertEqual(error_response[0].message, get_bar_error['message'])

    def test_stub_action_body_only(self):
        """
        StubClient.stub_action with a 'body' argument causes the client to return an action
        response with the given body.
        """
        response_body = {'foo': 'bar'}
        self.client.stub_action(STUB_CLIENT_SERVICE_NAME, 'test_action', body=response_body)
        response = self.client.call_action(STUB_CLIENT_SERVICE_NAME, 'test_action')
        self.assertEqual(response.body, response_body)

    def test_stub_action_errors(self):
        """
        StubClient.stub_action with an 'errors' argument causes the client to raise the
        given errors when calling the action.
        """
        errors = [
            {
                'code': ERROR_CODE_INVALID,
                'message': 'Invalid input',
                'field': 'foo.bar.baz',
            }
        ]
        self.client.stub_action(STUB_CLIENT_SERVICE_NAME, 'test_action', errors=errors)
        with self.assertRaises(StubClient.CallActionError) as e:
            self.client.call_action(STUB_CLIENT_SERVICE_NAME, 'test_action')

        error_response = e.exception.actions[0].errors
        self.assertEqual(len(error_response), 1)
        self.assertEqual(error_response[0].code, errors[0]['code'])
        self.assertEqual(error_response[0].message, errors[0]['message'])
        self.assertEqual(error_response[0].field, errors[0]['field'])

    def test_stub_action_permissions_errors(self):
        """
        StubClient.stub_action with an 'errors' argument causes the client to raise the
        given errors when calling the action.
        """
        errors = [
            {
                'code': ERROR_CODE_NOT_AUTHORIZED,
                'message': 'Permission "foo" required to access this resource',
                'denied_permissions': ['foo'],
            }
        ]
        self.client.stub_action(STUB_CLIENT_SERVICE_NAME, 'test_action', errors=errors)
        with self.assertRaises(StubClient.CallActionError) as e:
            self.client.call_action(STUB_CLIENT_SERVICE_NAME, 'test_action')

        error_response = e.exception.actions[0].errors
        self.assertEqual(len(error_response), 1)
        self.assertEqual(error_response[0].code, errors[0]['code'])
        self.assertEqual(error_response[0].message, errors[0]['message'])
        self.assertEqual(error_response[0].denied_permissions, errors[0]['denied_permissions'])

    def test_stub_action_errors_and_body(self):
        """
        StubClient.stub_action with an 'errors' argument and a 'body' argument causes the
        client to raise the given errors when calling the action.
        """
        errors = [
            {
                'code': ERROR_CODE_INVALID,
                'message': 'Invalid input',
                'field': 'foo.bar.baz',
            }
        ]
        response_body = {'foo': 'bar'}
        self.client.stub_action(STUB_CLIENT_SERVICE_NAME, 'test_action', errors=errors, body=response_body)
        with self.assertRaises(StubClient.CallActionError) as e:
            self.client.call_action(STUB_CLIENT_SERVICE_NAME, 'test_action')

        error_response = e.exception.actions[0].errors
        self.assertEqual(len(error_response), 1)
        self.assertEqual(error_response[0].code, errors[0]['code'])
        self.assertEqual(error_response[0].message, errors[0]['message'])
        self.assertEqual(error_response[0].field, errors[0]['field'])

    @mock.patch('pysoa.client.client.ServiceHandler._client_version', new=[0, 68, 0])
    def test_multiple_requests(self):
        """
        Sending multiple requests with StubClient.send_request for different actions and then
        calling get_all_responses returns responses for all the actions that were called.
        """
        responses = {
            'action_1': {'body': {'foo': 'bar'}, 'errors': []},
            'action_2': {'body': {'baz': 42}, 'errors': []},
            'action_3': {
                'body': {},
                'errors': [
                    {
                        'code': ERROR_CODE_INVALID,
                        'message': 'Invalid input',
                        'field': 'quas.wex',
                        'traceback': None,
                        'variables': None,
                        'denied_permissions': None,
                        'is_caller_error': True,
                    },
                ],
            },
        }  # type: Dict[six.text_type, Dict[six.text_type, Any]]
        self.client.stub_action(STUB_CLIENT_SERVICE_NAME, 'action_1', **responses['action_1'])
        self.client.stub_action(STUB_CLIENT_SERVICE_NAME, 'action_2', **responses['action_2'])
        self.client.stub_action(STUB_CLIENT_SERVICE_NAME, 'action_3', **responses['action_3'])

        control = self.client._make_control_header()
        context = self.client._make_context_header()
        request_1 = dict(control_extra=control, context=context, actions=[
            {'action': 'action_1'},
            {'action': 'action_2'},
        ])  # type: Dict[six.text_type, Any]
        request_2 = dict(control_extra=control, context=context, actions=[
            {'action': 'action_2'},
            {'action': 'action_1'},
        ])  # type: Dict[six.text_type, Any]
        request_3 = dict(control_extra=control, context=context, actions=[
            {'action': 'action_3'},
        ])  # type: Dict[six.text_type, Any]

        # Store requests by request ID for later verification, because order is not guaranteed
        requests_by_id = {}
        for request in (request_1, request_2, request_3):
            request_id = self.client.send_request(STUB_CLIENT_SERVICE_NAME, **request)
            requests_by_id[request_id] = request

        # Because we've patched the client version to look old, we need to be sure that `is_caller_error` isn't
        # coming through.
        responses = copy.deepcopy(responses)
        responses['action_3']['errors'][0]['is_caller_error'] = False  # type: ignore

        for response_id, response in self.client.get_all_responses(STUB_CLIENT_SERVICE_NAME):
            # The client returned the same number of actions as were requested
            self.assertEqual(len(response.actions), len(requests_by_id[response_id]['actions']))
            for i in range(len(response.actions)):
                action_response = response.actions[i]
                # The action name returned matches the action name in the request
                self.assertEqual(action_response.action, requests_by_id[response_id]['actions'][i]['action'])
                # The action response matches the expected response
                # Errors are returned as the Error type, so convert them to dict first
                self.assertEqual(action_response.body, responses[action_response.action]['body'])  # type: ignore
                self.assertEqual(
                    [attr.asdict(e, dict_factory=UnicodeKeysDict) for e in action_response.errors],
                    responses[action_response.action]['errors'],  # type: ignore
                )

    @mock.patch('pysoa.client.client.ServiceHandler._client_version', new=[0, 70, 0])
    def test_multiple_requests_with_is_caller_error(self):
        """
        Sending multiple requests with StubClient.send_request for different actions and then
        calling get_all_responses returns responses for all the actions that were called.
        """
        responses = {
            'action_1': {'body': {'foo': 'bar'}, 'errors': []},
            'action_2': {'body': {'baz': 42}, 'errors': []},
            'action_3': {
                'body': {},
                'errors': [
                    {
                        'code': ERROR_CODE_INVALID,
                        'message': 'Invalid input',
                        'field': 'quas.wex',
                        'traceback': None,
                        'variables': None,
                        'denied_permissions': None,
                        'is_caller_error': True,
                    },
                ],
            },
        }  # type: Dict[six.text_type, Dict[six.text_type, Any]]
        self.client.stub_action(STUB_CLIENT_SERVICE_NAME, 'action_1', **responses['action_1'])
        self.client.stub_action(STUB_CLIENT_SERVICE_NAME, 'action_2', **responses['action_2'])
        self.client.stub_action(STUB_CLIENT_SERVICE_NAME, 'action_3', **responses['action_3'])

        control = self.client._make_control_header()
        context = self.client._make_context_header()
        request_1 = dict(control_extra=control, context=context, actions=[
            {'action': 'action_1'},
            {'action': 'action_2'},
        ])  # type: Dict[six.text_type, Any]
        request_2 = dict(control_extra=control, context=context, actions=[
            {'action': 'action_2'},
            {'action': 'action_1'},
        ])  # type: Dict[six.text_type, Any]
        request_3 = dict(control_extra=control, context=context, actions=[
            {'action': 'action_3'},
        ])  # type: Dict[six.text_type, Any]

        # Store requests by request ID for later verification, because order is not guaranteed
        requests_by_id = {}
        for request in (request_1, request_2, request_3):
            request_id = self.client.send_request(STUB_CLIENT_SERVICE_NAME, **request)
            requests_by_id[request_id] = request

        for response_id, response in self.client.get_all_responses(STUB_CLIENT_SERVICE_NAME):
            # The client returned the same number of actions as were requested
            self.assertEqual(len(response.actions), len(requests_by_id[response_id]['actions']))
            for i in range(len(response.actions)):
                action_response = response.actions[i]
                # The action name returned matches the action name in the request
                self.assertEqual(action_response.action, requests_by_id[response_id]['actions'][i]['action'])
                # The action response matches the expected response
                # Errors are returned as the Error type, so convert them to dict first
                self.assertEqual(action_response.body, responses[action_response.action]['body'])  # type: ignore
                self.assertEqual(
                    [attr.asdict(e, dict_factory=UnicodeKeysDict) for e in action_response.errors],
                    responses[action_response.action]['errors'],  # type: ignore
                )


def _test_function(a, b):
    return random.randint(a, b)


class _TestAction(Action):
    def run(self, request):
        return {
            'value': _test_function(0, 99),
        }


class _TestServiceServer(Server):
    service_name = 'test_service'
    action_class_map = {
        'test_action_1': _TestAction,
        'test_action_2': ActionFactory(body={'value': 0}),
    }


_secondary_stub_client_settings = {
    'cat': {
        'transport': {
            'path': 'pysoa.test.stub_service:StubClientTransport',
            'kwargs': {
                'action_map': {
                    'meow': {'body': {'type': 'squeak'}},
                },
            },
        },
    },
    'dog': {
        'transport': {
            'path': 'pysoa.test.stub_service:StubClientTransport',
            'kwargs': {
                'action_map': {
                    'bark': {'body': {'sound': 'woof'}},
                },
            },
        },
    },
}


def stub_test_action(add_extra=True):
    def _run(body, **kwargs):
        if add_extra and body.get('type') == 'admin':
            body['extra'] = 'data'
        return body

    return stub_action(
        'test_service',
        'test_action',
        side_effect=_run,
    )


class TestStubAction(PyTestServerTestCase):
    server_class = _TestServiceServer
    server_settings = {}  # type: SettingsData

    def setup_method(self):
        super(TestStubAction, self).setup_method()

        self.secondary_stub_client = Client(_secondary_stub_client_settings)

    @stub_action('test_service', 'test_action_1')
    def test_one_stub_as_decorator(self, stub_test_action_1):
        stub_test_action_1.return_value = {'value': 1}

        response = self.client.call_action('test_service', 'test_action_1')
        self.assertEqual({'value': 1}, response.body)

        self.assertEqual(1, stub_test_action_1.call_count)
        self.assertEqual({}, stub_test_action_1.call_body)
        stub_test_action_1.assert_called_once_with({})

    if not six.PY2:
        # In Python 2, PyTest's parametrize cannot be used with patchings like mock.patch and stub_action
        @pytest.mark.parametrize(('input_arg', ), (('foo', ), ('bar', )))
        @stub_action('test_service', 'test_action_1')
        def test_one_stub_as_decorator_with_pytest_parametrize_before(self, stub_test_action_1, input_arg):
            stub_test_action_1.return_value = {'value': 1}

            response = self.client.call_action('test_service', 'test_action_1')
            self.assertEqual({'value': 1}, response.body)

            self.assertEqual(1, stub_test_action_1.call_count)
            self.assertEqual({}, stub_test_action_1.call_body)
            stub_test_action_1.assert_called_once_with({})

            assert input_arg in ('foo', 'bar')

        @stub_action('test_service', 'test_action_1')
        @pytest.mark.parametrize(('input_arg',), (('foo',), ('bar',)))
        def test_one_stub_as_decorator_with_pytest_parametrize_after(self, stub_test_action_1, input_arg):
            stub_test_action_1.return_value = {'value': 1}

            response = self.client.call_action('test_service', 'test_action_1')
            self.assertEqual({'value': 1}, response.body)

            self.assertEqual(1, stub_test_action_1.call_count)
            self.assertEqual({}, stub_test_action_1.call_body)
            stub_test_action_1.assert_called_once_with({})

            assert input_arg in ('foo', 'bar')

    @parameterized.expand((('foo', ), ('bar', )))
    @stub_action('test_service', 'test_action_1')
    def test_one_stub_as_decorator_with_3rd_party_parametrize(self, input_arg, stub_test_action_1):
        stub_test_action_1.return_value = {'value': 1}

        response = self.client.call_action('test_service', 'test_action_1')
        self.assertEqual({'value': 1}, response.body)

        self.assertEqual(1, stub_test_action_1.call_count)
        self.assertEqual({}, stub_test_action_1.call_body)
        stub_test_action_1.assert_called_once_with({})

        assert input_arg in ('foo', 'bar')

    @stub_action('test_service', 'test_action_1')
    def _external_method_get_response(self, stub_test_action_1):
        stub_test_action_1.return_value = {'value': -5}

        try:
            return self.client.call_action('test_service', 'test_action_1')
        finally:
            self.assertEqual(1, stub_test_action_1.call_count)
            self.assertEqual({}, stub_test_action_1.call_body)
            stub_test_action_1.assert_called_once_with({})

    def test_one_stub_as_decorated_external_method(self):
        response = self._external_method_get_response()
        self.assertEqual({'value': -5}, response.body)

    def test_one_stub_as_context_manager(self):
        with stub_action('test_service', 'test_action_1') as stub_test_action_1:
            stub_test_action_1.return_value = {'value': 1}

            response = self.client.call_action('test_service', 'test_action_1')

        self.assertEqual({'value': 1}, response.body)

        self.assertEqual(1, stub_test_action_1.call_count)
        self.assertEqual({}, stub_test_action_1.call_body)
        stub_test_action_1.assert_called_once_with({})

    @stub_action('test_service', 'test_action_1', body={'value': 1})
    def test_one_stub_as_decorator_with_body(self, stub_test_action_1):
        response = self.client.call_action('test_service', 'test_action_1')
        self.assertEqual({'value': 1}, response.body)

        self.assertEqual(1, stub_test_action_1.call_count)
        self.assertEqual({}, stub_test_action_1.call_body)
        stub_test_action_1.assert_called_once_with({})

    def test_one_stub_as_context_manager_with_body(self):
        with stub_action('test_service', 'test_action_1', body={'value': 1}) as stub_test_action_1:
            response = self.client.call_action('test_service', 'test_action_1')

        self.assertEqual({'value': 1}, response.body)

        self.assertEqual(1, stub_test_action_1.call_count)
        self.assertEqual({}, stub_test_action_1.call_body)
        stub_test_action_1.assert_called_once_with({})

    def test_one_stub_duplicated_as_context_manager(self):
        original_client_send_request = Client.send_request
        original_client_get_all_responses = Client.get_all_responses

        stub = stub_action('test_service', 'test_action_1', body={'value': 1})

        with stub as stub_test_action_1, stub as second_stub_test_action_1:
            response = self.client.call_action('test_service', 'test_action_1')

        # Check stub is correctly reverted
        for client_func, original_func in (
            (Client.send_request, original_client_send_request),
            (Client.get_all_responses, original_client_get_all_responses),
        ):
            self.assertTrue(
                six.get_unbound_function(client_func) is six.get_unbound_function(original_func)  # type: ignore
            )

        self.assertEqual({'value': 1}, response.body)

        self.assertTrue(stub_test_action_1 is second_stub_test_action_1)
        self.assertEqual(1, stub_test_action_1.call_count)
        self.assertEqual({}, stub_test_action_1.call_body)
        stub_test_action_1.assert_called_once_with({})

    @stub_action('test_service', 'test_action_2')
    @stub_action('test_service', 'test_action_1')
    def test_two_stubs_same_service_as_decorator(self, stub_test_action_1, stub_test_action_2):
        stub_test_action_1.return_value = {'value': 1}
        stub_test_action_2.return_value = {'another_value': 2}

        response = self.client.call_action('test_service', 'test_action_1')
        self.assertEqual({'value': 1}, response.body)

        response = self.client.call_action('test_service', 'test_action_2', {'input_attribute': True})
        self.assertEqual({'another_value': 2}, response.body)

        self.assertEqual(1, stub_test_action_1.call_count)
        self.assertEqual({}, stub_test_action_1.call_body)
        self.assertEqual(1, stub_test_action_2.call_count)
        self.assertEqual({'input_attribute': True}, stub_test_action_2.call_body)
        stub_test_action_1.assert_called_once_with({})
        stub_test_action_2.assert_called_once_with({'input_attribute': True})

    if not six.PY2:
        # In Python 2, PyTest's parametrize cannot be used with patchings like mock.patch and stub_action
        @pytest.mark.parametrize(('input_arg',), (('foo',), ('bar',)))
        @stub_action('test_service', 'test_action_2')
        @stub_action('test_service', 'test_action_1')
        def test_two_stubs_same_service_as_decorator_with_pytest_parametrize_before(
            self,
            stub_test_action_1,
            stub_test_action_2,
            input_arg,
        ):
            stub_test_action_1.return_value = {'value': 1}
            stub_test_action_2.return_value = {'another_value': 2}

            response = self.client.call_action('test_service', 'test_action_1')
            self.assertEqual({'value': 1}, response.body)

            response = self.client.call_action('test_service', 'test_action_2', {'input_attribute': True})
            self.assertEqual({'another_value': 2}, response.body)

            self.assertEqual(1, stub_test_action_1.call_count)
            self.assertEqual({}, stub_test_action_1.call_body)
            self.assertEqual(1, stub_test_action_2.call_count)
            self.assertEqual({'input_attribute': True}, stub_test_action_2.call_body)
            stub_test_action_1.assert_called_once_with({})
            stub_test_action_2.assert_called_once_with({'input_attribute': True})

            assert input_arg in ('foo', 'bar')

        @stub_action('test_service', 'test_action_2')
        @stub_action('test_service', 'test_action_1')
        @pytest.mark.parametrize(('input_arg',), (('foo',), ('bar',)))
        def test_two_stubs_same_service_as_decorator_with_pytest_parametrize_after(
            self,
            stub_test_action_1,
            stub_test_action_2,
            input_arg,
        ):
            stub_test_action_1.return_value = {'value': 1}
            stub_test_action_2.return_value = {'another_value': 2}

            response = self.client.call_action('test_service', 'test_action_1')
            self.assertEqual({'value': 1}, response.body)

            response = self.client.call_action('test_service', 'test_action_2', {'input_attribute': True})
            self.assertEqual({'another_value': 2}, response.body)

            self.assertEqual(1, stub_test_action_1.call_count)
            self.assertEqual({}, stub_test_action_1.call_body)
            self.assertEqual(1, stub_test_action_2.call_count)
            self.assertEqual({'input_attribute': True}, stub_test_action_2.call_body)
            stub_test_action_1.assert_called_once_with({})
            stub_test_action_2.assert_called_once_with({'input_attribute': True})

            assert input_arg in ('foo', 'bar')

    @parameterized.expand((('foo',), ('bar',)))
    @stub_action('test_service', 'test_action_2')
    @stub_action('test_service', 'test_action_1')
    def test_two_stubs_same_service_as_decorator_with_3rd_party_parametrize(
        self,
        input_arg,
        stub_test_action_1,
        stub_test_action_2,
    ):
        stub_test_action_1.return_value = {'value': 1}
        stub_test_action_2.return_value = {'another_value': 2}

        response = self.client.call_action('test_service', 'test_action_1')
        self.assertEqual({'value': 1}, response.body)

        response = self.client.call_action('test_service', 'test_action_2', {'input_attribute': True})
        self.assertEqual({'another_value': 2}, response.body)

        self.assertEqual(1, stub_test_action_1.call_count)
        self.assertEqual({}, stub_test_action_1.call_body)
        self.assertEqual(1, stub_test_action_2.call_count)
        self.assertEqual({'input_attribute': True}, stub_test_action_2.call_body)
        stub_test_action_1.assert_called_once_with({})
        stub_test_action_2.assert_called_once_with({'input_attribute': True})

        assert input_arg in ('foo', 'bar')

    @stub_action('test_service', 'test_action_2')
    @stub_action('test_service', 'test_action_1')
    def _two_stubs_external_method_get_response(self, another_value, stub_test_action_1, stub_test_action_2):
        stub_test_action_1.return_value = {'value': -10}
        stub_test_action_2.return_value = {'another_value': another_value}

        try:
            return (
                self.client.call_action('test_service', 'test_action_1'),
                self.client.call_action('test_service', 'test_action_2', {'input_attribute': False})
            )
        finally:
            self.assertEqual(1, stub_test_action_1.call_count)
            self.assertEqual({}, stub_test_action_1.call_body)
            self.assertEqual(1, stub_test_action_2.call_count)
            self.assertEqual({'input_attribute': False}, stub_test_action_2.call_body)
            stub_test_action_1.assert_called_once_with({})
            stub_test_action_2.assert_called_once_with({'input_attribute': False})

    @pytest.mark.parametrize(('value2', ), ((-15, ), (-20, )))
    def test_two_stubs_same_service_as_decorated_external_method(self, value2):
        response1, response2 = self._two_stubs_external_method_get_response(value2)
        self.assertEqual({'value': -10}, response1.body)
        self.assertEqual({'another_value': value2}, response2.body)

    @stub_action('test_service', 'test_action_2')
    @stub_action('test_service', 'test_action_1')
    def test_two_stubs_same_service_as_decorator_multiple_calls_to_one(self, stub_test_action_1, stub_test_action_2):
        stub_test_action_1.return_value = {'value': 1}
        stub_test_action_2.side_effect = ({'another_value': 2}, {'third_value': 3})

        response = self.client.call_action('test_service', 'test_action_1')
        self.assertEqual({'value': 1}, response.body)

        response = self.client.call_action('test_service', 'test_action_2', {'input_attribute': True})
        self.assertEqual({'another_value': 2}, response.body)

        response = self.client.call_action('test_service', 'test_action_2', {'another_attribute': False})
        self.assertEqual({'third_value': 3}, response.body)

        self.assertEqual(1, stub_test_action_1.call_count)
        self.assertEqual({}, stub_test_action_1.call_body)
        self.assertEqual(2, stub_test_action_2.call_count)
        self.assertEqual({'another_attribute': False}, stub_test_action_2.call_body)
        self.assertEqual(({'input_attribute': True}, {'another_attribute': False}), stub_test_action_2.call_bodies)
        stub_test_action_1.assert_called_once_with({})
        stub_test_action_2.assert_has_calls([
            mock.call({'input_attribute': True}),
            mock.call({'another_attribute': False}),
        ])

    def test_stub_action_with_side_effect_mixed_exceptions_and_bodies_as_context_manager(self):
        with stub_action('foo', 'bar', side_effect=[MessageReceiveTimeout('No message received'), {'good': 'yes'}]):
            with pytest.raises(MessageReceiveTimeout):
                self.client.call_action('foo', 'bar')

            response = self.client.call_action('foo', 'bar')
            assert response.body == {'good': 'yes'}

    @stub_action('foo', 'bar')
    def test_stub_action_with_side_effect_mixed_exceptions_and_bodies_as_decorator(self, stub_foo_bar):
        stub_foo_bar.side_effect = [MessageReceiveTimeout('No message received'), {'good': 'yes'}]
        with pytest.raises(MessageReceiveTimeout):
            self.client.call_action('foo', 'bar')

        response = self.client.call_action('foo', 'bar')
        assert response.body == {'good': 'yes'}

    @stub_action('test_service', 'test_action_1')
    def test_two_stubs_same_service_split(self, stub_test_action_1):
        stub_test_action_1.return_value = {'value': 1}

        with stub_action('test_service', 'test_action_2') as stub_test_action_2:
            stub_test_action_2.return_value = {'another_value': 2}

            response = self.client.call_action('test_service', 'test_action_1')
            self.assertEqual({'value': 1}, response.body)

            response = self.client.call_action('test_service', 'test_action_2', {'input_attribute': True})
            self.assertEqual({'another_value': 2}, response.body)

        self.assertEqual(1, stub_test_action_1.call_count)
        self.assertEqual({}, stub_test_action_1.call_body)
        self.assertEqual(1, stub_test_action_2.call_count)
        self.assertEqual({'input_attribute': True}, stub_test_action_2.call_body)

    @stub_action('test_another_service', 'test_action_2')
    @stub_action('test_service', 'test_action_1')
    def test_two_stubs_different_services_as_decorator(self, stub_test_action_1, stub_test_action_2):
        stub_test_action_1.return_value = {'value': 1}
        stub_test_action_2.return_value = {'another_value': 2}

        response = self.client.call_action('test_service', 'test_action_1')
        self.assertEqual({'value': 1}, response.body)

        response = self.client.call_action('test_another_service', 'test_action_2', {'input_attribute': True})
        self.assertEqual({'another_value': 2}, response.body)

        self.assertEqual(1, stub_test_action_1.call_count)
        self.assertEqual({}, stub_test_action_1.call_body)
        self.assertEqual(1, stub_test_action_2.call_count)
        self.assertEqual({'input_attribute': True}, stub_test_action_2.call_body)

    @stub_action('test_service', 'test_action_1')
    def test_two_stubs_different_services_split(self, stub_test_action_1):
        stub_test_action_1.return_value = {'value': 1}

        with stub_action('test_another_service', 'test_action_2') as stub_test_action_2:
            stub_test_action_2.return_value = {'another_value': 2}

            response = self.client.call_action('test_service', 'test_action_1')
            self.assertEqual({'value': 1}, response.body)

            response = self.client.call_action('test_another_service', 'test_action_2', {'input_attribute': True})
            self.assertEqual({'another_value': 2}, response.body)

        self.assertEqual(1, stub_test_action_1.call_count)
        self.assertEqual({}, stub_test_action_1.call_body)
        self.assertEqual(1, stub_test_action_2.call_count)
        self.assertEqual({'input_attribute': True}, stub_test_action_2.call_body)

    @stub_action('test_service', 'test_action_1', body={'value': 1})
    def test_one_stub_as_decorator_with_real_call_handled(self, stub_test_action_1):
        response = self.client.call_action('test_service', 'test_action_1')
        self.assertEqual(response.body, {'value': 1})

        response = self.secondary_stub_client.call_action('cat', 'meow')
        self.assertEqual({'type': 'squeak'}, response.body)

        response = self.secondary_stub_client.call_action('dog', 'bark')
        self.assertEqual({'sound': 'woof'}, response.body)

        self.assertEqual(1, stub_test_action_1.call_count)
        self.assertEqual({}, stub_test_action_1.call_body)

    def test_one_stub_as_context_manager_with_real_call_handled(self):
        with stub_action('test_service', 'test_action_1', body={'value': 1}) as stub_test_action_1:
            response = self.client.call_action('test_service', 'test_action_1')
            self.assertEqual(response.body, {'value': 1})

            response = self.secondary_stub_client.call_action('cat', 'meow')
            self.assertEqual({'type': 'squeak'}, response.body)

            response = self.secondary_stub_client.call_action('dog', 'bark')
            self.assertEqual({'sound': 'woof'}, response.body)

        self.assertEqual(1, stub_test_action_1.call_count)
        self.assertEqual({}, stub_test_action_1.call_body)

    @stub_action('test_service', 'test_action_2')
    @mock.patch(__name__ + '._test_function', return_value=3)
    def test_as_decorator_with_patch_before(self, mock_randint, stub_test_action_2):
        stub_test_action_2.return_value = {'value': 99}

        response = self.client.call_actions(
            'test_service',
            [ActionRequest(action='test_action_1'), ActionRequest(action='test_action_2')],
        )

        self.assertEqual(2, len(response.actions))
        self.assertEqual({'value': 3}, response.actions[0].body)
        self.assertEqual({'value': 99}, response.actions[1].body)

        self.assertEqual(1, stub_test_action_2.call_count)
        self.assertEqual({}, stub_test_action_2.call_body)
        mock_randint.assert_called_once_with(0, 99)

    @mock.patch(__name__ + '._test_function', return_value=7)
    @stub_action('test_service', 'test_action_2')
    def test_as_decorator_with_patch_after(self, stub_test_action_2, mock_randint):
        stub_test_action_2.side_effect = ({'value': 122}, {'also': 157})

        response = self.client.call_actions(
            'test_service',
            [{'action': 'test_action_1'}, {'action': 'test_action_2'}, {'action': 'test_action_2'}],
        )

        self.assertEqual(3, len(response.actions))
        self.assertEqual({'value': 7}, response.actions[0].body)
        self.assertEqual({'value': 122}, response.actions[1].body)
        self.assertEqual({'also': 157}, response.actions[2].body)

        self.assertEqual(2, stub_test_action_2.call_count)
        self.assertEqual(({}, {}), stub_test_action_2.call_bodies)
        stub_test_action_2.assert_has_calls([mock.call({}), mock.call({})])
        mock_randint.assert_called_once_with(0, 99)

    def test_using_start_stop(self):
        action_stubber = stub_action('test_service', 'test_action_1')
        stubbed_action = action_stubber.start()
        stubbed_action.return_value = {'what about': 'this'}

        response = self.client.call_action('test_service', 'test_action_1', {'burton': 'guster', 'sean': 'spencer'})
        self.assertEqual({'what about': 'this'}, response.body)

        self.assertEqual(1, stubbed_action.call_count)
        self.assertEqual({'burton': 'guster', 'sean': 'spencer'}, stubbed_action.call_body)
        stubbed_action.assert_called_once_with({'burton': 'guster', 'sean': 'spencer'})
        action_stubber.stop()

    @stub_action('test_service', 'test_action_2', errors=[
        {'code': 'BAD_FOO', 'field': 'foo', 'message': 'Nope'},
    ])
    def test_mock_action_with_error_raises_exception(self, stub_test_action_2):
        with self.assertRaises(Client.CallActionError) as e:
            self.client.call_action('test_service', 'test_action_2', {'a': 'body'})

        self.assertEqual('BAD_FOO', e.exception.actions[0].errors[0].code)
        self.assertEqual('foo', e.exception.actions[0].errors[0].field)
        self.assertEqual('Nope', e.exception.actions[0].errors[0].message)

        self.assertEqual(1, stub_test_action_2.call_count)
        self.assertEqual({'a': 'body'}, stub_test_action_2.call_body)
        stub_test_action_2.assert_called_once_with({'a': 'body'})

    @stub_test_action()
    def test_stub_action_with_side_effect_callback(self, _stub_test_action):
        response = self.client.call_action('test_service', 'test_action', body={'id': 1, 'type': 'user'})
        self.assertEqual(response.body, {'id': 1, 'type': 'user'})

        response = self.client.call_action('test_service', 'test_action', body={'id': 2, 'type': 'admin'})
        self.assertEqual(response.body, {'id': 2, 'type': 'admin', 'extra': 'data'})

    @stub_test_action(add_extra=False)
    def test_stub_action_with_side_effect_callback_and_param(self, _stub_test_action):
        response = self.client.call_action('test_service', 'test_action', body={'id': 1, 'type': 'user'})
        self.assertEqual(response.body, {'id': 1, 'type': 'user'})

        response = self.client.call_action('test_service', 'test_action', body={'id': 2, 'type': 'admin'})
        self.assertEqual(response.body, {'id': 2, 'type': 'admin'})

    def test_stub_action_with_side_effect_callback_in_context_manager(self):
        with stub_test_action():
            response = self.client.call_action('test_service', 'test_action', body={'id': 1, 'type': 'user'})
        self.assertEqual(response.body, {'id': 1, 'type': 'user'})

        with stub_test_action():
            response = self.client.call_action('test_service', 'test_action', body={'id': 2, 'type': 'admin'})
        self.assertEqual(response.body, {'id': 2, 'type': 'admin', 'extra': 'data'})

    def test_stub_action_with_side_effect_callback_in_context_manager_and_param(self):
        with stub_test_action(add_extra=False):
            response = self.client.call_action('test_service', 'test_action', body={'id': 1, 'type': 'user'})
        self.assertEqual(response.body, {'id': 1, 'type': 'user'})

        with stub_test_action(add_extra=False):
            response = self.client.call_action('test_service', 'test_action', body={'id': 2, 'type': 'admin'})
        self.assertEqual(response.body, {'id': 2, 'type': 'admin'})

    @stub_action(
        'test_service',
        'test_action_2',
        side_effect=ActionError(errors=[Error(code='BAR_BAD', field='bar', message='Uh-uh')]),
    )
    def test_stub_action_with_error_side_effect_raises_exception(self, stub_test_action_2):
        with self.assertRaises(Client.CallActionError) as e:
            self.client.call_action('test_service', 'test_action_2', {'a': 'body'})

        self.assertEqual('BAR_BAD', e.exception.actions[0].errors[0].code)
        self.assertEqual('bar', e.exception.actions[0].errors[0].field)
        self.assertEqual('Uh-uh', e.exception.actions[0].errors[0].message)

        self.assertEqual(1, stub_test_action_2.call_count)
        self.assertEqual({'a': 'body'}, stub_test_action_2.call_body)
        stub_test_action_2.assert_called_once_with({'a': 'body'})

    @stub_action(
        'test_service',
        'test_action_2',
        side_effect=JobError(errors=[Error(code='BAR_BAD_JOB', message='Uh-uh job')]),
    )
    def test_stub_action_with_job_error_side_effect_raises_job_error_exception(self, stub_test_action_2):
        with self.assertRaises(Client.JobError) as e:
            self.client.call_action('test_service', 'test_action_2', {'a': 'body'})

        self.assertEqual('BAR_BAD_JOB', e.exception.errors[0].code)
        self.assertIsNone(e.exception.errors[0].field)
        self.assertEqual('Uh-uh job', e.exception.errors[0].message)

        self.assertEqual(1, stub_test_action_2.call_count)
        self.assertEqual({'a': 'body'}, stub_test_action_2.call_body)
        stub_test_action_2.assert_called_once_with({'a': 'body'})

    @stub_action('test_service', 'test_action_2')
    def test_mock_action_with_error_side_effect_raises_exception(self, stub_test_action_2):
        stub_test_action_2.side_effect = ActionError(errors=[Error(code='BAR_BAD', field='bar', message='Uh-uh')])

        with self.assertRaises(Client.CallActionError) as e:
            self.client.call_action('test_service', 'test_action_2', {'a': 'body'})

        self.assertEqual('BAR_BAD', e.exception.actions[0].errors[0].code)
        self.assertEqual('bar', e.exception.actions[0].errors[0].field)
        self.assertEqual('Uh-uh', e.exception.actions[0].errors[0].message)

        self.assertEqual(1, stub_test_action_2.call_count)
        self.assertEqual({'a': 'body'}, stub_test_action_2.call_body)
        stub_test_action_2.assert_called_once_with({'a': 'body'})

    @stub_action('test_service', 'test_action_2')
    def test_mock_action_with_job_error_side_effect_raises_job_error_exception(self, stub_test_action_2):
        stub_test_action_2.side_effect = JobError(errors=[Error(code='BAR_BAD_JOB', message='Uh-uh job')])

        with self.assertRaises(Client.JobError) as e:
            self.client.call_action('test_service', 'test_action_2', {'a': 'body'})

        self.assertEqual('BAR_BAD_JOB', e.exception.errors[0].code)
        self.assertIsNone(e.exception.errors[0].field)
        self.assertEqual('Uh-uh job', e.exception.errors[0].message)

        self.assertEqual(1, stub_test_action_2.call_count)
        self.assertEqual({'a': 'body'}, stub_test_action_2.call_body)
        stub_test_action_2.assert_called_once_with({'a': 'body'})

    @stub_action('test_service', 'test_action_2')
    def test_mock_action_with_job_error_response_raises_job_error_exception(self, stub_test_action_2):
        stub_test_action_2.return_value = JobResponse(errors=[Error(code='BAR_BAD_JOB', message='Uh-uh job')])

        with self.assertRaises(Client.JobError) as e:
            self.client.call_action('test_service', 'test_action_2', {'a': 'body'})

        self.assertEqual('BAR_BAD_JOB', e.exception.errors[0].code)
        self.assertIsNone(e.exception.errors[0].field)
        self.assertEqual('Uh-uh job', e.exception.errors[0].message)

        self.assertEqual(1, stub_test_action_2.call_count)
        self.assertEqual({'a': 'body'}, stub_test_action_2.call_body)
        stub_test_action_2.assert_called_once_with({'a': 'body'})

    @stub_action('test_service', 'test_action_2', errors=[
        {'code': 'INVALID_BAR', 'message': 'A bad message'},
    ])
    def test_multiple_actions_stop_on_error(self, stub_test_action_2):
        response = self.client.call_actions(
            'test_service',
            [
                ActionRequest(action='test_action_1'),
                ActionRequest(action='test_action_2'),
                ActionRequest(action='test_action_1'),
            ],
            raise_action_errors=False,
        )

        # Called 3 actions, but expected to stop after the error in the second action
        self.assertEqual(2, len(response.actions))
        self.assertEqual('INVALID_BAR', response.actions[1].errors[0].code)
        self.assertEqual('A bad message', response.actions[1].errors[0].message)
        self.assertTrue(stub_test_action_2.called)

    @stub_action('test_service', 'test_action_2', errors=[
        {'code': 'MISSING_BAZ', 'field': 'entity_id', 'message': 'Your entity ID was missing'},
    ])
    def test_multiple_actions_continue_on_error(self, mock_test_action_2):
        response = self.client.call_actions(
            'test_service',
            [{'action': 'test_action_1'}, {'action': 'test_action_2'}, {'action': 'test_action_1'}],
            raise_action_errors=False,
            continue_on_error=True,
        )

        # Called 3 actions, and expected all three of them to be called, even with the interrupting error
        self.assertEqual(3, len(response.actions))
        self.assertEqual('MISSING_BAZ', response.actions[1].errors[0].code)
        self.assertEqual('entity_id', response.actions[1].errors[0].field)
        self.assertEqual('Your entity ID was missing', response.actions[1].errors[0].message)
        self.assertTrue(mock_test_action_2.called)

    @stub_action('test_service', 'test_action_2', body={'three': 'four'})
    @stub_action('test_service', 'test_action_1', body={'one': 'two'})
    def test_two_stubs_with_parallel_calls_all_stubbed(self, stub_test_action_1, stub_test_action_2):
        job_responses = self.client.call_jobs_parallel(
            [
                {'service_name': 'test_service', 'actions': [{'action': 'test_action_1', 'body': {'a': 'b'}}]},
                {'service_name': 'test_service', 'actions': [{'action': 'test_action_2', 'body': {'c': 'd'}}]},
            ],
        )

        self.assertIsNotNone(job_responses)
        self.assertEqual(2, len(job_responses))
        self.assertEqual(1, len(job_responses[0].actions))
        self.assertEqual({'one': 'two'}, job_responses[0].actions[0].body)
        self.assertEqual(1, len(job_responses[1].actions))
        self.assertEqual({'three': 'four'}, job_responses[1].actions[0].body)

        stub_test_action_1.assert_called_once_with({'a': 'b'})
        stub_test_action_2.assert_called_once_with({'c': 'd'})

    @stub_action('test_service', 'test_action_2')
    @mock.patch(__name__ + '._test_function')
    def test_one_stub_with_parallel_calls(self, mock_randint, stub_test_action_2):
        mock_randint.side_effect = (42, 17, 31)
        stub_test_action_2.return_value = {'concert': 'tickets'}

        job_responses = self.client.call_jobs_parallel(
            [
                {'service_name': 'test_service', 'actions': [{'action': 'test_action_1'}]},
                {'service_name': 'test_service', 'actions': [
                    {'action': 'test_action_2', 'body': {'slide': 'rule'}},
                    {'action': 'test_action_1'},
                ]},
                {'service_name': 'test_service', 'actions': [{'action': 'test_action_1'}]},
            ],
        )

        self.assertIsNotNone(job_responses)
        self.assertEqual(3, len(job_responses))
        self.assertEqual(1, len(job_responses[0].actions))
        self.assertEqual({'value': 42}, job_responses[0].actions[0].body)
        self.assertEqual(2, len(job_responses[1].actions))
        self.assertEqual({'concert': 'tickets'}, job_responses[1].actions[0].body)
        self.assertEqual({'value': 17}, job_responses[1].actions[1].body)
        self.assertEqual(1, len(job_responses[2].actions))
        self.assertEqual({'value': 31}, job_responses[2].actions[0].body)

        stub_test_action_2.assert_called_once_with({'slide': 'rule'})

    @stub_action('test_service', 'test_action_2')
    @stub_action('test_service', 'test_action_1')
    def test_two_stubs_with_parallel_calls(self, stub_test_action_1, stub_test_action_2):
        stub_test_action_1.return_value = {'value': 1}
        stub_test_action_2.return_value = {'another_value': 2}

        job_responses = Client(dict(self.client.config, **_secondary_stub_client_settings)).call_jobs_parallel(
            [
                {'service_name': 'test_service', 'actions': [
                    {'action': 'test_action_1', 'body': {'input_attribute': True}},
                    {'action': 'test_action_2', 'body': {'another_variable': 'Cool'}},
                ]},
                {'service_name': 'cat', 'actions': [{'action': 'meow'}]},
                {'service_name': 'dog', 'actions': [{'action': 'bark'}]},
                {'service_name': 'test_service', 'actions': [{'action': 'does_not_exist'}]},
            ],
            raise_action_errors=False,
        )

        self.assertIsNotNone(job_responses)
        self.assertEqual(4, len(job_responses))
        self.assertEqual(2, len(job_responses[0].actions))
        self.assertEqual({'value': 1}, job_responses[0].actions[0].body)
        self.assertEqual({'another_value': 2}, job_responses[0].actions[1].body)
        self.assertEqual(1, len(job_responses[1].actions))
        self.assertEqual({'type': 'squeak'}, job_responses[1].actions[0].body)
        self.assertEqual(1, len(job_responses[2].actions))
        self.assertEqual({'sound': 'woof'}, job_responses[2].actions[0].body)
        self.assertEqual(1, len(job_responses[3].actions))
        self.assertEqual(
            [Error(
                code='UNKNOWN',
                message='The action "does_not_exist" was not found on this server.',
                field='action',
                is_caller_error=True,
            )],
            job_responses[3].actions[0].errors
        )

        stub_test_action_1.assert_called_once_with({'input_attribute': True})
        stub_test_action_2.assert_called_once_with({'another_variable': 'Cool'})

    @stub_action('test_service', 'test_action_2', body={'three': 'four'})
    @stub_action('test_service', 'test_action_1')
    def test_two_stubs_with_parallel_calls_and_job_response_errors_raised(self, stub_test_action_1, stub_test_action_2):
        stub_test_action_1.return_value = JobResponse(errors=[Error(code='BAD_JOB', message='You are a bad job')])

        with self.assertRaises(self.client.JobError) as error_context:
            self.client.call_jobs_parallel(
                [
                    {'service_name': 'test_service', 'actions': [{'action': 'test_action_1', 'body': {'a': 'b'}}]},
                    {'service_name': 'test_service', 'actions': [{'action': 'test_action_2', 'body': {'c': 'd'}}]},
                ],
            )

        self.assertEqual([Error(code='BAD_JOB', message='You are a bad job')], error_context.exception.errors)

        stub_test_action_1.assert_called_once_with({'a': 'b'})
        stub_test_action_2.assert_called_once_with({'c': 'd'})

    @stub_action('test_service', 'test_action_2', body={'three': 'four'})
    @stub_action(
        'test_service',
        'test_action_1',
        side_effect=JobError(errors=[Error(code='BAD_JOB', message='You are a bad job')]),
    )
    def test_stub_action_with_two_stubs_with_parallel_calls_and_job_errors_not_raised(
        self,
        stub_test_action_1,
        stub_test_action_2,
    ):
        job_responses = self.client.call_jobs_parallel(
            [
                {'service_name': 'test_service', 'actions': [{'action': 'test_action_1', 'body': {'a': 'b'}}]},
                {'service_name': 'test_service', 'actions': [{'action': 'test_action_2', 'body': {'c': 'd'}}]},
            ],
            raise_job_errors=False,
        )

        self.assertIsNotNone(job_responses)
        self.assertEqual(2, len(job_responses))
        self.assertEqual(0, len(job_responses[0].actions))
        self.assertEqual([Error(code='BAD_JOB', message='You are a bad job')], job_responses[0].errors)
        self.assertEqual(1, len(job_responses[1].actions))
        self.assertEqual({'three': 'four'}, job_responses[1].actions[0].body)

        stub_test_action_1.assert_called_once_with({'a': 'b'})
        stub_test_action_2.assert_called_once_with({'c': 'd'})

    @stub_action('test_service', 'test_action_2', body={'three': 'four'})
    @stub_action(
        'test_service',
        'test_action_1',
        side_effect=ActionError(errors=[Error(code='BAD_ACTION', message='You are a bad actor')]),
    )
    def test_stub_action_with_two_stubs_with_parallel_calls_and_action_errors_raised(
        self,
        stub_test_action_1,
        stub_test_action_2,
    ):
        with self.assertRaises(self.client.CallActionError) as error_context:
            self.client.call_jobs_parallel(
                [
                    {'service_name': 'test_service', 'actions': [{'action': 'test_action_1', 'body': {'a': 'b'}}]},
                    {'service_name': 'test_service', 'actions': [{'action': 'test_action_2', 'body': {'c': 'd'}}]},
                ],
            )

        self.assertEqual(
            [Error(code='BAD_ACTION', message='You are a bad actor', is_caller_error=True)],
            error_context.exception.actions[0].errors,
        )

        stub_test_action_1.assert_called_once_with({'a': 'b'})
        stub_test_action_2.assert_called_once_with({'c': 'd'})

    @stub_action('test_service', 'test_action_2', body={'three': 'four'})
    @stub_action('test_service', 'test_action_1')
    def test_two_stubs_with_parallel_calls_and_job_errors_not_raised(self, stub_test_action_1, stub_test_action_2):
        stub_test_action_1.side_effect = JobError(errors=[Error(code='BAD_JOB', message='You are a bad job')])

        job_responses = self.client.call_jobs_parallel(
            [
                {'service_name': 'test_service', 'actions': [{'action': 'test_action_1', 'body': {'a': 'b'}}]},
                {'service_name': 'test_service', 'actions': [{'action': 'test_action_2', 'body': {'c': 'd'}}]},
            ],
            raise_job_errors=False,
        )

        self.assertIsNotNone(job_responses)
        self.assertEqual(2, len(job_responses))
        self.assertEqual(0, len(job_responses[0].actions))
        self.assertEqual([Error(code='BAD_JOB', message='You are a bad job')], job_responses[0].errors)
        self.assertEqual(1, len(job_responses[1].actions))
        self.assertEqual({'three': 'four'}, job_responses[1].actions[0].body)

        stub_test_action_1.assert_called_once_with({'a': 'b'})
        stub_test_action_2.assert_called_once_with({'c': 'd'})

    @stub_action('test_service', 'test_action_2', body={'three': 'four'})
    @stub_action('test_service', 'test_action_1')
    def test_two_stubs_with_parallel_calls_and_action_errors_raised(self, stub_test_action_1, stub_test_action_2):
        stub_test_action_1.side_effect = ActionError(errors=[Error(code='BAD_ACTION', message='You are a bad actor')])

        with self.assertRaises(self.client.CallActionError) as error_context:
            self.client.call_jobs_parallel(
                [
                    {'service_name': 'test_service', 'actions': [{'action': 'test_action_1', 'body': {'a': 'b'}}]},
                    {'service_name': 'test_service', 'actions': [{'action': 'test_action_2', 'body': {'c': 'd'}}]},
                ],
            )

        self.assertEqual(
            [Error(code='BAD_ACTION', message='You are a bad actor', is_caller_error=True)],
            error_context.exception.actions[0].errors,
        )

        stub_test_action_1.assert_called_once_with({'a': 'b'})
        stub_test_action_2.assert_called_once_with({'c': 'd'})

    @stub_action('test_service', 'test_action_2', body={'three': 'four'})
    @stub_action('test_service', 'test_action_1')
    def test_two_stubs_with_parallel_calls_and_action_response_errors_not_raised(
        self,
        stub_test_action_1,
        stub_test_action_2,
    ):
        stub_test_action_1.return_value = ActionResponse(
            action='test_action_1',
            errors=[Error(code='BAD_ACTION', message='You are a bad actor')],
        )

        job_responses = self.client.call_jobs_parallel(
            [
                {'service_name': 'test_service', 'actions': [{'action': 'test_action_1', 'body': {'a': 'b'}}]},
                {'service_name': 'test_service', 'actions': [{'action': 'test_action_2', 'body': {'c': 'd'}}]},
            ],
            raise_action_errors=False,
        )

        self.assertIsNotNone(job_responses)
        self.assertEqual(2, len(job_responses))
        self.assertEqual(1, len(job_responses[0].actions))
        self.assertEqual([Error(code='BAD_ACTION', message='You are a bad actor')], job_responses[0].actions[0].errors)
        self.assertEqual(1, len(job_responses[1].actions))
        self.assertEqual({'three': 'four'}, job_responses[1].actions[0].body)

        stub_test_action_1.assert_called_once_with({'a': 'b'})
        stub_test_action_2.assert_called_once_with({'c': 'd'})

    @stub_action('test_service', 'test_action_1', body={'food': 'chicken'})
    def test_send_receive_one_stub_simple(self, stub_test_action_1):
        request_id = self.client.send_request('test_service', [{'action': 'test_action_1', 'body': {'menu': 'look'}}])

        self.assertIsNotNone(request_id)

        responses = list(self.client.get_all_responses('test_service'))
        self.assertEqual(1, len(responses))

        received_request_id, response = responses[0]
        self.assertEqual(request_id, received_request_id)
        self.assertIsNotNone(response)
        self.assertEqual([], response.errors)
        self.assertEqual(1, len(response.actions))
        self.assertEqual([], response.actions[0].errors)
        self.assertEqual({'food': 'chicken'}, response.actions[0].body)

        stub_test_action_1.assert_called_once_with({'menu': 'look'})

    @stub_action('test_service', 'test_action_1')
    def test_send_receive_one_stub_multiple_calls(self, stub_test_action_1):
        stub_test_action_1.side_effect = ({'look': 'menu'}, {'pepperoni': 'pizza'}, {'cheese': 'pizza'})

        request_id1 = self.client.send_request(
            'test_service',
            [
                {'action': 'test_action_1', 'body': {'menu': 'look'}},
                {'action': 'test_action_1', 'body': {'pizza': 'pepperoni'}},
            ]
        )
        request_id2 = self.client.send_request(
            'test_service',
            [
                {'action': 'test_action_1', 'body': {'pizza': 'cheese'}},
            ]
        )

        self.assertIsNotNone(request_id1)
        self.assertIsNotNone(request_id2)

        responses = list(self.client.get_all_responses('test_service'))
        self.assertEqual(2, len(responses))

        response_dict = {k: v for k, v in responses}
        self.assertIn(request_id1, response_dict)
        self.assertIn(request_id2, response_dict)

        response = response_dict[request_id1]
        self.assertIsNotNone(response)
        self.assertEqual([], response.errors)
        self.assertEqual(2, len(response.actions))
        self.assertEqual([], response.actions[0].errors)
        self.assertEqual({'look': 'menu'}, response.actions[0].body)
        self.assertEqual({'pepperoni': 'pizza'}, response.actions[1].body)

        response = response_dict[request_id2]
        self.assertIsNotNone(response)
        self.assertEqual([], response.errors)
        self.assertEqual(1, len(response.actions))
        self.assertEqual([], response.actions[0].errors)
        self.assertEqual({'cheese': 'pizza'}, response.actions[0].body)

        stub_test_action_1.assert_has_calls(
            [
                mock.call({'menu': 'look'}),
                mock.call({'pizza': 'pepperoni'}),
                mock.call({'pizza': 'cheese'}),
            ],
            any_order=True,
        )

    @stub_action('test_service', 'test_action_1')
    def test_send_receive_one_stub_one_real_call_mixture(self, stub_test_action_1):
        stub_test_action_1.side_effect = (
            ActionResponse(action='does not matter', body={'look': 'menu'}),
            ActionResponse(action='no', errors=[Error(code='WEIRD', field='pizza', message='Weird error about pizza')]),
            ActionError(errors=[Error(code='COOL', message='Another error')]),
        )

        actions = [
            {'action': 'test_action_1', 'body': {'menu': 'look'}},
            {'action': 'test_action_2'},
            {'action': 'test_action_1', 'body': {'pizza': 'pepperoni'}},
            {'action': 'test_action_2'},
            {'action': 'test_action_2'},
        ]  # type: List[Dict[six.text_type, Any]]

        request_id1 = self.client.send_request('test_service', actions, continue_on_error=True)
        request_id2 = self.client.send_request(
            'test_service',
            [
                {'action': 'test_action_1', 'body': {'pizza': 'cheese'}},
            ]
        )
        request_id3 = self.client.send_request(
            'test_service',
            [
                {'action': 'test_action_2'},
            ]
        )

        self.assertIsNotNone(request_id1)
        self.assertIsNotNone(request_id2)
        self.assertIsNotNone(request_id3)

        responses = list(self.client.get_all_responses('test_service'))
        self.assertEqual(3, len(responses))

        response_dict = {k: v for k, v in responses}
        self.assertIn(request_id1, response_dict)
        self.assertIn(request_id2, response_dict)
        self.assertIn(request_id3, response_dict)

        response = response_dict[request_id1]
        self.assertIsNotNone(response)
        self.assertEqual([], response.errors)
        self.assertEqual(5, len(response.actions))
        self.assertEqual([], response.actions[0].errors)
        self.assertEqual({'look': 'menu'}, response.actions[0].body)
        self.assertEqual([], response.actions[1].errors)
        self.assertEqual({'value': 0}, response.actions[1].body)
        self.assertEqual(
            [Error(code='WEIRD', field='pizza', message='Weird error about pizza')],
            response.actions[2].errors,
        )
        self.assertEqual([], response.actions[3].errors)
        self.assertEqual({'value': 0}, response.actions[3].body)
        self.assertEqual([], response.actions[4].errors)
        self.assertEqual({'value': 0}, response.actions[4].body)

        response = response_dict[request_id2]
        self.assertIsNotNone(response)
        self.assertEqual([], response.errors)
        self.assertEqual(1, len(response.actions))
        self.assertEqual(
            [Error(code='COOL', message='Another error', is_caller_error=True)],
            response.actions[0].errors,
        )

        response = response_dict[request_id3]
        self.assertIsNotNone(response)
        self.assertEqual([], response.errors)
        self.assertEqual(1, len(response.actions))
        self.assertEqual([], response.actions[0].errors)
        self.assertEqual({'value': 0}, response.actions[0].body)

        stub_test_action_1.assert_has_calls(
            [
                mock.call({'menu': 'look'}),
                mock.call({'pizza': 'pepperoni'}),
                mock.call({'pizza': 'cheese'}),
            ],
            any_order=True,
        )


class TestStubActionUnitTestCase(UnitTestServerTestCase):
    server_class = _TestServiceServer
    server_settings = {}  # type: SettingsData

    def setUp(self):
        super(TestStubActionUnitTestCase, self).setUp()

        self.secondary_stub_client = Client(_secondary_stub_client_settings)

    @stub_action('test_service', 'test_action_1')
    def test_one_stub_as_decorator(self, stub_test_action_1):
        stub_test_action_1.return_value = {'value': 1}

        response = self.client.call_action('test_service', 'test_action_1')
        self.assertEqual({'value': 1}, response.body)

        self.assertEqual(1, stub_test_action_1.call_count)
        self.assertEqual({}, stub_test_action_1.call_body)
        stub_test_action_1.assert_called_once_with({})

    @parameterized.expand((('foo', ), ('bar', )))
    @stub_action('test_service', 'test_action_1')
    def test_one_stub_as_decorator_with_3rd_party_parametrize(self, input_arg, stub_test_action_1):
        stub_test_action_1.return_value = {'value': 1}

        response = self.client.call_action('test_service', 'test_action_1')
        self.assertEqual({'value': 1}, response.body)

        self.assertEqual(1, stub_test_action_1.call_count)
        self.assertEqual({}, stub_test_action_1.call_body)
        stub_test_action_1.assert_called_once_with({})

        assert input_arg in ('foo', 'bar')

    @stub_action('test_service', 'test_action_1')
    def _external_method_get_response(self, stub_test_action_1):
        stub_test_action_1.return_value = {'value': -5}

        try:
            return self.client.call_action('test_service', 'test_action_1')
        finally:
            self.assertEqual(1, stub_test_action_1.call_count)
            self.assertEqual({}, stub_test_action_1.call_body)
            stub_test_action_1.assert_called_once_with({})

    def test_one_stub_as_decorated_external_method(self):
        response = self._external_method_get_response()
        self.assertEqual({'value': -5}, response.body)

    def test_one_stub_as_context_manager(self):
        with stub_action('test_service', 'test_action_1') as stub_test_action_1:
            stub_test_action_1.return_value = {'value': 1}

            response = self.client.call_action('test_service', 'test_action_1')

        self.assertEqual({'value': 1}, response.body)

        self.assertEqual(1, stub_test_action_1.call_count)
        self.assertEqual({}, stub_test_action_1.call_body)
        stub_test_action_1.assert_called_once_with({})

    @stub_action('test_service', 'test_action_1', body={'value': 1})
    def test_one_stub_as_decorator_with_body(self, stub_test_action_1):
        response = self.client.call_action('test_service', 'test_action_1')
        self.assertEqual({'value': 1}, response.body)

        self.assertEqual(1, stub_test_action_1.call_count)
        self.assertEqual({}, stub_test_action_1.call_body)
        stub_test_action_1.assert_called_once_with({})

    def test_one_stub_as_context_manager_with_body(self):
        with stub_action('test_service', 'test_action_1', body={'value': 1}) as stub_test_action_1:
            response = self.client.call_action('test_service', 'test_action_1')

        self.assertEqual({'value': 1}, response.body)

        self.assertEqual(1, stub_test_action_1.call_count)
        self.assertEqual({}, stub_test_action_1.call_body)
        stub_test_action_1.assert_called_once_with({})

    def test_one_stub_duplicated_as_context_manager(self):
        original_client_send_request = Client.send_request
        original_client_get_all_responses = Client.get_all_responses

        stub = stub_action('test_service', 'test_action_1', body={'value': 1})

        with stub as stub_test_action_1, stub as second_stub_test_action_1:
            response = self.client.call_action('test_service', 'test_action_1')

        # Check stub is correctly reverted
        for client_func, original_func in (
            (Client.send_request, original_client_send_request),
            (Client.get_all_responses, original_client_get_all_responses),
        ):
            self.assertTrue(
                six.get_unbound_function(client_func) is six.get_unbound_function(original_func)  # type: ignore
            )

        self.assertEqual({'value': 1}, response.body)

        self.assertTrue(stub_test_action_1 is second_stub_test_action_1)
        self.assertEqual(1, stub_test_action_1.call_count)
        self.assertEqual({}, stub_test_action_1.call_body)
        stub_test_action_1.assert_called_once_with({})

    @stub_action('test_service', 'test_action_2')
    @stub_action('test_service', 'test_action_1')
    def test_two_stubs_same_service_as_decorator(self, stub_test_action_1, stub_test_action_2):
        stub_test_action_1.return_value = {'value': 1}
        stub_test_action_2.return_value = {'another_value': 2}

        response = self.client.call_action('test_service', 'test_action_1')
        self.assertEqual({'value': 1}, response.body)

        response = self.client.call_action('test_service', 'test_action_2', {'input_attribute': True})
        self.assertEqual({'another_value': 2}, response.body)

        self.assertEqual(1, stub_test_action_1.call_count)
        self.assertEqual({}, stub_test_action_1.call_body)
        self.assertEqual(1, stub_test_action_2.call_count)
        self.assertEqual({'input_attribute': True}, stub_test_action_2.call_body)
        stub_test_action_1.assert_called_once_with({})
        stub_test_action_2.assert_called_once_with({'input_attribute': True})

    @parameterized.expand((('foo',), ('bar',)))
    @stub_action('test_service', 'test_action_2')
    @stub_action('test_service', 'test_action_1')
    def test_two_stubs_same_service_as_decorator_with_3rd_party_parametrize(
        self,
        input_arg,
        stub_test_action_1,
        stub_test_action_2,
    ):
        stub_test_action_1.return_value = {'value': 1}
        stub_test_action_2.return_value = {'another_value': 2}

        response = self.client.call_action('test_service', 'test_action_1')
        self.assertEqual({'value': 1}, response.body)

        response = self.client.call_action('test_service', 'test_action_2', {'input_attribute': True})
        self.assertEqual({'another_value': 2}, response.body)

        self.assertEqual(1, stub_test_action_1.call_count)
        self.assertEqual({}, stub_test_action_1.call_body)
        self.assertEqual(1, stub_test_action_2.call_count)
        self.assertEqual({'input_attribute': True}, stub_test_action_2.call_body)
        stub_test_action_1.assert_called_once_with({})
        stub_test_action_2.assert_called_once_with({'input_attribute': True})

        assert input_arg in ('foo', 'bar')

    @stub_action('test_service', 'test_action_2')
    @stub_action('test_service', 'test_action_1')
    def _two_stubs_external_method_get_response(self, another_value, stub_test_action_1, stub_test_action_2):
        stub_test_action_1.return_value = {'value': -10}
        stub_test_action_2.return_value = {'another_value': another_value}

        try:
            return (
                self.client.call_action('test_service', 'test_action_1'),
                self.client.call_action('test_service', 'test_action_2', {'input_attribute': False})
            )
        finally:
            self.assertEqual(1, stub_test_action_1.call_count)
            self.assertEqual({}, stub_test_action_1.call_body)
            self.assertEqual(1, stub_test_action_2.call_count)
            self.assertEqual({'input_attribute': False}, stub_test_action_2.call_body)
            stub_test_action_1.assert_called_once_with({})
            stub_test_action_2.assert_called_once_with({'input_attribute': False})

    @parameterized.expand(((-15,), (-20,)))
    def test_two_stubs_same_service_as_decorated_external_method(self, value2):
        response1, response2 = self._two_stubs_external_method_get_response(value2)
        self.assertEqual({'value': -10}, response1.body)
        self.assertEqual({'another_value': value2}, response2.body)

    @stub_action('test_service', 'test_action_2')
    @stub_action('test_service', 'test_action_1')
    def test_two_stubs_same_service_as_decorator_multiple_calls_to_one(self, stub_test_action_1, stub_test_action_2):
        stub_test_action_1.return_value = {'value': 1}
        stub_test_action_2.side_effect = ({'another_value': 2}, {'third_value': 3})

        response = self.client.call_action('test_service', 'test_action_1')
        self.assertEqual({'value': 1}, response.body)

        response = self.client.call_action('test_service', 'test_action_2', {'input_attribute': True})
        self.assertEqual({'another_value': 2}, response.body)

        response = self.client.call_action('test_service', 'test_action_2', {'another_attribute': False})
        self.assertEqual({'third_value': 3}, response.body)

        self.assertEqual(1, stub_test_action_1.call_count)
        self.assertEqual({}, stub_test_action_1.call_body)
        self.assertEqual(2, stub_test_action_2.call_count)
        self.assertEqual({'another_attribute': False}, stub_test_action_2.call_body)
        self.assertEqual(({'input_attribute': True}, {'another_attribute': False}), stub_test_action_2.call_bodies)
        stub_test_action_1.assert_called_once_with({})
        stub_test_action_2.assert_has_calls([
            mock.call({'input_attribute': True}),
            mock.call({'another_attribute': False}),
        ])

    def test_stub_action_with_side_effect_mixed_exceptions_and_bodies_as_context_manager(self):
        with stub_action('foo', 'bar', side_effect=[MessageReceiveTimeout('No message received'), {'good': 'yes'}]):
            with pytest.raises(MessageReceiveTimeout):
                self.client.call_action('foo', 'bar')

            response = self.client.call_action('foo', 'bar')
            assert response.body == {'good': 'yes'}

    @stub_action('foo', 'bar')
    def test_stub_action_with_side_effect_mixed_exceptions_and_bodies_as_decorator(self, stub_foo_bar):
        stub_foo_bar.side_effect = [MessageReceiveTimeout('No message received'), {'good': 'yes'}]
        with pytest.raises(MessageReceiveTimeout):
            self.client.call_action('foo', 'bar')

        response = self.client.call_action('foo', 'bar')
        assert response.body == {'good': 'yes'}

    @stub_action('test_service', 'test_action_1')
    def test_two_stubs_same_service_split(self, stub_test_action_1):
        stub_test_action_1.return_value = {'value': 1}

        with stub_action('test_service', 'test_action_2') as stub_test_action_2:
            stub_test_action_2.return_value = {'another_value': 2}

            response = self.client.call_action('test_service', 'test_action_1')
            self.assertEqual({'value': 1}, response.body)

            response = self.client.call_action('test_service', 'test_action_2', {'input_attribute': True})
            self.assertEqual({'another_value': 2}, response.body)

        self.assertEqual(1, stub_test_action_1.call_count)
        self.assertEqual({}, stub_test_action_1.call_body)
        self.assertEqual(1, stub_test_action_2.call_count)
        self.assertEqual({'input_attribute': True}, stub_test_action_2.call_body)

    @stub_action('test_another_service', 'test_action_2')
    @stub_action('test_service', 'test_action_1')
    def test_two_stubs_different_services_as_decorator(self, stub_test_action_1, stub_test_action_2):
        stub_test_action_1.return_value = {'value': 1}
        stub_test_action_2.return_value = {'another_value': 2}

        response = self.client.call_action('test_service', 'test_action_1')
        self.assertEqual({'value': 1}, response.body)

        response = self.client.call_action('test_another_service', 'test_action_2', {'input_attribute': True})
        self.assertEqual({'another_value': 2}, response.body)

        self.assertEqual(1, stub_test_action_1.call_count)
        self.assertEqual({}, stub_test_action_1.call_body)
        self.assertEqual(1, stub_test_action_2.call_count)
        self.assertEqual({'input_attribute': True}, stub_test_action_2.call_body)

    @stub_action('test_service', 'test_action_1')
    def test_two_stubs_different_services_split(self, stub_test_action_1):
        stub_test_action_1.return_value = {'value': 1}

        with stub_action('test_another_service', 'test_action_2') as stub_test_action_2:
            stub_test_action_2.return_value = {'another_value': 2}

            response = self.client.call_action('test_service', 'test_action_1')
            self.assertEqual({'value': 1}, response.body)

            response = self.client.call_action('test_another_service', 'test_action_2', {'input_attribute': True})
            self.assertEqual({'another_value': 2}, response.body)

        self.assertEqual(1, stub_test_action_1.call_count)
        self.assertEqual({}, stub_test_action_1.call_body)
        self.assertEqual(1, stub_test_action_2.call_count)
        self.assertEqual({'input_attribute': True}, stub_test_action_2.call_body)

    @stub_action('test_service', 'test_action_1', body={'value': 1})
    def test_one_stub_as_decorator_with_real_call_handled(self, stub_test_action_1):
        response = self.client.call_action('test_service', 'test_action_1')
        self.assertEqual(response.body, {'value': 1})

        response = self.secondary_stub_client.call_action('cat', 'meow')
        self.assertEqual({'type': 'squeak'}, response.body)

        response = self.secondary_stub_client.call_action('dog', 'bark')
        self.assertEqual({'sound': 'woof'}, response.body)

        self.assertEqual(1, stub_test_action_1.call_count)
        self.assertEqual({}, stub_test_action_1.call_body)

    def test_one_stub_as_context_manager_with_real_call_handled(self):
        with stub_action('test_service', 'test_action_1', body={'value': 1}) as stub_test_action_1:
            response = self.client.call_action('test_service', 'test_action_1')
            self.assertEqual(response.body, {'value': 1})

            response = self.secondary_stub_client.call_action('cat', 'meow')
            self.assertEqual({'type': 'squeak'}, response.body)

            response = self.secondary_stub_client.call_action('dog', 'bark')
            self.assertEqual({'sound': 'woof'}, response.body)

        self.assertEqual(1, stub_test_action_1.call_count)
        self.assertEqual({}, stub_test_action_1.call_body)

    @stub_action('test_service', 'test_action_2')
    @mock.patch(__name__ + '._test_function', return_value=3)
    def test_as_decorator_with_patch_before(self, mock_randint, stub_test_action_2):
        stub_test_action_2.return_value = {'value': 99}

        response = self.client.call_actions(
            'test_service',
            [ActionRequest(action='test_action_1'), ActionRequest(action='test_action_2')],
        )

        self.assertEqual(2, len(response.actions))
        self.assertEqual({'value': 3}, response.actions[0].body)
        self.assertEqual({'value': 99}, response.actions[1].body)

        self.assertEqual(1, stub_test_action_2.call_count)
        self.assertEqual({}, stub_test_action_2.call_body)
        mock_randint.assert_called_once_with(0, 99)

    @mock.patch(__name__ + '._test_function', return_value=7)
    @stub_action('test_service', 'test_action_2')
    def test_as_decorator_with_patch_after(self, stub_test_action_2, mock_randint):
        stub_test_action_2.side_effect = ({'value': 122}, {'also': 157})

        response = self.client.call_actions(
            'test_service',
            [{'action': 'test_action_1'}, {'action': 'test_action_2'}, {'action': 'test_action_2'}],
        )

        self.assertEqual(3, len(response.actions))
        self.assertEqual({'value': 7}, response.actions[0].body)
        self.assertEqual({'value': 122}, response.actions[1].body)
        self.assertEqual({'also': 157}, response.actions[2].body)

        self.assertEqual(2, stub_test_action_2.call_count)
        self.assertEqual(({}, {}), stub_test_action_2.call_bodies)
        stub_test_action_2.assert_has_calls([mock.call({}), mock.call({})])
        mock_randint.assert_called_once_with(0, 99)

    def test_using_start_stop(self):
        action_stubber = stub_action('test_service', 'test_action_1')
        stubbed_action = action_stubber.start()
        stubbed_action.return_value = {'what about': 'this'}

        response = self.client.call_action('test_service', 'test_action_1', {'burton': 'guster', 'sean': 'spencer'})
        self.assertEqual({'what about': 'this'}, response.body)

        self.assertEqual(1, stubbed_action.call_count)
        self.assertEqual({'burton': 'guster', 'sean': 'spencer'}, stubbed_action.call_body)
        stubbed_action.assert_called_once_with({'burton': 'guster', 'sean': 'spencer'})
        action_stubber.stop()

    @stub_action('test_service', 'test_action_2', errors=[
        {'code': 'BAD_FOO', 'field': 'foo', 'message': 'Nope'},
    ])
    def test_mock_action_with_error_raises_exception(self, stub_test_action_2):
        with self.assertRaises(Client.CallActionError) as e:
            self.client.call_action('test_service', 'test_action_2', {'a': 'body'})

        self.assertEqual('BAD_FOO', e.exception.actions[0].errors[0].code)
        self.assertEqual('foo', e.exception.actions[0].errors[0].field)
        self.assertEqual('Nope', e.exception.actions[0].errors[0].message)

        self.assertEqual(1, stub_test_action_2.call_count)
        self.assertEqual({'a': 'body'}, stub_test_action_2.call_body)
        stub_test_action_2.assert_called_once_with({'a': 'body'})

    @stub_test_action()
    def test_stub_action_with_side_effect_callback(self, _stub_test_action):
        response = self.client.call_action('test_service', 'test_action', body={'id': 1, 'type': 'user'})
        self.assertEqual(response.body, {'id': 1, 'type': 'user'})

        response = self.client.call_action('test_service', 'test_action', body={'id': 2, 'type': 'admin'})
        self.assertEqual(response.body, {'id': 2, 'type': 'admin', 'extra': 'data'})

    @stub_test_action(add_extra=False)
    def test_stub_action_with_side_effect_callback_and_param(self, _stub_test_action):
        response = self.client.call_action('test_service', 'test_action', body={'id': 1, 'type': 'user'})
        self.assertEqual(response.body, {'id': 1, 'type': 'user'})

        response = self.client.call_action('test_service', 'test_action', body={'id': 2, 'type': 'admin'})
        self.assertEqual(response.body, {'id': 2, 'type': 'admin'})

    def test_stub_action_with_side_effect_callback_in_context_manager(self):
        with stub_test_action():
            response = self.client.call_action('test_service', 'test_action', body={'id': 1, 'type': 'user'})
        self.assertEqual(response.body, {'id': 1, 'type': 'user'})

        with stub_test_action():
            response = self.client.call_action('test_service', 'test_action', body={'id': 2, 'type': 'admin'})
        self.assertEqual(response.body, {'id': 2, 'type': 'admin', 'extra': 'data'})

    def test_stub_action_with_side_effect_callback_in_context_manager_and_param(self):
        with stub_test_action(add_extra=False):
            response = self.client.call_action('test_service', 'test_action', body={'id': 1, 'type': 'user'})
        self.assertEqual(response.body, {'id': 1, 'type': 'user'})

        with stub_test_action(add_extra=False):
            response = self.client.call_action('test_service', 'test_action', body={'id': 2, 'type': 'admin'})
        self.assertEqual(response.body, {'id': 2, 'type': 'admin'})

    @stub_action(
        'test_service',
        'test_action_2',
        side_effect=ActionError(errors=[Error(code='BAR_BAD', field='bar', message='Uh-uh')]),
    )
    def test_stub_action_with_error_side_effect_raises_exception(self, stub_test_action_2):
        with self.assertRaises(Client.CallActionError) as e:
            self.client.call_action('test_service', 'test_action_2', {'a': 'body'})

        self.assertEqual('BAR_BAD', e.exception.actions[0].errors[0].code)
        self.assertEqual('bar', e.exception.actions[0].errors[0].field)
        self.assertEqual('Uh-uh', e.exception.actions[0].errors[0].message)

        self.assertEqual(1, stub_test_action_2.call_count)
        self.assertEqual({'a': 'body'}, stub_test_action_2.call_body)
        stub_test_action_2.assert_called_once_with({'a': 'body'})

    @stub_action(
        'test_service',
        'test_action_2',
        side_effect=JobError(errors=[Error(code='BAR_BAD_JOB', message='Uh-uh job')]),
    )
    def test_stub_action_with_job_error_side_effect_raises_job_error_exception(self, stub_test_action_2):
        with self.assertRaises(Client.JobError) as e:
            self.client.call_action('test_service', 'test_action_2', {'a': 'body'})

        self.assertEqual('BAR_BAD_JOB', e.exception.errors[0].code)
        self.assertIsNone(e.exception.errors[0].field)
        self.assertEqual('Uh-uh job', e.exception.errors[0].message)

        self.assertEqual(1, stub_test_action_2.call_count)
        self.assertEqual({'a': 'body'}, stub_test_action_2.call_body)
        stub_test_action_2.assert_called_once_with({'a': 'body'})

    @stub_action('test_service', 'test_action_2')
    def test_mock_action_with_error_side_effect_raises_exception(self, stub_test_action_2):
        stub_test_action_2.side_effect = ActionError(errors=[Error(code='BAR_BAD', field='bar', message='Uh-uh')])

        with self.assertRaises(Client.CallActionError) as e:
            self.client.call_action('test_service', 'test_action_2', {'a': 'body'})

        self.assertEqual('BAR_BAD', e.exception.actions[0].errors[0].code)
        self.assertEqual('bar', e.exception.actions[0].errors[0].field)
        self.assertEqual('Uh-uh', e.exception.actions[0].errors[0].message)

        self.assertEqual(1, stub_test_action_2.call_count)
        self.assertEqual({'a': 'body'}, stub_test_action_2.call_body)
        stub_test_action_2.assert_called_once_with({'a': 'body'})

    @stub_action('test_service', 'test_action_2')
    def test_mock_action_with_job_error_side_effect_raises_job_error_exception(self, stub_test_action_2):
        stub_test_action_2.side_effect = JobError(errors=[Error(code='BAR_BAD_JOB', message='Uh-uh job')])

        with self.assertRaises(Client.JobError) as e:
            self.client.call_action('test_service', 'test_action_2', {'a': 'body'})

        self.assertEqual('BAR_BAD_JOB', e.exception.errors[0].code)
        self.assertIsNone(e.exception.errors[0].field)
        self.assertEqual('Uh-uh job', e.exception.errors[0].message)

        self.assertEqual(1, stub_test_action_2.call_count)
        self.assertEqual({'a': 'body'}, stub_test_action_2.call_body)
        stub_test_action_2.assert_called_once_with({'a': 'body'})

    @stub_action('test_service', 'test_action_2')
    def test_mock_action_with_job_error_response_raises_job_error_exception(self, stub_test_action_2):
        stub_test_action_2.return_value = JobResponse(errors=[Error(code='BAR_BAD_JOB', message='Uh-uh job')])

        with self.assertRaises(Client.JobError) as e:
            self.client.call_action('test_service', 'test_action_2', {'a': 'body'})

        self.assertEqual('BAR_BAD_JOB', e.exception.errors[0].code)
        self.assertIsNone(e.exception.errors[0].field)
        self.assertEqual('Uh-uh job', e.exception.errors[0].message)

        self.assertEqual(1, stub_test_action_2.call_count)
        self.assertEqual({'a': 'body'}, stub_test_action_2.call_body)
        stub_test_action_2.assert_called_once_with({'a': 'body'})

    @stub_action('test_service', 'test_action_2', errors=[
        {'code': 'INVALID_BAR', 'message': 'A bad message'},
    ])
    def test_multiple_actions_stop_on_error(self, stub_test_action_2):
        response = self.client.call_actions(
            'test_service',
            [
                ActionRequest(action='test_action_1'),
                ActionRequest(action='test_action_2'),
                ActionRequest(action='test_action_1'),
            ],
            raise_action_errors=False,
        )

        # Called 3 actions, but expected to stop after the error in the second action
        self.assertEqual(2, len(response.actions))
        self.assertEqual('INVALID_BAR', response.actions[1].errors[0].code)
        self.assertEqual('A bad message', response.actions[1].errors[0].message)
        self.assertTrue(stub_test_action_2.called)

    @stub_action('test_service', 'test_action_2', errors=[
        {'code': 'MISSING_BAZ', 'field': 'entity_id', 'message': 'Your entity ID was missing'},
    ])
    def test_multiple_actions_continue_on_error(self, mock_test_action_2):
        response = self.client.call_actions(
            'test_service',
            [{'action': 'test_action_1'}, {'action': 'test_action_2'}, {'action': 'test_action_1'}],
            raise_action_errors=False,
            continue_on_error=True,
        )

        # Called 3 actions, and expected all three of them to be called, even with the interrupting error
        self.assertEqual(3, len(response.actions))
        self.assertEqual('MISSING_BAZ', response.actions[1].errors[0].code)
        self.assertEqual('entity_id', response.actions[1].errors[0].field)
        self.assertEqual('Your entity ID was missing', response.actions[1].errors[0].message)
        self.assertTrue(mock_test_action_2.called)

    @stub_action('test_service', 'test_action_2', body={'three': 'four'})
    @stub_action('test_service', 'test_action_1', body={'one': 'two'})
    def test_two_stubs_with_parallel_calls_all_stubbed(self, stub_test_action_1, stub_test_action_2):
        job_responses = self.client.call_jobs_parallel(
            [
                {'service_name': 'test_service', 'actions': [{'action': 'test_action_1', 'body': {'a': 'b'}}]},
                {'service_name': 'test_service', 'actions': [{'action': 'test_action_2', 'body': {'c': 'd'}}]},
            ],
        )

        self.assertIsNotNone(job_responses)
        self.assertEqual(2, len(job_responses))
        self.assertEqual(1, len(job_responses[0].actions))
        self.assertEqual({'one': 'two'}, job_responses[0].actions[0].body)
        self.assertEqual(1, len(job_responses[1].actions))
        self.assertEqual({'three': 'four'}, job_responses[1].actions[0].body)

        stub_test_action_1.assert_called_once_with({'a': 'b'})
        stub_test_action_2.assert_called_once_with({'c': 'd'})

    @stub_action('test_service', 'test_action_2')
    @mock.patch(__name__ + '._test_function')
    def test_one_stub_with_parallel_calls(self, mock_randint, stub_test_action_2):
        mock_randint.side_effect = (42, 17, 31)
        stub_test_action_2.return_value = {'concert': 'tickets'}

        job_responses = self.client.call_jobs_parallel(
            [
                {'service_name': 'test_service', 'actions': [{'action': 'test_action_1'}]},
                {'service_name': 'test_service', 'actions': [
                    {'action': 'test_action_2', 'body': {'slide': 'rule'}},
                    {'action': 'test_action_1'},
                ]},
                {'service_name': 'test_service', 'actions': [{'action': 'test_action_1'}]},
            ],
        )

        self.assertIsNotNone(job_responses)
        self.assertEqual(3, len(job_responses))
        self.assertEqual(1, len(job_responses[0].actions))
        self.assertEqual({'value': 42}, job_responses[0].actions[0].body)
        self.assertEqual(2, len(job_responses[1].actions))
        self.assertEqual({'concert': 'tickets'}, job_responses[1].actions[0].body)
        self.assertEqual({'value': 17}, job_responses[1].actions[1].body)
        self.assertEqual(1, len(job_responses[2].actions))
        self.assertEqual({'value': 31}, job_responses[2].actions[0].body)

        stub_test_action_2.assert_called_once_with({'slide': 'rule'})

    @stub_action('test_service', 'test_action_2')
    @stub_action('test_service', 'test_action_1')
    def test_two_stubs_with_parallel_calls(self, stub_test_action_1, stub_test_action_2):
        stub_test_action_1.return_value = {'value': 1}
        stub_test_action_2.return_value = {'another_value': 2}

        job_responses = Client(dict(self.client.config, **_secondary_stub_client_settings)).call_jobs_parallel(
            [
                {'service_name': 'test_service', 'actions': [
                    {'action': 'test_action_1', 'body': {'input_attribute': True}},
                    {'action': 'test_action_2', 'body': {'another_variable': 'Cool'}},
                ]},
                {'service_name': 'cat', 'actions': [{'action': 'meow'}]},
                {'service_name': 'dog', 'actions': [{'action': 'bark'}]},
                {'service_name': 'test_service', 'actions': [{'action': 'does_not_exist'}]},
            ],
            raise_action_errors=False,
        )

        self.assertIsNotNone(job_responses)
        self.assertEqual(4, len(job_responses))
        self.assertEqual(2, len(job_responses[0].actions))
        self.assertEqual({'value': 1}, job_responses[0].actions[0].body)
        self.assertEqual({'another_value': 2}, job_responses[0].actions[1].body)
        self.assertEqual(1, len(job_responses[1].actions))
        self.assertEqual({'type': 'squeak'}, job_responses[1].actions[0].body)
        self.assertEqual(1, len(job_responses[2].actions))
        self.assertEqual({'sound': 'woof'}, job_responses[2].actions[0].body)
        self.assertEqual(1, len(job_responses[3].actions))
        self.assertEqual(
            [Error(
                code='UNKNOWN',
                message='The action "does_not_exist" was not found on this server.',
                field='action',
                is_caller_error=True,
            )],
            job_responses[3].actions[0].errors
        )

        stub_test_action_1.assert_called_once_with({'input_attribute': True})
        stub_test_action_2.assert_called_once_with({'another_variable': 'Cool'})

    @stub_action('test_service', 'test_action_2', body={'three': 'four'})
    @stub_action('test_service', 'test_action_1')
    def test_two_stubs_with_parallel_calls_and_job_response_errors_raised(self, stub_test_action_1, stub_test_action_2):
        stub_test_action_1.return_value = JobResponse(errors=[Error(code='BAD_JOB', message='You are a bad job')])

        with self.assertRaises(self.client.JobError) as error_context:
            self.client.call_jobs_parallel(
                [
                    {'service_name': 'test_service', 'actions': [{'action': 'test_action_1', 'body': {'a': 'b'}}]},
                    {'service_name': 'test_service', 'actions': [{'action': 'test_action_2', 'body': {'c': 'd'}}]},
                ],
            )

        self.assertEqual([Error(code='BAD_JOB', message='You are a bad job')], error_context.exception.errors)

        stub_test_action_1.assert_called_once_with({'a': 'b'})
        stub_test_action_2.assert_called_once_with({'c': 'd'})

    @stub_action('test_service', 'test_action_2', body={'three': 'four'})
    @stub_action(
        'test_service',
        'test_action_1',
        side_effect=JobError(errors=[Error(code='BAD_JOB', message='You are a bad job')]),
    )
    def test_stub_action_with_two_stubs_with_parallel_calls_and_job_errors_not_raised(
        self,
        stub_test_action_1,
        stub_test_action_2,
    ):
        job_responses = self.client.call_jobs_parallel(
            [
                {'service_name': 'test_service', 'actions': [{'action': 'test_action_1', 'body': {'a': 'b'}}]},
                {'service_name': 'test_service', 'actions': [{'action': 'test_action_2', 'body': {'c': 'd'}}]},
            ],
            raise_job_errors=False,
        )

        self.assertIsNotNone(job_responses)
        self.assertEqual(2, len(job_responses))
        self.assertEqual(0, len(job_responses[0].actions))
        self.assertEqual([Error(code='BAD_JOB', message='You are a bad job')], job_responses[0].errors)
        self.assertEqual(1, len(job_responses[1].actions))
        self.assertEqual({'three': 'four'}, job_responses[1].actions[0].body)

        stub_test_action_1.assert_called_once_with({'a': 'b'})
        stub_test_action_2.assert_called_once_with({'c': 'd'})

    @stub_action('test_service', 'test_action_2', body={'three': 'four'})
    @stub_action(
        'test_service',
        'test_action_1',
        side_effect=ActionError(errors=[Error(code='BAD_ACTION', message='You are a bad actor')]),
    )
    def test_stub_action_with_two_stubs_with_parallel_calls_and_action_errors_raised(
        self,
        stub_test_action_1,
        stub_test_action_2,
    ):
        with self.assertRaises(self.client.CallActionError) as error_context:
            self.client.call_jobs_parallel(
                [
                    {'service_name': 'test_service', 'actions': [{'action': 'test_action_1', 'body': {'a': 'b'}}]},
                    {'service_name': 'test_service', 'actions': [{'action': 'test_action_2', 'body': {'c': 'd'}}]},
                ],
            )

        self.assertEqual(
            [Error(code='BAD_ACTION', message='You are a bad actor', is_caller_error=True)],
            error_context.exception.actions[0].errors,
        )

        stub_test_action_1.assert_called_once_with({'a': 'b'})
        stub_test_action_2.assert_called_once_with({'c': 'd'})

    @stub_action('test_service', 'test_action_2', body={'three': 'four'})
    @stub_action('test_service', 'test_action_1')
    def test_two_stubs_with_parallel_calls_and_job_errors_not_raised(self, stub_test_action_1, stub_test_action_2):
        stub_test_action_1.side_effect = JobError(errors=[Error(code='BAD_JOB', message='You are a bad job')])

        job_responses = self.client.call_jobs_parallel(
            [
                {'service_name': 'test_service', 'actions': [{'action': 'test_action_1', 'body': {'a': 'b'}}]},
                {'service_name': 'test_service', 'actions': [{'action': 'test_action_2', 'body': {'c': 'd'}}]},
            ],
            raise_job_errors=False,
        )

        self.assertIsNotNone(job_responses)
        self.assertEqual(2, len(job_responses))
        self.assertEqual(0, len(job_responses[0].actions))
        self.assertEqual([Error(code='BAD_JOB', message='You are a bad job')], job_responses[0].errors)
        self.assertEqual(1, len(job_responses[1].actions))
        self.assertEqual({'three': 'four'}, job_responses[1].actions[0].body)

        stub_test_action_1.assert_called_once_with({'a': 'b'})
        stub_test_action_2.assert_called_once_with({'c': 'd'})

    @stub_action('test_service', 'test_action_2', body={'three': 'four'})
    @stub_action('test_service', 'test_action_1')
    def test_two_stubs_with_parallel_calls_and_action_errors_raised(self, stub_test_action_1, stub_test_action_2):
        stub_test_action_1.side_effect = ActionError(errors=[Error(code='BAD_ACTION', message='You are a bad actor')])

        with self.assertRaises(self.client.CallActionError) as error_context:
            self.client.call_jobs_parallel(
                [
                    {'service_name': 'test_service', 'actions': [{'action': 'test_action_1', 'body': {'a': 'b'}}]},
                    {'service_name': 'test_service', 'actions': [{'action': 'test_action_2', 'body': {'c': 'd'}}]},
                ],
            )

        self.assertEqual(
            [Error(code='BAD_ACTION', message='You are a bad actor', is_caller_error=True)],
            error_context.exception.actions[0].errors,
        )

        stub_test_action_1.assert_called_once_with({'a': 'b'})
        stub_test_action_2.assert_called_once_with({'c': 'd'})

    @stub_action('test_service', 'test_action_2', body={'three': 'four'})
    @stub_action('test_service', 'test_action_1')
    def test_two_stubs_with_parallel_calls_and_action_response_errors_not_raised(
        self,
        stub_test_action_1,
        stub_test_action_2,
    ):
        stub_test_action_1.return_value = ActionResponse(
            action='test_action_1',
            errors=[Error(code='BAD_ACTION', message='You are a bad actor')],
        )

        job_responses = self.client.call_jobs_parallel(
            [
                {'service_name': 'test_service', 'actions': [{'action': 'test_action_1', 'body': {'a': 'b'}}]},
                {'service_name': 'test_service', 'actions': [{'action': 'test_action_2', 'body': {'c': 'd'}}]},
            ],
            raise_action_errors=False,
        )

        self.assertIsNotNone(job_responses)
        self.assertEqual(2, len(job_responses))
        self.assertEqual(1, len(job_responses[0].actions))
        self.assertEqual([Error(code='BAD_ACTION', message='You are a bad actor')], job_responses[0].actions[0].errors)
        self.assertEqual(1, len(job_responses[1].actions))
        self.assertEqual({'three': 'four'}, job_responses[1].actions[0].body)

        stub_test_action_1.assert_called_once_with({'a': 'b'})
        stub_test_action_2.assert_called_once_with({'c': 'd'})

    @stub_action('test_service', 'test_action_1', body={'food': 'chicken'})
    def test_send_receive_one_stub_simple(self, stub_test_action_1):
        request_id = self.client.send_request('test_service', [{'action': 'test_action_1', 'body': {'menu': 'look'}}])

        self.assertIsNotNone(request_id)

        responses = list(self.client.get_all_responses('test_service'))
        self.assertEqual(1, len(responses))

        received_request_id, response = responses[0]
        self.assertEqual(request_id, received_request_id)
        self.assertIsNotNone(response)
        self.assertEqual([], response.errors)
        self.assertEqual(1, len(response.actions))
        self.assertEqual([], response.actions[0].errors)
        self.assertEqual({'food': 'chicken'}, response.actions[0].body)

        stub_test_action_1.assert_called_once_with({'menu': 'look'})

    @stub_action('test_service', 'test_action_1')
    def test_send_receive_one_stub_multiple_calls(self, stub_test_action_1):
        stub_test_action_1.side_effect = ({'look': 'menu'}, {'pepperoni': 'pizza'}, {'cheese': 'pizza'})

        request_id1 = self.client.send_request(
            'test_service',
            [
                {'action': 'test_action_1', 'body': {'menu': 'look'}},
                {'action': 'test_action_1', 'body': {'pizza': 'pepperoni'}},
            ]
        )
        request_id2 = self.client.send_request(
            'test_service',
            [
                {'action': 'test_action_1', 'body': {'pizza': 'cheese'}},
            ]
        )

        self.assertIsNotNone(request_id1)
        self.assertIsNotNone(request_id2)

        responses = list(self.client.get_all_responses('test_service'))
        self.assertEqual(2, len(responses))

        response_dict = {k: v for k, v in responses}
        self.assertIn(request_id1, response_dict)
        self.assertIn(request_id2, response_dict)

        response = response_dict[request_id1]
        self.assertIsNotNone(response)
        self.assertEqual([], response.errors)
        self.assertEqual(2, len(response.actions))
        self.assertEqual([], response.actions[0].errors)
        self.assertEqual({'look': 'menu'}, response.actions[0].body)
        self.assertEqual({'pepperoni': 'pizza'}, response.actions[1].body)

        response = response_dict[request_id2]
        self.assertIsNotNone(response)
        self.assertEqual([], response.errors)
        self.assertEqual(1, len(response.actions))
        self.assertEqual([], response.actions[0].errors)
        self.assertEqual({'cheese': 'pizza'}, response.actions[0].body)

        stub_test_action_1.assert_has_calls(
            [
                mock.call({'menu': 'look'}),
                mock.call({'pizza': 'pepperoni'}),
                mock.call({'pizza': 'cheese'}),
            ],
            any_order=True,
        )

    @stub_action('test_service', 'test_action_1')
    def test_send_receive_one_stub_one_real_call_mixture(self, stub_test_action_1):
        stub_test_action_1.side_effect = (
            ActionResponse(action='does not matter', body={'look': 'menu'}),
            ActionResponse(action='no', errors=[Error(code='WEIRD', field='pizza', message='Weird error about pizza')]),
            ActionError(errors=[Error(code='COOL', message='Another error')]),
        )

        actions = [
            {'action': 'test_action_1', 'body': {'menu': 'look'}},
            {'action': 'test_action_2'},
            {'action': 'test_action_1', 'body': {'pizza': 'pepperoni'}},
            {'action': 'test_action_2'},
            {'action': 'test_action_2'},
        ]  # type: List[Dict[six.text_type, Any]]

        request_id1 = self.client.send_request('test_service', actions, continue_on_error=True)
        request_id2 = self.client.send_request(
            'test_service',
            [
                {'action': 'test_action_1', 'body': {'pizza': 'cheese'}},
            ]
        )
        request_id3 = self.client.send_request(
            'test_service',
            [
                {'action': 'test_action_2'},
            ]
        )

        self.assertIsNotNone(request_id1)
        self.assertIsNotNone(request_id2)
        self.assertIsNotNone(request_id3)

        responses = list(self.client.get_all_responses('test_service'))
        self.assertEqual(3, len(responses))

        response_dict = {k: v for k, v in responses}
        self.assertIn(request_id1, response_dict)
        self.assertIn(request_id2, response_dict)
        self.assertIn(request_id3, response_dict)

        response = response_dict[request_id1]
        self.assertIsNotNone(response)
        self.assertEqual([], response.errors)
        self.assertEqual(5, len(response.actions))
        self.assertEqual([], response.actions[0].errors)
        self.assertEqual({'look': 'menu'}, response.actions[0].body)
        self.assertEqual([], response.actions[1].errors)
        self.assertEqual({'value': 0}, response.actions[1].body)
        self.assertEqual(
            [Error(code='WEIRD', field='pizza', message='Weird error about pizza')],
            response.actions[2].errors,
        )
        self.assertEqual([], response.actions[3].errors)
        self.assertEqual({'value': 0}, response.actions[3].body)
        self.assertEqual([], response.actions[4].errors)
        self.assertEqual({'value': 0}, response.actions[4].body)

        response = response_dict[request_id2]
        self.assertIsNotNone(response)
        self.assertEqual([], response.errors)
        self.assertEqual(1, len(response.actions))
        self.assertEqual(
            [Error(code='COOL', message='Another error', is_caller_error=True)],
            response.actions[0].errors,
        )

        response = response_dict[request_id3]
        self.assertIsNotNone(response)
        self.assertEqual([], response.errors)
        self.assertEqual(1, len(response.actions))
        self.assertEqual([], response.actions[0].errors)
        self.assertEqual({'value': 0}, response.actions[0].body)

        stub_test_action_1.assert_has_calls(
            [
                mock.call({'menu': 'look'}),
                mock.call({'pizza': 'pepperoni'}),
                mock.call({'pizza': 'cheese'}),
            ],
            any_order=True,
        )


@stub_action('test_service', 'test_action_2')
class TestStubActionAsDecoratedClass(PyTestServerTestCase):
    server_class = _TestServiceServer
    server_settings = {}  # type: SettingsData

    def setup_method(self):
        super(TestStubActionAsDecoratedClass, self).setup_method()

        self.secondary_stub_client = Client(_secondary_stub_client_settings)

    def test_works_as_expected(self, stub_test_action_2):
        stub_test_action_2.return_value = {'brown': 'cow'}

        response = self.client.call_action('test_service', 'test_action_2', {'how': 'now'})
        self.assertEqual({'brown': 'cow'}, response.body)

        self.assertEqual(1, stub_test_action_2.call_count)
        self.assertEqual({'how': 'now'}, stub_test_action_2.call_body)
        stub_test_action_2.assert_called_once_with({'how': 'now'})

    @mock.patch(__name__ + '._test_function', return_value=7)
    def test_works_also_with_patch(self, mock_randint, stub_test_action_2):
        stub_test_action_2.return_value = {'brown': 'cow'}

        response = self.client.call_action('test_service', 'test_action_2', {'how': 'now'})
        self.assertEqual({'brown': 'cow'}, response.body)

        response = self.client.call_action('test_service', 'test_action_1')
        self.assertEqual({'value': 7}, response.body)

        self.assertEqual(1, stub_test_action_2.call_count)
        self.assertEqual({'how': 'now'}, stub_test_action_2.call_body)
        stub_test_action_2.assert_called_once_with({'how': 'now'})

        mock_randint.assert_called_once_with(0, 99)

    @stub_action('test_service', 'test_action_1', body={'christmas': 'tree'})
    def test_works_with_other_action_stubbed_as_decorator(self, stub_test_action_1, stub_test_action_2):
        stub_test_action_2.return_value = {'brown': 'cow'}

        response = self.client.call_action('test_service', 'test_action_1', {'which': 'decoration'})
        self.assertEqual({'christmas': 'tree'}, response.body)

        response = self.client.call_action('test_service', 'test_action_2', {'how': 'now'})
        self.assertEqual({'brown': 'cow'}, response.body)

        self.assertEqual(1, stub_test_action_1.call_count)
        self.assertEqual({'which': 'decoration'}, stub_test_action_1.call_body)
        stub_test_action_1.assert_called_once_with({'which': 'decoration'})

        self.assertEqual(1, stub_test_action_2.call_count)
        self.assertEqual({'how': 'now'}, stub_test_action_2.call_body)
        stub_test_action_2.assert_called_once_with({'how': 'now'})

    def test_works_with_other_action_stubbed_as_context_manager(self, stub_test_action_2):
        stub_test_action_2.return_value = {'brown': 'cow'}

        with stub_action('test_service', 'test_action_1', body={'christmas': 'tree'}) as stub_test_action_1:
            response = self.client.call_action('test_service', 'test_action_1', {'which': 'decoration'})
            self.assertEqual({'christmas': 'tree'}, response.body)

            response = self.client.call_action('test_service', 'test_action_2', {'how': 'now'})
            self.assertEqual({'brown': 'cow'}, response.body)

        self.assertEqual(1, stub_test_action_1.call_count)
        self.assertEqual({'which': 'decoration'}, stub_test_action_1.call_body)
        stub_test_action_1.assert_called_once_with({'which': 'decoration'})

        self.assertEqual(1, stub_test_action_2.call_count)
        self.assertEqual({'how': 'now'}, stub_test_action_2.call_body)
        stub_test_action_2.assert_called_once_with({'how': 'now'})

    def test_works_with_other_services_called(self, stub_test_action_2):
        stub_test_action_2.return_value = {'brown': 'cow'}

        response = self.client.call_action('test_service', 'test_action_2', {'how': 'now'})
        self.assertEqual({'brown': 'cow'}, response.body)

        response = self.secondary_stub_client.call_action('cat', 'meow')
        self.assertEqual({'type': 'squeak'}, response.body)

        response = self.secondary_stub_client.call_action('dog', 'bark')
        self.assertEqual({'sound': 'woof'}, response.body)

        self.assertEqual(1, stub_test_action_2.call_count)
        self.assertEqual({'how': 'now'}, stub_test_action_2.call_body)
        stub_test_action_2.assert_called_once_with({'how': 'now'})


@stub_action('test_service', 'test_action_2')
class TestStubActionAsDecoratedClassUnitTestCase(UnitTestServerTestCase):
    server_class = _TestServiceServer
    server_settings = {}  # type: SettingsData

    def setUp(self):
        super(TestStubActionAsDecoratedClassUnitTestCase, self).setUp()

        self.secondary_stub_client = Client(_secondary_stub_client_settings)

    def test_works_as_expected(self, stub_test_action_2):
        stub_test_action_2.return_value = {'brown': 'cow'}

        response = self.client.call_action('test_service', 'test_action_2', {'how': 'now'})
        self.assertEqual({'brown': 'cow'}, response.body)

        self.assertEqual(1, stub_test_action_2.call_count)
        self.assertEqual({'how': 'now'}, stub_test_action_2.call_body)
        stub_test_action_2.assert_called_once_with({'how': 'now'})

    @mock.patch(__name__ + '._test_function', return_value=7)
    def test_works_also_with_patch(self, mock_randint, stub_test_action_2):
        stub_test_action_2.return_value = {'brown': 'cow'}

        response = self.client.call_action('test_service', 'test_action_2', {'how': 'now'})
        self.assertEqual({'brown': 'cow'}, response.body)

        response = self.client.call_action('test_service', 'test_action_1')
        self.assertEqual({'value': 7}, response.body)

        self.assertEqual(1, stub_test_action_2.call_count)
        self.assertEqual({'how': 'now'}, stub_test_action_2.call_body)
        stub_test_action_2.assert_called_once_with({'how': 'now'})

        mock_randint.assert_called_once_with(0, 99)

    @stub_action('test_service', 'test_action_1', body={'christmas': 'tree'})
    def test_works_with_other_action_stubbed_as_decorator(self, stub_test_action_1, stub_test_action_2):
        stub_test_action_2.return_value = {'brown': 'cow'}

        response = self.client.call_action('test_service', 'test_action_1', {'which': 'decoration'})
        self.assertEqual({'christmas': 'tree'}, response.body)

        response = self.client.call_action('test_service', 'test_action_2', {'how': 'now'})
        self.assertEqual({'brown': 'cow'}, response.body)

        self.assertEqual(1, stub_test_action_1.call_count)
        self.assertEqual({'which': 'decoration'}, stub_test_action_1.call_body)
        stub_test_action_1.assert_called_once_with({'which': 'decoration'})

        self.assertEqual(1, stub_test_action_2.call_count)
        self.assertEqual({'how': 'now'}, stub_test_action_2.call_body)
        stub_test_action_2.assert_called_once_with({'how': 'now'})

    def test_works_with_other_action_stubbed_as_context_manager(self, stub_test_action_2):
        stub_test_action_2.return_value = {'brown': 'cow'}

        with stub_action('test_service', 'test_action_1', body={'christmas': 'tree'}) as stub_test_action_1:
            response = self.client.call_action('test_service', 'test_action_1', {'which': 'decoration'})
            self.assertEqual({'christmas': 'tree'}, response.body)

            response = self.client.call_action('test_service', 'test_action_2', {'how': 'now'})
            self.assertEqual({'brown': 'cow'}, response.body)

        self.assertEqual(1, stub_test_action_1.call_count)
        self.assertEqual({'which': 'decoration'}, stub_test_action_1.call_body)
        stub_test_action_1.assert_called_once_with({'which': 'decoration'})

        self.assertEqual(1, stub_test_action_2.call_count)
        self.assertEqual({'how': 'now'}, stub_test_action_2.call_body)
        stub_test_action_2.assert_called_once_with({'how': 'now'})

    def test_works_with_other_services_called(self, stub_test_action_2):
        stub_test_action_2.return_value = {'brown': 'cow'}

        response = self.client.call_action('test_service', 'test_action_2', {'how': 'now'})
        self.assertEqual({'brown': 'cow'}, response.body)

        response = self.secondary_stub_client.call_action('cat', 'meow')
        self.assertEqual({'type': 'squeak'}, response.body)

        response = self.secondary_stub_client.call_action('dog', 'bark')
        self.assertEqual({'sound': 'woof'}, response.body)

        self.assertEqual(1, stub_test_action_2.call_count)
        self.assertEqual({'how': 'now'}, stub_test_action_2.call_body)
        stub_test_action_2.assert_called_once_with({'how': 'now'})


@stub_action('test_service', 'test_action_2', body={'major': 'response'})
@mock.patch(__name__ + '._test_function', return_value=42)
class TestStubActionAsStubAndPatchDecoratedClass(PyTestServerTestCase):
    server_class = _TestServiceServer
    server_settings = {}  # type: SettingsData

    def test_works_as_expected(self, mock_randint, stub_test_action_2):
        response = self.client.call_action('test_service', 'test_action_1')
        self.assertEqual({'value': 42}, response.body)

        response = self.client.call_action('test_service', 'test_action_2', {'minor': 'request'})
        self.assertEqual({'major': 'response'}, response.body)

        self.assertEqual(1, stub_test_action_2.call_count)
        self.assertEqual({'minor': 'request'}, stub_test_action_2.call_body)
        stub_test_action_2.assert_called_once_with({'minor': 'request'})
        mock_randint.assert_called_once_with(0, 99)

    @stub_action('cow', 'moo', body={'eats': 'grass'})
    def test_works_with_yet_another_stub(self, stub_moo, mock_randint, stub_test_action_2):
        response = self.client.call_action('test_service', 'test_action_1')
        self.assertEqual({'value': 42}, response.body)

        response = self.client.call_action('test_service', 'test_action_2', {'minor': 'request'})
        self.assertEqual({'major': 'response'}, response.body)

        response = self.client.call_action('cow', 'moo')
        self.assertEqual({'eats': 'grass'}, response.body)

        self.assertEqual(1, stub_test_action_2.call_count)
        self.assertEqual({'minor': 'request'}, stub_test_action_2.call_body)
        stub_test_action_2.assert_called_once_with({'minor': 'request'})
        self.assertEqual(1, stub_moo.call_count)
        self.assertEqual({}, stub_moo.call_body)
        stub_moo.assert_called_once_with({})
        mock_randint.assert_called_once_with(0, 99)


@stub_action('test_service', 'test_action_2', body={'major': 'response'})
@mock.patch(__name__ + '._test_function', return_value=42)
class TestStubActionAsStubAndPatchDecoratedClassUnitTestCase(UnitTestServerTestCase):
    server_class = _TestServiceServer
    server_settings = {}  # type: SettingsData

    def test_works_as_expected(self, mock_randint, stub_test_action_2):
        response = self.client.call_action('test_service', 'test_action_1')
        self.assertEqual({'value': 42}, response.body)

        response = self.client.call_action('test_service', 'test_action_2', {'minor': 'request'})
        self.assertEqual({'major': 'response'}, response.body)

        self.assertEqual(1, stub_test_action_2.call_count)
        self.assertEqual({'minor': 'request'}, stub_test_action_2.call_body)
        stub_test_action_2.assert_called_once_with({'minor': 'request'})
        mock_randint.assert_called_once_with(0, 99)

    @stub_action('cow', 'moo', body={'eats': 'grass'})
    def test_works_with_yet_another_stub(self, stub_moo, mock_randint, stub_test_action_2):
        response = self.client.call_action('test_service', 'test_action_1')
        self.assertEqual({'value': 42}, response.body)

        response = self.client.call_action('test_service', 'test_action_2', {'minor': 'request'})
        self.assertEqual({'major': 'response'}, response.body)

        response = self.client.call_action('cow', 'moo')
        self.assertEqual({'eats': 'grass'}, response.body)

        self.assertEqual(1, stub_test_action_2.call_count)
        self.assertEqual({'minor': 'request'}, stub_test_action_2.call_body)
        stub_test_action_2.assert_called_once_with({'minor': 'request'})
        self.assertEqual(1, stub_moo.call_count)
        self.assertEqual({}, stub_moo.call_body)
        stub_moo.assert_called_once_with({})
        mock_randint.assert_called_once_with(0, 99)
