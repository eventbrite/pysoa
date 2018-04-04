from __future__ import unicode_literals

from pysoa.client.client import Client
from pysoa.client.middleware import ClientMiddleware
from pysoa.common.constants import (
    ERROR_CODE_INVALID,
    ERROR_CODE_SERVER_ERROR,
)
from pysoa.common.types import (
    ActionRequest,
    ActionResponse,
    JobResponse,
    Error,
)
from pysoa.server.errors import JobError

import mock
from unittest import TestCase

SERVICE_NAME = 'test_service'


class MutateRequestMiddleware(ClientMiddleware):

    def request(self, send_request):
        def handler(request_id, meta, request, message_expiry_in_seconds):
            if request.control.get('test_request_middleware'):
                request.actions[0].body['middleware_was_here'] = True
            return send_request(request_id, meta, request, message_expiry_in_seconds)
        return handler


class RaiseExceptionOnRequestMiddleware(ClientMiddleware):

    class MiddlewareProcessedRequest(Exception):
        pass

    def request(self, send_request):
        def handler(request_id, meta, request, message_expiry_in_seconds):
            if request.actions and request.actions[0].body.get('middleware_was_here') is True:
                raise self.MiddlewareProcessedRequest()
            return send_request(request_id, meta, request, message_expiry_in_seconds)
        return handler


class CatchExceptionOnRequestMiddleware(ClientMiddleware):

    def __init__(self, *args, **kwargs):
        super(CatchExceptionOnRequestMiddleware, self).__init__(*args, **kwargs)
        self.error_count = 0
        self.request_count = 0

    def request(self, send_request):
        def handler(request_id, meta, request, message_expiry_in_seconds):
            try:
                return send_request(request_id, meta, request, message_expiry_in_seconds)
            except Exception:
                self.error_count += 1
                raise
            finally:
                self.request_count += 1
        return handler


class MutateResponseMiddleware(ClientMiddleware):

    def response(self, get_response):
        def handler(receive_timeout_in_seconds):
            request_id, response = get_response(receive_timeout_in_seconds)
            if response and response.actions:
                response.actions[0].body['middleware_was_here'] = True
            return request_id, response
        return handler


class RaiseExceptionOnResponseMiddleware(ClientMiddleware):

    class MiddlewareProcessedResponse(Exception):
        pass

    def response(self, get_response):
        def handler(receive_timeout_in_seconds):
            request_id, response = get_response(receive_timeout_in_seconds)
            if response and response.actions and response.actions[0].body.get('middleware_was_here') is True:
                raise self.MiddlewareProcessedResponse()
            return request_id, response
        return handler


class CatchExceptionOnResponseMiddleware(ClientMiddleware):

    def __init__(self, *args, **kwargs):
        super(CatchExceptionOnResponseMiddleware, self).__init__(*args, **kwargs)
        self.error_count = 0
        self.request_count = 0

    def response(self, get_response):
        def handler(receive_timeout_in_seconds):
            try:
                return get_response(receive_timeout_in_seconds)
            except Exception:
                self.error_count += 1
                raise
            finally:
                self.request_count += 1
        return handler


