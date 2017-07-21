from __future__ import unicode_literals

from pysoa.client.client import (
    Client,
    ServiceHandler
)
from pysoa.client.middleware import ClientMiddleware
from pysoa.common.constants import (
    ERROR_CODE_INVALID,
    ERROR_CODE_SERVER_ERROR,
)
from pysoa.common.serializer.msgpack_serializer import MsgpackSerializer
from pysoa.common.types import (
    ActionRequest,
    ActionResponse,
    JobResponse,
    Error,
)
from pysoa.server.errors import JobError
from pysoa.test.stub_service import StubClientTransport

import mock
from unittest import TestCase

SERVICE_NAME = 'test_service'


class MutateRequestMiddleware(ClientMiddleware):

    def request(self, send_request):
        def handler(request_id, meta, request):
            if request.control.get('test_request_middleware'):
                request.actions[0].body['middleware_was_here'] = True
            return send_request(request_id, meta, request)
        return handler


class RaiseExceptionOnRequestMiddleware(ClientMiddleware):

    class MiddlewareProcessedRequest(Exception):
        pass

    def request(self, send_request):
        def handler(request_id, meta, request):
            if request.actions and request.actions[0].body.get('middleware_was_here') is True:
                raise self.MiddlewareProcessedRequest()
            return send_request(request_id, meta, request)
        return handler


class CatchExceptionOnRequestMiddleware(ClientMiddleware):

    def __init__(self, *args, **kwargs):
        super(CatchExceptionOnRequestMiddleware, self).__init__(*args, **kwargs)
        self.error_count = 0
        self.request_count = 0

    def request(self, send_request):
        def handler(request_id, meta, request):
            try:
                return send_request(request_id, meta, request)
            except:
                self.error_count += 1
                raise
            finally:
                self.request_count += 1
        return handler


class MutateResponseMiddleware(ClientMiddleware):

    def response(self, get_response):
        def handler():
            request_id, response = get_response()
            if response and response.actions:
                response.actions[0].body['middleware_was_here'] = True
            return request_id, response
        return handler


