from pysoa.client import Client
from pysoa.common.constants import ERROR_CODE_INVALID
from pysoa.common.types import (
    ActionRequest,
    JobRequest,
    ActionResponse,
    JobResponse,
)

from ..fixtures import (
    client_transport,
    serializer,
) # flake8: noqa

import pytest
import mock

SERVICE_NAME = 'test_service'


class TestClientSendReceive:
    """
    Test that the client send/receive methods return the correct types with the action responses
    set on the correct fields. Tests with both raw dict and JobRequest/ActionRequest where
    applicable.
    """

    def test_send_request_get_response(self, client_transport, serializer):
        request_dict = {
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

    def test_call_actions_raises_exception_on_error(self, client_transport, serializer):
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
        error_response = [
            {
                'code': ERROR_CODE_INVALID,
                'message': 'Invalid input',
                'field': 'foo',
            }
        ]
        client_transport.stub_action('action_1', errors=error_response)
        client_transport.stub_action('action_2', body={'baz': 3})
        client = Client(SERVICE_NAME, client_transport, serializer)
        for actions in (action_dicts, [ActionRequest(**a) for a in action_dicts]):
            with pytest.raises(Client.CallActionError) as e:
                client.call_actions(actions)
            assert len(e.value.actions) == 1
            assert e.value.actions[0].action == 'action_1'
            assert e.value.actions[0].errors == error_response

    def test_call_action(self, client_transport, serializer):
        client_transport.stub_action('action_1', body={'foo': 'bar'})
        client = Client(SERVICE_NAME, client_transport, serializer)
        response = client.call_action('action_1')
        assert isinstance(response, ActionResponse)
        assert response.action == 'action_1'
        assert response.body['foo'] == 'bar'