class TestClientSendReceive(TestCase):
    """
    Test that the client send/receive methods return the correct types with the action responses
    set on the correct fields. Tests with both raw dict and JobRequest/ActionRequest where
    applicable.
    """

    def setUp(self):
        self.client_settings = {
            SERVICE_NAME: {
                'transport': {
                    'path': 'pysoa.test.stub_service:StubClientTransport',
                    'kwargs': {
                        'action_map': {
                            'action_1': {'body': {'foo': 'bar'}},
                            'action_2': {'body': {'baz': 3}},
                        },
                    },
                },
            },
        }

    def test_send_request_get_response(self):
        """
        Client.send_request sends a valid request and Client.get_all_responses returns a valid response
        without errors.
        """
        action_request = [
            {
                'action': 'action_1',
                'body': {},
            },
            {
                'action': 'action_2',
                'body': {},
            },
        ]
        client = Client(self.client_settings)

        responses = list(client.get_all_responses(SERVICE_NAME))
        self.assertEqual(len(responses), 0)

        request_id = client.send_request(
            SERVICE_NAME,
            action_request,
            switches={1},
        )
        self.assertTrue(request_id >= 0)
        responses = list(client.get_all_responses(SERVICE_NAME))
        self.assertEqual(len(responses), 1)
        response_id, response = responses[0]
        # ensure that the response is structured as expected
        self.assertEqual(response_id, request_id)
        self.assertTrue(isinstance(response, JobResponse))
        self.assertTrue(all([isinstance(a, ActionResponse) for a in response.actions]))
        self.assertEqual(response.actions[0].action, 'action_1')
        self.assertEqual(response.actions[0].body['foo'], 'bar')
        self.assertEqual(response.actions[1].action, 'action_2')
        self.assertEqual(response.actions[1].body['baz'], 3)

    def test_call_actions(self):
        """Client.call_actions sends a valid request and returns a valid response without errors."""
        action_request = [
            {
                'action': 'action_1',
                'body': {},
            },
            {
                'action': 'action_2',
                'body': {},
            },
        ]
        client = Client(self.client_settings)

        for actions in (action_request, [ActionRequest(**a) for a in action_request]):
            response = client.call_actions(SERVICE_NAME, actions)
            self.assertTrue(isinstance(response, JobResponse))
            self.assertTrue(all([isinstance(a, ActionResponse) for a in response.actions]))
            self.assertEqual(len(response.actions), 2)
            # ensure that the response is structured as expected
            self.assertEqual(response.actions[0].action, 'action_1')
            self.assertEqual(response.actions[0].body['foo'], 'bar')
            self.assertEqual(response.actions[1].action, 'action_2')
            self.assertEqual(response.actions[1].body['baz'], 3)

    def test_call_actions_raises_exception_on_action_error(self):
        """Client.call_actions raises CallActionError when any action response is an error."""
        action_request = [
            {
                'action': 'action_1',
                'body': {'foo': 'bar'},
            },
            {
                'action': 'action_2',
                'body': {},
            },
        ]
        error_expected = [
            Error(
                code=ERROR_CODE_INVALID,
                message='Invalid input',
                field='foo',
            )
        ]
        self.client_settings[SERVICE_NAME]['transport']['kwargs']['action_map']['action_1'] = {'errors': error_expected}
        client = Client(self.client_settings)

        for actions in (action_request, [ActionRequest(**a) for a in action_request]):
            with self.assertRaises(Client.CallActionError) as e:
                client.call_actions(SERVICE_NAME, actions)
                self.assertEqual(len(e.value.actions), 1)
                self.assertEqual(e.value.actions[0].action, 'action_1')
                error_response = e.value.actions[0].errors
                self.assertEqual(len(error_response), 1)
                self.assertEqual(error_response[0].code, error_expected[0]['code'])
                self.assertEqual(error_response[0].message, error_expected[0]['message'])
                self.assertEqual(error_response[0].field, error_expected[0]['field'])

    def test_call_actions_no_raise_action_errors(self):
        action_request = [
            {
                'action': 'action_1',
                'body': {'foo': 'bar'},
            },
            {
                'action': 'action_2',
                'body': {},
            },
        ]
        error_expected = [
            Error(
                code=ERROR_CODE_INVALID,
                message='Invalid input',
                field='foo'
            )
        ]
        self.client_settings[SERVICE_NAME]['transport']['kwargs']['action_map']['action_2'] = {'errors': error_expected}
        client = Client(self.client_settings)
        for actions in (action_request, [ActionRequest(**a) for a in action_request]):
            response = client.call_actions(SERVICE_NAME, actions, raise_action_errors=False)
            self.assertEqual(response.actions[0].body, {'foo': 'bar'})
            self.assertEqual(response.actions[1].errors, error_expected)

    def test_call_actions_raises_exception_on_job_error(self):
        """Client.call_actions raises Client.JobError when a JobError occurs on the server."""
        client = Client(self.client_settings)
        errors = [Error(code=ERROR_CODE_SERVER_ERROR, message='Something went wrong!')]
        with mock.patch.object(
            client._get_handler(SERVICE_NAME).transport.server,
            'execute_job',
            new=mock.Mock(side_effect=JobError(errors)),
        ):
            with self.assertRaises(Client.JobError) as e:
                client.call_action(SERVICE_NAME, 'action_1')
                self.assertEqual(e.errors, errors)

    def test_call_action(self):
        """Client.call_action sends a valid request and returns a valid response without errors."""
        client = Client(self.client_settings)
        response = client.call_action(SERVICE_NAME, 'action_1')
        self.assertTrue(isinstance(response, ActionResponse))
        self.assertEqual(response.action, 'action_1')
        self.assertEqual(response.body['foo'], 'bar')

    def test_call_action_with_cached_transport(self):
        """
        Client.call_action sends a valid request and returns a valid response without errors using a cached transport.
        """
        self.client_settings[SERVICE_NAME]['transport_cache_time_in_seconds'] = 2

        client = Client(self.client_settings)
        response = client.call_action(SERVICE_NAME, 'action_1')
        self.assertTrue(isinstance(response, ActionResponse))
        self.assertEqual(response.action, 'action_1')
        self.assertEqual(response.body['foo'], 'bar')

        client = Client(self.client_settings)
        response = client.call_action(SERVICE_NAME, 'action_2')
        self.assertTrue(isinstance(response, ActionResponse))
        self.assertEqual(response.action, 'action_2')
        self.assertEqual(response.body['baz'], 3)

        client = Client(self.client_settings)
        response = client.call_action(SERVICE_NAME, 'action_1')
        self.assertTrue(isinstance(response, ActionResponse))
        self.assertEqual(response.action, 'action_1')
        self.assertEqual(response.body['foo'], 'bar')