class RaiseExceptionOnResponseMiddleware(ClientMiddleware):

    class MiddlewareProcessedResponse(Exception):
        pass

    def response(self, get_response):
        def handler():
            request_id, response = get_response()
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
        def handler():
            try:
                return get_response()
            except:
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
        self.transport = StubClientTransport()
        self.serializer = MsgpackSerializer()

    def test_send_request_get_response(self):
        """
        Client.send_request sends a valid request and Client.get_all_responses returns a valid response
        without errors.
        """
        actions = [
            {
                'action': 'action_1',
                'body': {},
            },
            {
                'action': 'action_2',
                'body': {},
            },
        ]
        self.transport.stub_action('action_1', body={'foo': 'bar'})
        self.transport.stub_action('action_2', body={'baz': 3})
        client = Client(
            handlers={
                SERVICE_NAME: ServiceHandler(transport=self.transport, serializer=self.serializer),
            }
        )

        responses = list(client.get_all_responses(SERVICE_NAME))
        self.assertEqual(len(responses), 0)

        request_id = client.send_request(
            SERVICE_NAME,
            actions,
            switches=set([1]),
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
        action_dicts = [
            {
                'action': 'action_1',
                'body': {},
            },
            {
                'action': 'action_2',
                'body': {},
            },
        ]
        self.transport.stub_action('action_1', body={'foo': 'bar'})
        self.transport.stub_action('action_2', body={'baz': 3})
        client = Client(
            handlers={
                SERVICE_NAME: ServiceHandler(self.transport, self.serializer)
            }
        )

        for actions in (action_dicts, [ActionRequest(**a) for a in action_dicts]):
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
        action_dicts = [
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
            {
                'code': ERROR_CODE_INVALID,
                'message': 'Invalid input',
                'field': 'foo',
            }
        ]
        self.transport.stub_action('action_1', errors=error_expected)
        self.transport.stub_action('action_2', body={'baz': 3})
        client = Client(
            handlers={
                SERVICE_NAME: ServiceHandler(transport=self.transport, serializer=self.serializer),
            }
        )

        for actions in (action_dicts, [ActionRequest(**a) for a in action_dicts]):
            with self.assertRaises(Client.CallActionError) as e:
                client.call_actions(SERVICE_NAME, actions)
                self.assertEqual(len(e.value.actions), 1)
                self.assertEqual(e.value.actions[0].action, 'action_1')
                error_response = e.value.actions[0].errors
                self.assertEqual(len(error_response), 1)
                self.assertEqual(error_response[0].code, error_expected[0]['code'])
                self.assertEqual(error_response[0].message, error_expected[0]['message'])
                self.assertEqual(error_response[0].field, error_expected[0]['field'])

    def test_call_actions_raises_exception_on_job_error(self):
        """Client.call_actions raises Client.JobError when a JobError occurs on the server."""
        self.transport.stub_action('action_1', body={})
        client = Client(
            handlers={
                SERVICE_NAME: ServiceHandler(transport=self.transport, serializer=self.serializer),
            }
        )
        errors = [Error(code=ERROR_CODE_SERVER_ERROR, message='Something went wrong!')]
        with mock.patch.object(self.transport.server, 'execute_job', new=mock.Mock(side_effect=JobError(errors))):
            with self.assertRaises(Client.JobError) as e:
                client.call_action(SERVICE_NAME, 'action_1')
                self.assertEqual(e.errors, errors)

    def test_call_action(self):
        """Client.call_action sends a valid request and returns a valid response without errors."""
        self.transport.stub_action('action_1', body={'foo': 'bar'})
        client = Client(
            handlers={
                SERVICE_NAME: ServiceHandler(transport=self.transport, serializer=self.serializer),
            }
        )
        response = client.call_action(SERVICE_NAME, 'action_1')
        self.assertTrue(isinstance(response, ActionResponse))
        self.assertEqual(response.action, 'action_1')
        self.assertEqual(response.body['foo'], 'bar')


class TestClientMiddleware(TestCase):
    """Test that the client calls its middleware correctly."""

    def setUp(self):
        self.transport = StubClientTransport()
        self.serializer = MsgpackSerializer()

    def test_request_single_middleware(self):
        middleware = [RaiseExceptionOnRequestMiddleware()]
        client = Client(
            handlers={
                SERVICE_NAME: ServiceHandler(
                    transport=self.transport,
                    serializer=self.serializer,
                    middleware=middleware,
                ),
            }
        )
        with self.assertRaises(RaiseExceptionOnRequestMiddleware.MiddlewareProcessedRequest):
            client.call_action(SERVICE_NAME, 'action_1', body={'middleware_was_here': True})

    def test_request_multiple_middleware_order(self):
        self.transport.stub_action('action_1', body={})

        # The first middleware mutates the response so that the second raises an exception
        middleware = [
            MutateRequestMiddleware(),
            RaiseExceptionOnRequestMiddleware(),
        ]
        client = Client(
            handlers={
                SERVICE_NAME: ServiceHandler(
                    transport=self.transport,
                    serializer=self.serializer,
                    middleware=middleware,
                ),
            }
        )
        with self.assertRaises(RaiseExceptionOnRequestMiddleware.MiddlewareProcessedRequest):
            client.call_action(SERVICE_NAME, 'action_1', control_extra={'test_request_middleware': True})

        # If the order is reversed, no exception is raised
        middleware = reversed(middleware)
        client = Client(
            handlers={
                SERVICE_NAME: ServiceHandler(
                    transport=self.transport,
                    serializer=self.serializer,
                    middleware=middleware,
                ),
            }
        )
        client.call_action(SERVICE_NAME, 'action_1', control_extra={'test_request_middleware': True})

    def test_request_middleware_handle_exception(self):
        # the exception handler must be on the outer layer of the onion
        middleware = [
            CatchExceptionOnRequestMiddleware(),
            MutateRequestMiddleware(),
            RaiseExceptionOnRequestMiddleware(),
        ]
        client = Client(
            handlers={
                SERVICE_NAME: ServiceHandler(
                    transport=self.transport,
                    serializer=self.serializer,
                    middleware=middleware,
                ),
            }
        )
        with self.assertRaises(RaiseExceptionOnRequestMiddleware.MiddlewareProcessedRequest):
            client.call_action(SERVICE_NAME, 'action_1', control_extra={'test_request_middleware': True})
        self.assertEqual(client.handlers[SERVICE_NAME].middleware[0].request_count, 1)
        self.assertEqual(client.handlers[SERVICE_NAME].middleware[0].error_count, 1)

    def test_response_single_middleware(self):
        middleware = [RaiseExceptionOnResponseMiddleware()]
        self.transport.stub_action('action_1', body={'middleware_was_here': True})
        client = Client(
            handlers={
                SERVICE_NAME: ServiceHandler(
                    transport=self.transport,
                    serializer=self.serializer,
                    middleware=middleware,
                ),
            }
        )
        with self.assertRaises(RaiseExceptionOnResponseMiddleware.MiddlewareProcessedResponse):
            client.call_action(SERVICE_NAME, 'action_1')

    def test_response_multiple_middleware_order(self):
        middleware = [
            RaiseExceptionOnResponseMiddleware(),
            MutateResponseMiddleware(),
        ]
        self.transport.stub_action('action_1', body={})
        client = Client(
            handlers={
                SERVICE_NAME: ServiceHandler(
                    transport=self.transport,
                    serializer=self.serializer,
                    middleware=middleware,
                ),
            }
        )
        with self.assertRaises(RaiseExceptionOnResponseMiddleware.MiddlewareProcessedResponse):
            client.call_action(SERVICE_NAME, 'action_1')

    def test_response_middleware_handle_exception(self):
        middleware = [
            CatchExceptionOnResponseMiddleware(),
            RaiseExceptionOnResponseMiddleware(),
            MutateResponseMiddleware(),
        ]
        self.transport.stub_action('action_1', body={})
        client = Client(
            handlers={
                SERVICE_NAME: ServiceHandler(
                    transport=self.transport,
                    serializer=self.serializer,
                    middleware=middleware,
                ),
            }
        )
        with self.assertRaises(RaiseExceptionOnResponseMiddleware.MiddlewareProcessedResponse):
            client.call_action(SERVICE_NAME, 'action_1')
        self.assertEqual(client.handlers[SERVICE_NAME].middleware[0].request_count, 1)
        self.assertEqual(client.handlers[SERVICE_NAME].middleware[0].error_count, 1)
