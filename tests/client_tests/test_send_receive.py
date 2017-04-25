from __future__ import unicode_literals

from pysoa.client import Client
from pysoa.client.middleware import ClientMiddleware
from pysoa.common.constants import (
    ERROR_CODE_INVALID,
    ERROR_CODE_SERVER_ERROR,
)
from pysoa.common.types import (
    ActionRequest,
    JobRequest,
    ActionResponse,
    JobResponse,
    Error,
)
from pysoa.server.errors import JobError

from ..fixtures import (
    client_transport,
    serializer,
)  # flake8: noqa

import pytest
import mock

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


class TestClientSendReceive:
    """
    Test that the client send/receive methods return the correct types with the action responses
    set on the correct fields. Tests with both raw dict and JobRequest/ActionRequest where
    applicable.
    """

    def test_send_request_get_response(self, client_transport, serializer):
        """
        Client.send_request sends a valid request and Client.get_all_responses returns a valid response
        without errors.
        """
        request_dict={
            'actions': [
                {
                    'action': 'action_1',
                    'body': {},
                },
                {
                    'action': 'action_2',
                    'body': {},
                },
            ]
        }
        client_transport.stub_action('action_1', body={'foo': 'bar'})
        client_transport.stub_action('action_2', body={'baz': 3})
        client = Client(SERVICE_NAME, client_transport, serializer)
        request_dict['control'] = client.make_control_header()

        for request in (request_dict, JobRequest(**request_dict)):
            responses = list(client.get_all_responses())
            assert len(responses) == 0

            request_id = client.send_request(request)
            assert request_id >= 0
            responses = list(client.get_all_responses())
            assert len(responses) == 1
            response_id, response = responses[0]
            # ensure that the response is structured as expected
            assert response_id == request_id
            assert isinstance(response, JobResponse)
            assert all([isinstance(a, ActionResponse) for a in response.actions])
            assert response.actions[0].action == 'action_1'
            assert response.actions[0].body['foo'] == 'bar'
            assert response.actions[1].action == 'action_2'
            assert response.actions[1].body['baz'] == 3

    def test_call_actions(self, client_transport, serializer):
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
        client_transport.stub_action('action_1', body={'foo': 'bar'})
        client_transport.stub_action('action_2', body={'baz': 3})
        client = Client(SERVICE_NAME, client_transport, serializer)

        for actions in (action_dicts, [ActionRequest(**a) for a in action_dicts]):
            response = client.call_actions(actions)
            assert isinstance(response, JobResponse)
            assert all([isinstance(a, ActionResponse) for a in response.actions])
            assert len(response.actions) == 2
            # ensure that the response is structured as expected
            assert response.actions[0].action == 'action_1'
            assert response.actions[0].body['foo'] == 'bar'
            assert response.actions[1].action == 'action_2'
            assert response.actions[1].body['baz'] == 3

    def test_call_actions_raises_exception_on_action_error(self, client_transport, serializer):
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
        client_transport.stub_action('action_1', errors=error_expected)
        client_transport.stub_action('action_2', body={'baz': 3})
        client = Client(SERVICE_NAME, client_transport, serializer)
        for actions in (action_dicts, [ActionRequest(**a) for a in action_dicts]):
            with pytest.raises(Client.CallActionError) as e:
                client.call_actions(actions)
            assert len(e.value.actions) == 1
            assert e.value.actions[0].action == 'action_1'
            error_response = e.value.actions[0].errors
            assert len(error_response) == 1
            assert error_response[0].code == error_expected[0]['code']
            assert error_response[0].message == error_expected[0]['message']
            assert error_response[0].field == error_expected[0]['field']

    def test_call_actions_raises_exception_on_job_error(self, client_transport, serializer):
        """Client.call_actions raises Client.JobError when a JobError occurs on the server."""
        client = Client(SERVICE_NAME, client_transport, serializer)
        client.transport.stub_action('action_1', body={})
        errors = [Error(code=ERROR_CODE_SERVER_ERROR, message='Something went wrong!')]
        with mock.patch.object(client.transport.server, 'execute_job', new=mock.Mock(side_effect=JobError(errors))):
            with pytest.raises(Client.JobError) as e:
                client.call_action('action_1')
                assert e.errors == errors

    def test_call_action(self, client_transport, serializer):
        """Client.call_action sends a valid request and returns a valid response without errors."""
        client_transport.stub_action('action_1', body={'foo': 'bar'})
        client = Client(SERVICE_NAME, client_transport, serializer)
        response = client.call_action('action_1')
        assert isinstance(response, ActionResponse)
        assert response.action == 'action_1'
        assert response.body['foo'] == 'bar'