class TestClientMiddleware(TestCase):
    """Test that the client calls its middleware correctly."""

    def setUp(self):
        self.client = Client({
            SERVICE_NAME: {
                'transport': {
                    'path': 'pysoa.test.stub_service:StubClientTransport',
                    'kwargs': {
                        'action_map': {
                            'action_1': {'body': {}},
                        },
                    },
                }
            }
        })

    def test_request_single_middleware(self):
        # Need to manually set the middleware on the handler, since the middleware is defined in this file
        # and cannot be
        self.client._get_handler(SERVICE_NAME).middleware.append(RaiseExceptionOnRequestMiddleware())
        with self.assertRaises(RaiseExceptionOnRequestMiddleware.MiddlewareProcessedRequest):
            self.client.call_action(SERVICE_NAME, 'action_1', body={'middleware_was_here': True})

    def test_request_multiple_middleware_order(self):
        # The first middleware mutates the response so that the second raises an exception
        self.client._get_handler(SERVICE_NAME).middleware = [
            MutateRequestMiddleware(),
            RaiseExceptionOnRequestMiddleware(),
        ]
        with self.assertRaises(RaiseExceptionOnRequestMiddleware.MiddlewareProcessedRequest):
            self.client.call_action(SERVICE_NAME, 'action_1', control_extra={'test_request_middleware': True})

        # If the order is reversed, no exception is raised
        self.client._get_handler(SERVICE_NAME).middleware = [
            RaiseExceptionOnRequestMiddleware(),
            MutateRequestMiddleware(),
        ]
        self.client.call_action(SERVICE_NAME, 'action_1', control_extra={'test_request_middleware': True})

    def test_request_middleware_handle_exception(self):
        # the exception handler must be on the outer layer of the onion
        self.client._get_handler(SERVICE_NAME).middleware = [
            CatchExceptionOnRequestMiddleware(),
            MutateRequestMiddleware(),
            RaiseExceptionOnRequestMiddleware(),
        ]
        with self.assertRaises(RaiseExceptionOnRequestMiddleware.MiddlewareProcessedRequest):
            self.client.call_action(SERVICE_NAME, 'action_1', control_extra={'test_request_middleware': True})
        self.assertEqual(self.client.handlers[SERVICE_NAME].middleware[0].request_count, 1)
        self.assertEqual(self.client.handlers[SERVICE_NAME].middleware[0].error_count, 1)

    def test_response_single_middleware(self):
        handler = self.client._get_handler(SERVICE_NAME)
        handler.middleware = [RaiseExceptionOnResponseMiddleware()]
        handler.transport.stub_action('action_1', body={'middleware_was_here': True})
        with self.assertRaises(RaiseExceptionOnResponseMiddleware.MiddlewareProcessedResponse):
            self.client.call_action(SERVICE_NAME, 'action_1')

    def test_response_multiple_middleware_order(self):
        self.client._get_handler(SERVICE_NAME).middleware = [
            RaiseExceptionOnResponseMiddleware(),
            MutateResponseMiddleware(),
        ]
        with self.assertRaises(RaiseExceptionOnResponseMiddleware.MiddlewareProcessedResponse):
            self.client.call_action(SERVICE_NAME, 'action_1')

    def test_response_middleware_handle_exception(self):
        self.client._get_handler(SERVICE_NAME).middleware = [
            CatchExceptionOnResponseMiddleware(),
            RaiseExceptionOnResponseMiddleware(),
            MutateResponseMiddleware(),
        ]
        with self.assertRaises(RaiseExceptionOnResponseMiddleware.MiddlewareProcessedResponse):
            self.client.call_action(SERVICE_NAME, 'action_1')
        self.assertEqual(self.client.handlers[SERVICE_NAME].middleware[0].request_count, 1)
        self.assertEqual(self.client.handlers[SERVICE_NAME].middleware[0].error_count, 1)
