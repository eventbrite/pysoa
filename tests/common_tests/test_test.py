from __future__ import unicode_literals

from pysoa.test.stub_service import StubClient
from pysoa.common.constants import ERROR_CODE_INVALID
from pysoa.common.types import JobRequest

import attr
import pytest


@pytest.fixture
def client():
    return StubClient()


class TestStubClient:

    def test_stub_action_body_only(self, client):
        """
        StubClient.stub_action with a 'body' argument causes the client to return an action
        response with the given body.
        """
        response_body = {'foo': 'bar'}
        client.stub_action('test_action', body=response_body)
        response = client.call_action('test_action')
        assert response.body == response_body

    def test_stub_action_errors(self, client):
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
        client.stub_action('test_action', errors=errors)
        with pytest.raises(StubClient.CallActionError) as e:
            client.call_action('test_action')
            error_response = e.value.actions[0].errors
            assert len(error_response) == 1
            assert error_response[0].code == errors[0]['code']
            assert error_response[0].message == errors[0]['message']
            assert error_response[0].field == errors[0]['field']

    def test_stub_action_errors_and_body(self, client):
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
        client.stub_action('test_action', errors=errors, body=response_body)
        with pytest.raises(StubClient.CallActionError) as e:
            client.call_action('test_action')
            error_response = e.value.actions[0].errors
            assert len(error_response) == 1
            assert error_response[0].code == errors[0]['code']
            assert error_response[0].message == errors[0]['message']
            assert error_response[0].field == errors[0]['field']

    def test_multiple_requests(self, client):
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
        client.stub_action('action_1', **responses['action_1'])
        client.stub_action('action_2', **responses['action_2'])
        client.stub_action('action_3', **responses['action_3'])

        control = client.make_control_header()
        request_1 = JobRequest(control=control, actions=[{'action': 'action_1'}, {'action': 'action_2'}])
        request_2 = JobRequest(control=control, actions=[{'action': 'action_2'}, {'action': 'action_1'}])
        request_3 = JobRequest(control=control, actions=[{'action': 'action_3'}])

        # Store requests by request ID for later verification, because order is not guaranteed
        requests_by_id = {}
        for request in (request_1, request_2, request_3):
            request_id = client.send_request(request)
            requests_by_id[request_id] = request

        for response_id, response in client.get_all_responses():
            # The client returned the same number of actions as were requested
            assert len(response.actions) == len(requests_by_id[response_id].actions)
            for i in range(len(response.actions)):
                action_response = response.actions[i]
                # The action name returned matches the action name in the request
                assert action_response.action == requests_by_id[response_id].actions[i].action
                # The action response matches the expected response
                # Errors are returned as the Error type, so convert them to dict first
                assert action_response.body == responses[action_response.action]['body']
                assert [attr.asdict(e) for e in action_response.errors] == responses[action_response.action]['errors']