class TestClientMiddleware:
    """Test that the client calls its middleware correctly."""

    def test_request_single_middleware(self, client_transport, serializer):
        middleware = [RaiseExceptionOnRequestMiddleware()]
        client = Client(SERVICE_NAME, client_transport, serializer, middleware=middleware)
        with pytest.raises(RaiseExceptionOnRequestMiddleware.MiddlewareProcessedRequest):
            client.call_action('action_1', body={'middleware_was_here': True})

    def test_request_multiple_middleware_order(self, client_transport, serializer):
        client_transport.stub_action('action_1', body={})

        # The first middleware mutates the response so that the second raises an exception
        middleware = [
            MutateRequestMiddleware(),
            RaiseExceptionOnRequestMiddleware(),
        ]
        client = Client(SERVICE_NAME, client_transport, serializer, middleware=middleware)
        with pytest.raises(RaiseExceptionOnRequestMiddleware.MiddlewareProcessedRequest):
            client.call_action('action_1', control_extra={'test_request_middleware': True})

        # If the order is reversed, no exception is raised
        middleware = reversed(middleware)
        client = Client(SERVICE_NAME, client_transport, serializer, middleware=middleware)
        client.call_action('action_1', control_extra={'test_request_middleware': True})

    def test_request_middleware_handle_exception(self, client_transport, serializer):
        # the exception handler must be on the outer layer of the onion
        middleware = [
            CatchExceptionOnRequestMiddleware(),
            MutateRequestMiddleware(),
            RaiseExceptionOnRequestMiddleware(),
        ]
        client = Client(SERVICE_NAME, client_transport, serializer, middleware=middleware)
        with pytest.raises(RaiseExceptionOnRequestMiddleware.MiddlewareProcessedRequest):
            client.call_action('action_1', control_extra={'test_request_middleware': True})
        assert client.middleware[0].request_count == 1
        assert client.middleware[0].error_count == 1

    def test_response_single_middleware(self, client_transport, serializer):
        middleware = [RaiseExceptionOnResponseMiddleware()]
        client_transport.stub_action('action_1', body={'middleware_was_here': True})
        client = Client(SERVICE_NAME, client_transport, serializer, middleware=middleware)
        with pytest.raises(RaiseExceptionOnResponseMiddleware.MiddlewareProcessedResponse):
            client.call_action('action_1')

    def test_response_multiple_middleware_order(self, client_transport, serializer):
        middleware = [
            RaiseExceptionOnResponseMiddleware(),
            MutateResponseMiddleware(),
        ]
        client_transport.stub_action('action_1', body={})
        client = Client(SERVICE_NAME, client_transport, serializer, middleware=middleware)
        with pytest.raises(RaiseExceptionOnResponseMiddleware.MiddlewareProcessedResponse):
            client.call_action('action_1')

    def test_response_middleware_handle_exception(self, client_transport, serializer):
        middleware = [
            CatchExceptionOnResponseMiddleware(),
            RaiseExceptionOnResponseMiddleware(),
            MutateResponseMiddleware(),
        ]
        client_transport.stub_action('action_1', body={})
        client = Client(SERVICE_NAME, client_transport, serializer, middleware=middleware)
        with pytest.raises(RaiseExceptionOnResponseMiddleware.MiddlewareProcessedResponse):
            client.call_action('action_1')
        assert client.middleware[0].request_count == 1
        assert client.middleware[0].error_count == 1
