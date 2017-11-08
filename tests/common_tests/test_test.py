from __future__ import unicode_literals

from unittest import TestCase

import attr

from pysoa.common.constants import ERROR_CODE_INVALID
from pysoa.common.types import UnicodeKeysDict
from pysoa.test.stub_service import StubClient



SERVICE_NAME = 'test_service'


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
            error_response = e.value.actions[0].errors
            self.assertEqual(len(error_response), 1)
            self.assertEqual(error_response['code'], get_bar_error['code'])
            self.assertEqual(error_response['message'], get_bar_error['message'])
            self.assertEqual(error_response['code'], get_bar_error['code'])

    def test_stub_action_body_only(self):
        """
        StubClient.stub_action with a 'body' argument causes the client to return an action
        response with the given body.
        """
        response_body = {'foo': 'bar'}
        self.client.stub_action(SERVICE_NAME, 'test_action', body=response_body)
        response = self.client.call_action(SERVICE_NAME, 'test_action')
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
        self.client.stub_action(SERVICE_NAME, 'test_action', errors=errors)
        with self.assertRaises(StubClient.CallActionError) as e:
            self.client.call_action(SERVICE_NAME, 'test_action')
            error_response = e.value.actions[0].errors
            self.assertEqual(len(error_response), 1)
            self.assertEqual(error_response[0].code, errors[0]['code'])
            self.assertEqual(error_response[0].message, errors[0]['message'])
            self.assertEqual(error_response[0].field, errors[0]['field'])

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
        self.client.stub_action(SERVICE_NAME, 'test_action', errors=errors, body=response_body)
        with self.assertRaises(StubClient.CallActionError) as e:
            self.client.call_action(SERVICE_NAME, 'test_action')
            error_response = e.value.actions[0].errors
            self.assertEqual(len(error_response), 1)
            self.assertEqual(error_response[0].code, errors[0]['code'])
            self.assertEqual(error_response[0].message, errors[0]['message'])
            self.assertEqual(error_response[0].field, errors[0]['field'])

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
                    },
                ],
            },
        }
        self.client.stub_action(SERVICE_NAME, 'action_1', **responses['action_1'])
        self.client.stub_action(SERVICE_NAME, 'action_2', **responses['action_2'])
        self.client.stub_action(SERVICE_NAME, 'action_3', **responses['action_3'])

        control = self.client._make_control_header()
        context = self.client._make_context_header()
        request_1 = dict(control_extra=control, context=context, actions=[
            {'action': 'action_1'},
            {'action': 'action_2'},
        ])
        request_2 = dict(control_extra=control, context=context, actions=[
            {'action': 'action_2'},
            {'action': 'action_1'},
        ])
        request_3 = dict(control_extra=control, context=context, actions=[{'action': 'action_3'}])

        # Store requests by request ID for later verification, because order is not guaranteed
        requests_by_id = {}
        for request in (request_1, request_2, request_3):
            request_id = self.client.send_request(SERVICE_NAME, **request)
            requests_by_id[request_id] = request

        for response_id, response in self.client.get_all_responses(SERVICE_NAME):
            # The client returned the same number of actions as were requested
            self.assertEqual(len(response.actions), len(requests_by_id[response_id]['actions']))
            for i in range(len(response.actions)):
                action_response = response.actions[i]
                # The action name returned matches the action name in the request
                self.assertEqual(action_response.action, requests_by_id[response_id]['actions'][i]['action'])
                # The action response matches the expected response
                # Errors are returned as the Error type, so convert them to dict first
                self.assertEqual(action_response.body, responses[action_response.action]['body'])
                self.assertEqual(
                    [attr.asdict(e, dict_factory=UnicodeKeysDict) for e in action_response.errors],
                    responses[action_response.action]['errors'],
                )
