from __future__ import (
    absolute_import,
    unicode_literals,
)

import sys
import traceback
import types
from typing import (
    Any,
    Dict,
    List,
)
from unittest import TestCase

from conformity import fields
from conformity.settings import SettingsData
import pytest
import six

from pysoa.client.client import Client
from pysoa.client.middleware import ClientMiddleware
from pysoa.common.constants import (
    ERROR_CODE_INVALID,
    ERROR_CODE_SERVER_ERROR,
)
from pysoa.common.errors import Error
from pysoa.common.transport.base import ClientTransport
from pysoa.common.transport.errors import (
    MessageReceiveError,
    MessageSendError,
)
from pysoa.common.types import (
    ActionRequest,
    ActionResponse,
    JobResponse,
)
from pysoa.server.errors import JobError
from pysoa.server.server import Server
from pysoa.test.compatibility import mock
from pysoa.test.stub_service import stub_action


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
        super(CatchExceptionOnRequestMiddleware, self).__init__(*args, **kwargs)  # type: ignore
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
        super(CatchExceptionOnResponseMiddleware, self).__init__(*args, **kwargs)  # type: ignore
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


def _job_error(*_, **__):
    def a(*_, **__):
        raise JobError(errors=[Error(code='BAD_JOB', message='You are a bad job')])

    return a


class ErrorServer(Server):
    service_name = 'error_service'

    # noinspection PyTypeChecker
    action_class_map = {
        'job_error': _job_error,
        'okay_action': lambda *_, **__: lambda *_, **__: ActionResponse(action='okay_action', body={'no_error': True}),
    }


@fields.ClassConfigurationSchema.provider(fields.Dictionary({}))
class SendErrorTransport(ClientTransport):
    def send_request_message(self, request_id, meta, body, message_expiry_in_seconds=None):
        raise MessageSendError('The message failed to send')

    def receive_response_message(self, receive_timeout_in_seconds=None):
        raise AssertionError('Something weird happened; receive should not have been called')


@fields.ClassConfigurationSchema.provider(fields.Dictionary({}))
class ReceiveErrorTransport(ClientTransport):
    def send_request_message(self, request_id, meta, body, message_expiry_in_seconds=None):
        pass  # We want this to silently do nothing

    def receive_response_message(self, receive_timeout_in_seconds=None):
        raise MessageReceiveError('Could not receive a message')


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
        }  # type: Dict[six.text_type, SettingsData]

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

    def test_send_request_with_suppress_response_then_get_response_error(self):
        """
        Client.send_request with suppress_response sends a valid request and Client.get_all_responses returns no
        response because the response was suppressed
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
            suppress_response=True,
        )
        self.assertTrue(request_id >= 0)
        responses = list(client.get_all_responses(SERVICE_NAME))
        self.assertEqual(len(responses), 0)

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
        ]  # type: List[Dict[six.text_type, Any]]
        client = Client(self.client_settings)

        for actions in (action_request, [ActionRequest(**a) for a in action_request]):
            response = client.call_actions(SERVICE_NAME, actions, timeout=2)  # type: ignore
            self.assertTrue(isinstance(response, JobResponse))
            self.assertTrue(all([isinstance(a, ActionResponse) for a in response.actions]))
            self.assertEqual(len(response.actions), 2)
            # ensure that the response is structured as expected
            self.assertEqual(response.actions[0].action, 'action_1')
            self.assertEqual(response.actions[0].body['foo'], 'bar')
            self.assertEqual(response.actions[1].action, 'action_2')
            self.assertEqual(response.actions[1].body['baz'], 3)

    def test_call_actions_suppress_response_is_ignored(self):
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
        ]  # type: List[Dict[six.text_type, Any]]
        client = Client(self.client_settings)

        for actions in (action_request, [ActionRequest(**a) for a in action_request]):
            with pytest.raises(TypeError):
                # noinspection PyArgumentList
                client.call_actions(SERVICE_NAME, actions, timeout=2, suppress_response=True)  # type: ignore

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
        ]  # type: List[Dict[six.text_type, Any]]
        error_expected = Error(code=ERROR_CODE_INVALID, message='Invalid input', field='foo')
        self.client_settings[SERVICE_NAME]['transport']['kwargs']['action_map']['action_1'] = {
            'errors': [error_expected],
        }
        client = Client(self.client_settings)

        for actions in (action_request, [ActionRequest(**a) for a in action_request]):
            with self.assertRaises(Client.CallActionError) as e:
                client.call_actions(SERVICE_NAME, actions)  # type: ignore
            self.assertEqual(len(e.exception.actions), 1)
            self.assertEqual(e.exception.actions[0].action, 'action_1')
            error_response = e.exception.actions[0].errors
            self.assertEqual(len(error_response), 1)
            self.assertEqual(error_response[0].code, error_expected.code)
            self.assertEqual(error_response[0].message, error_expected.message)
            self.assertEqual(error_response[0].field, error_expected.field)

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
        ]  # type: List[Dict[six.text_type, Any]]
        error_expected = Error(code=ERROR_CODE_INVALID, message='Invalid input', field='foo', is_caller_error=True)
        self.client_settings[SERVICE_NAME]['transport']['kwargs']['action_map']['action_2'] = {
            'errors': [error_expected],
        }
        client = Client(self.client_settings)
        for actions in (action_request, [ActionRequest(**a) for a in action_request]):
            response = client.call_actions(SERVICE_NAME, actions, raise_action_errors=False)  # type: ignore
            self.assertEqual(response.actions[0].body, {'foo': 'bar'})
            self.assertEqual(response.actions[1].errors, [error_expected])
            self.assertIsNotNone(response.context['correlation_id'])

    def test_call_actions_raises_exception_on_job_error(self):
        """Client.call_actions raises Client.JobError when a JobError occurs on the server."""
        errors = [Error(code=ERROR_CODE_SERVER_ERROR, message='Something went wrong!')]
        with mock.patch(
            'pysoa.server.server.Server.execute_job',
            new=mock.Mock(side_effect=JobError(errors)),
        ):
            client = Client(self.client_settings)
            with self.assertRaises(Client.JobError) as e:
                client.call_action(SERVICE_NAME, 'action_1')
            self.assertEqual(e.exception.errors, errors)

    def test_call_action(self):
        """Client.call_action sends a valid request and returns a valid response without errors."""
        client = Client(self.client_settings)
        response = client.call_action(SERVICE_NAME, 'action_1')
        self.assertTrue(isinstance(response, ActionResponse))
        self.assertEqual(response.action, 'action_1')
        self.assertEqual(response.body['foo'], 'bar')

    def test_call_action_job_error_not_raised(self):
        client = Client({
            'error_service': {
                'transport': {
                    'path': 'pysoa.common.transport.local:LocalClientTransport',
                    'kwargs': {
                        'server_class': ErrorServer,
                        'server_settings': {},
                    },
                },
            }
        })
        response = client.call_action('error_service', 'job_error', raise_job_errors=False)

        self.assertIsNotNone(response)
        self.assertEqual([Error(code='BAD_JOB', message='You are a bad job')], response)


class TestClientParallelSendReceive(TestCase):
    """
    Test that the client parallel send/receive methods work as expected.
    """
    def setUp(self):
        self.client = Client({
            'service_1': {
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
            'service_2': {
                'transport': {
                    'path': 'pysoa.test.stub_service:StubClientTransport',
                    'kwargs': {
                        'action_map': {
                            'action_3': {'body': {'cat': 'dog'}},
                            'action_4': {'body': {'selected': True, 'count': 7}},
                            'action_with_errors': {
                                'errors': [Error(code=ERROR_CODE_INVALID, message='Invalid input', field='foo')],
                            },
                        },
                    },
                },
            },
            'error_service': {
                'transport': {
                    'path': 'pysoa.common.transport.local:LocalClientTransport',
                    'kwargs': {
                        'server_class': ErrorServer,
                        'server_settings': {},
                    },
                },
            },
            'send_error_service': {
                'transport': {
                    'path': 'tests.integration.test_send_receive:SendErrorTransport',
                }
            },
            'receive_error_service': {
                'transport': {
                    'path': 'tests.integration.test_send_receive:ReceiveErrorTransport',
                }
            },
        })

    def test_call_actions_parallel(self):
        """
        Test that call_actions_parallel works to call multiple actions run parallel on a single service.
        """
        action_responses = self.client.call_actions_parallel(
            'service_1',
            [ActionRequest(action='action_1'), ActionRequest(action='action_2'), ActionRequest(action='action_1')],
        )

        self.assertIsNotNone(action_responses)
        self.assertIsInstance(action_responses, types.GeneratorType)

        action_responses_list = list(action_responses)
        self.assertEqual(3, len(action_responses_list))
        self.assertEqual({'foo': 'bar'}, action_responses_list[0].body)
        self.assertEqual({'baz': 3}, action_responses_list[1].body)
        self.assertEqual({'foo': 'bar'}, action_responses_list[2].body)

    def test_call_actions_parallel_suppress_response_is_prohibited(self):
        """
        Test that call_actions_parallel works to call multiple actions run parallel on a single service.
        """
        with pytest.raises(TypeError):
            # noinspection PyArgumentList
            self.client.call_actions_parallel(  # type: ignore
                'service_1',
                [ActionRequest(action='action_1'), ActionRequest(action='action_2'), ActionRequest(action='action_1')],
                suppress_response=True,
            )

    def test_call_actions_parallel_with_extras(self):
        """
        Test that call_actions_parallel works to call multiple actions run parallel on a single service using extra
        kwargs to more finely control behavior.
        """
        action_responses = self.client.call_actions_parallel(
            'service_2',
            [
                ActionRequest(action='action_3'),
                ActionRequest(action='action_with_errors'),
                ActionRequest(action='action_4'),
            ],
            timeout=2,
            raise_action_errors=False,
        )

        self.assertIsNotNone(action_responses)

        action_responses_list = list(action_responses)
        self.assertEqual(3, len(action_responses_list))
        self.assertEqual({'cat': 'dog'}, action_responses_list[0].body)
        self.assertEqual({}, action_responses_list[1].body)
        self.assertEqual(
            [Error(code=ERROR_CODE_INVALID, message='Invalid input', field='foo', is_caller_error=True)],
            action_responses_list[1].errors,
        )
        self.assertEqual({'selected': True, 'count': 7}, action_responses_list[2].body)

    def test_call_actions_parallel_with_job_errors_not_raised(self):
        action_responses = self.client.call_actions_parallel(
            'error_service',
            [
                ActionRequest(action='okay_action'),
                ActionRequest(action='job_error'),
                ActionRequest(action='okay_action'),
            ],
            timeout=2,
            raise_job_errors=False,
        )

        self.assertIsNotNone(action_responses)

        action_responses_list = list(action_responses)
        self.assertEqual(3, len(action_responses_list))
        self.assertEqual({'no_error': True}, action_responses_list[0].body)
        self.assertEqual([Error(code='BAD_JOB', message='You are a bad job')], action_responses_list[1])
        self.assertEqual({'no_error': True}, action_responses_list[2].body)

    def test_call_actions_parallel_with_transport_errors_caught(self):
        original_send = self.client.send_request
        side_effect_context = {'call': 0}
        error = MessageSendError('Hello!')

        def side_effect(*args, **kwargs):
            side_effect_context['call'] += 1
            if side_effect_context['call'] == 2:
                raise error
            return original_send(*args, **kwargs)

        with mock.patch.object(self.client, 'send_request') as mock_send_request:
            mock_send_request.side_effect = side_effect

            action_responses = self.client.call_actions_parallel(
                'error_service',
                [
                    ActionRequest(action='okay_action'),
                    ActionRequest(action='job_error'),
                    ActionRequest(action='okay_action'),
                ],
                timeout=2,
                catch_transport_errors=True,
            )

        self.assertIsNotNone(action_responses)

        action_responses_list = list(action_responses)
        self.assertEqual(3, len(action_responses_list))
        self.assertEqual({'no_error': True}, action_responses_list[0].body)
        self.assertIs(error, action_responses_list[1])
        self.assertEqual({'no_error': True}, action_responses_list[2].body)

    def test_call_actions_parallel_action_errors_raised(self):
        """
        Test that call_actions_parallel raises action errors when they occur
        """
        with self.assertRaises(self.client.CallActionError) as error_context:
            self.client.call_actions_parallel(
                'service_2',
                [
                    ActionRequest(action='action_3'),
                    ActionRequest(action='action_with_errors'),
                ],
            )

        self.assertEqual(
            [Error(code=ERROR_CODE_INVALID, message='Invalid input', field='foo', is_caller_error=True)],
            error_context.exception.actions[0].errors,
        )

    def test_call_actions_parallel_job_errors_raised(self):
        """
        Test that call_actions_parallel raises job errors when they occur
        """
        with self.assertRaises(self.client.JobError) as error_context:
            self.client.call_actions_parallel('error_service', [{'action': 'job_error'}])

        self.assertEqual([Error(code='BAD_JOB', message='You are a bad job')], error_context.exception.errors)

    def test_call_actions_parallel_transport_send_errors_raised(self):
        """
        Test that call_actions_parallel raises transport send errors when they occur
        """
        with self.assertRaises(MessageSendError) as error_context:
            self.client.call_actions_parallel('send_error_service', [{'action': 'does_not_matter'}])

        self.assertEqual('The message failed to send', error_context.exception.args[0])

    def test_call_actions_parallel_transport_receive_errors_raised(self):
        """
        Test that call_actions_parallel raises transport receive errors when they occur
        """
        with self.assertRaises(MessageReceiveError) as error_context:
            self.client.call_actions_parallel('receive_error_service', [{'action': 'does_not_matter'}])

        self.assertEqual('Could not receive a message', error_context.exception.args[0])

    def test_call_jobs_parallel_simple(self):
        """
        Test that call_jobs_parallel works properly under fairly simple circumstances (no errors).
        """
        job_responses = self.client.call_jobs_parallel(
            [
                {'service_name': 'service_1', 'actions': [{'action': 'action_2'}, {'action': 'action_1'}]},
                {'service_name': 'service_2', 'actions': [{'action': 'action_4'}]},
                {'service_name': 'service_2', 'actions': [{'action': 'action_3'}]},
            ],
        )

        self.assertIsNotNone(job_responses)

        self.assertEqual(3, len(job_responses))
        self.assertEqual(2, len(job_responses[0].actions))
        self.assertEqual({'baz': 3}, job_responses[0].actions[0].body)
        self.assertEqual({'foo': 'bar'}, job_responses[0].actions[1].body)
        self.assertEqual(1, len(job_responses[1].actions))
        self.assertEqual({'selected': True, 'count': 7}, job_responses[1].actions[0].body)
        self.assertEqual(1, len(job_responses[2].actions))
        self.assertEqual({'cat': 'dog'}, job_responses[2].actions[0].body)

    def test_call_jobs_parallel_job_errors_not_raised(self):
        """
        Test that call_jobs_parallel returns job errors instead of raising them when asked.
        """
        job_responses = self.client.call_jobs_parallel(
            [
                {'service_name': 'service_1', 'actions': [{'action': 'action_1'}, {'action': 'action_2'}]},
                {'service_name': 'error_service', 'actions': [{'action': 'job_error'}]},
                {'service_name': 'service_2', 'actions': [{'action': 'action_3'}]},
                {'service_name': 'service_2', 'actions': [{'action': 'action_4'}]},
            ],
            raise_job_errors=False,
        )

        self.assertIsNotNone(job_responses)

        self.assertEqual(4, len(job_responses))
        self.assertEqual(2, len(job_responses[0].actions))
        self.assertEqual({'foo': 'bar'}, job_responses[0].actions[0].body)
        self.assertEqual({'baz': 3}, job_responses[0].actions[1].body)
        self.assertEqual(0, len(job_responses[1].actions))
        self.assertEqual([Error(code='BAD_JOB', message='You are a bad job')], job_responses[1].errors)
        self.assertEqual(1, len(job_responses[2].actions))
        self.assertEqual({'cat': 'dog'}, job_responses[2].actions[0].body)
        self.assertEqual(1, len(job_responses[3].actions))
        self.assertEqual({'selected': True, 'count': 7}, job_responses[3].actions[0].body)

    def test_call_jobs_parallel_transport_send_errors_caught(self):
        """
        Test that call_jobs_parallel returns transport send errors instead of raising them when asked.
        """
        job_responses = self.client.call_jobs_parallel(
            [
                {'service_name': 'service_1', 'actions': [{'action': 'action_1'}, {'action': 'action_2'}]},
                {'service_name': 'send_error_service', 'actions': [{'action': 'no matter'}]},
                {'service_name': 'service_2', 'actions': [{'action': 'action_3'}]},
                {'service_name': 'service_2', 'actions': [{'action': 'action_4'}]},
            ],
            catch_transport_errors=True,
        )

        self.assertIsNotNone(job_responses)

        self.assertEqual(4, len(job_responses))
        self.assertEqual(2, len(job_responses[0].actions))
        self.assertEqual({'foo': 'bar'}, job_responses[0].actions[0].body)
        self.assertEqual({'baz': 3}, job_responses[0].actions[1].body)

        r1 = job_responses[1]
        assert isinstance(r1, MessageSendError)
        self.assertEqual('The message failed to send', r1.args[0])

        self.assertEqual(1, len(job_responses[2].actions))
        self.assertEqual({'cat': 'dog'}, job_responses[2].actions[0].body)
        self.assertEqual(1, len(job_responses[3].actions))
        self.assertEqual({'selected': True, 'count': 7}, job_responses[3].actions[0].body)

    def test_call_jobs_parallel_transport_receive_errors_caught(self):
        """
        Test that call_jobs_parallel returns transport send errors instead of raising them when asked.
        """
        job_responses = self.client.call_jobs_parallel(
            [
                {'service_name': 'service_1', 'actions': [{'action': 'action_1'}, {'action': 'action_2'}]},
                {'service_name': 'receive_error_service', 'actions': [{'action': 'no matter'}]},
                {'service_name': 'service_2', 'actions': [{'action': 'action_3'}]},
                {'service_name': 'service_2', 'actions': [{'action': 'action_4'}]},
            ],
            catch_transport_errors=True,
        )

        self.assertIsNotNone(job_responses)

        self.assertEqual(4, len(job_responses))
        self.assertEqual(2, len(job_responses[0].actions))
        self.assertEqual({'foo': 'bar'}, job_responses[0].actions[0].body)
        self.assertEqual({'baz': 3}, job_responses[0].actions[1].body)

        r1 = job_responses[1]
        assert isinstance(r1, MessageReceiveError)
        self.assertEqual('Could not receive a message', r1.args[0])

        self.assertEqual(1, len(job_responses[2].actions))
        self.assertEqual({'cat': 'dog'}, job_responses[2].actions[0].body)
        self.assertEqual(1, len(job_responses[3].actions))
        self.assertEqual({'selected': True, 'count': 7}, job_responses[3].actions[0].body)

    def test_call_jobs_parallel_transport_multiple_send_and_receive_errors_caught(self):
        """
        Test that call_jobs_parallel returns transport send errors instead of raising them when asked.
        """
        job_responses = self.client.call_jobs_parallel(
            [
                {'service_name': 'service_1', 'actions': [{'action': 'action_1'}, {'action': 'action_2'}]},
                {'service_name': 'send_error_service', 'actions': [{'action': 'no'}]},
                {'service_name': 'service_2', 'actions': [{'action': 'action_3'}]},
                {'service_name': 'send_error_service', 'actions': [{'action': 'no'}, {'action': 'no'}]},
                {'service_name': 'receive_error_service', 'actions': [{'action': 'no'}]},
                {'service_name': 'service_2', 'actions': [{'action': 'action_4'}]},
                {'service_name': 'receive_error_service', 'actions': [{'action': 'no'}, {'action': 'no'}]},
                {'service_name': 'receive_error_service', 'actions': [{'action': 'no'}]},
                {'service_name': 'receive_error_service', 'actions': [{'action': 'no'}, {'action': 'no'}]},
            ],
            catch_transport_errors=True,
        )

        self.assertIsNotNone(job_responses)

        self.assertEqual(9, len(job_responses))
        self.assertEqual(2, len(job_responses[0].actions))
        self.assertEqual({'foo': 'bar'}, job_responses[0].actions[0].body)
        self.assertEqual({'baz': 3}, job_responses[0].actions[1].body)

        r1 = job_responses[1]
        assert isinstance(r1, MessageSendError)
        self.assertEqual('The message failed to send', r1.args[0])

        self.assertEqual(1, len(job_responses[2].actions))
        self.assertEqual({'cat': 'dog'}, job_responses[2].actions[0].body)

        r3 = job_responses[3]
        assert isinstance(r3, MessageSendError)
        self.assertEqual('The message failed to send', r3.args[0])

        r4 = job_responses[4]
        assert isinstance(r4, MessageReceiveError)
        self.assertEqual('Could not receive a message', r4.args[0])

        self.assertEqual(1, len(job_responses[5].actions))
        self.assertEqual({'selected': True, 'count': 7}, job_responses[5].actions[0].body)

        r6 = job_responses[6]
        assert isinstance(r6, MessageReceiveError)
        self.assertEqual('Could not receive a message', r6.args[0])

        r7 = job_responses[7]
        assert isinstance(r7, MessageReceiveError)
        self.assertEqual('Could not receive a message', r7.args[0])


class TestFutureSendReceive(TestCase):
    @stub_action('future_service', 'present_sounds', errors=[{'code': 'BROKEN', 'message': 'Broken, dude'}])
    def test_call_action_future_error(self, mock_present_sounds):
        client = Client({})

        future = client.call_action_future('future_service', 'present_sounds', body={'hello': 'world'})

        mock_present_sounds.assert_called_once_with({'hello': 'world'})

        with self.assertRaises(client.CallActionError) as error_context:
            assert future.result()

        first_exception = error_context.exception

        assert len(error_context.exception.actions[0].errors) == 1

        error = error_context.exception.actions[0].errors[0]
        assert error.code == 'BROKEN'
        assert error.message == 'Broken, dude'

        with self.assertRaises(client.CallActionError) as error_context:
            assert future.result()

        assert error_context.exception is first_exception

        assert len(error_context.exception.actions[0].errors) == 1

        error = error_context.exception.actions[0].errors[0]
        assert error.code == 'BROKEN'
        assert error.message == 'Broken, dude'

        with self.assertRaises(client.CallActionError) as error_context:
            assert future.result()

        assert error_context.exception is first_exception

        assert len(error_context.exception.actions[0].errors) == 1

        error = error_context.exception.actions[0].errors[0]
        assert error.code == 'BROKEN'
        assert error.message == 'Broken, dude'

        mock_present_sounds.assert_called_once_with({'hello': 'world'})

    @stub_action('future_service', 'present_sounds', body={'goodbye': 'universe'})
    def test_call_action_future_success(self, mock_present_sounds):
        client = Client({})

        future = client.call_action_future('future_service', 'present_sounds', body={'hello': 'world'})

        mock_present_sounds.assert_called_once_with({'hello': 'world'})

        assert future.running() is True
        assert future.done() is False

        response = future.result()

        assert future.running() is False
        assert future.done() is True

        assert response.errors == []
        assert response.body == {'goodbye': 'universe'}
        assert response.action == 'present_sounds'

        assert future.result() is response
        assert future.result() is response

        mock_present_sounds.assert_called_once_with({'hello': 'world'})

    @stub_action('future_service', 'present_sounds', errors=[{'code': 'BROKEN', 'message': 'Broken, dude'}])
    def test_call_action_future_verify_traceback(self, mock_present_sounds):
        client = Client({})

        future = client.call_action_future('future_service', 'present_sounds', body={'hello': 'world'})

        try:
            assert future.result()
            assert False, 'We should not have hit this line of code'
        except client.CallActionError:
            _, __, tb1 = sys.exc_info()

        try:
            assert future.result()
            assert False, 'We should not have hit this line of code'
        except client.CallActionError:
            _, __, tb2 = sys.exc_info()

        try:
            assert future.result()
            assert False, 'We should not have hit this line of code'
        except client.CallActionError:
            _, __, tb3 = sys.exc_info()

        assert traceback.format_tb(tb1)[1:] == traceback.format_tb(tb2)[2:]
        assert traceback.format_tb(tb2)[2:] == traceback.format_tb(tb3)[2:]

    @stub_action('future_service', 'present_sounds', errors=[{'code': 'BROKEN', 'message': 'Broken, dude'}])
    def test_call_actions_future_error(self, mock_present_sounds):
        client = Client({})

        future = client.call_actions_future(
            'future_service',
            [{'action': 'present_sounds', 'body': {'foo': 'bar'}}],
        )

        mock_present_sounds.assert_called_once_with({'foo': 'bar'})

        with self.assertRaises(client.CallActionError) as error_context:
            raise future.exception()  # type: ignore

        first_exception = error_context.exception

        assert len(error_context.exception.actions[0].errors) == 1

        error = error_context.exception.actions[0].errors[0]
        assert error.code == 'BROKEN'
        assert error.message == 'Broken, dude'

        with self.assertRaises(client.CallActionError) as error_context:
            assert future.result()

        assert error_context.exception is first_exception

        assert len(error_context.exception.actions[0].errors) == 1

        error = error_context.exception.actions[0].errors[0]
        assert error.code == 'BROKEN'
        assert error.message == 'Broken, dude'

        with self.assertRaises(client.CallActionError) as error_context:
            raise future.exception()  # type: ignore

        assert error_context.exception is first_exception

        assert len(error_context.exception.actions[0].errors) == 1

        error = error_context.exception.actions[0].errors[0]
        assert error.code == 'BROKEN'
        assert error.message == 'Broken, dude'

        mock_present_sounds.assert_called_once_with({'foo': 'bar'})

    @stub_action('future_service', 'present_sounds', body={'baz': 'qux'})
    def test_call_actions_future_success(self, mock_present_sounds):
        client = Client({})

        future = client.call_actions_future(
            'future_service',
            [{'action': 'present_sounds', 'body': {'foo': 'bar'}}],
        )

        mock_present_sounds.assert_called_once_with({'foo': 'bar'})

        assert future.exception() is None

        response = future.result()

        assert response.errors == []
        assert response.actions[0].errors == []
        assert response.actions[0].body == {'baz': 'qux'}
        assert response.context == {}

        assert future.result() is response
        assert future.result() is response

        assert future.exception() is None

        mock_present_sounds.assert_called_once_with({'foo': 'bar'})

    @stub_action('future_service', 'past_sounds', errors=[{'code': 'BROKEN', 'message': 'Broken, too'}])
    @stub_action('future_service', 'present_sounds', body={'when': 'present'})
    def test_call_actions_parallel_future_error(self, mock_present_sounds, mock_past_sounds):
        client = Client({})

        future = client.call_actions_parallel_future(
            'future_service',
            [
                {'action': 'present_sounds', 'body': {'where': 'here'}},
                {'action': 'past_sounds', 'body': {'where': 'there'}},
            ],
        )

        mock_present_sounds.assert_called_once_with({'where': 'here'})
        mock_past_sounds.assert_called_once_with({'where': 'there'})

        with self.assertRaises(client.CallActionError) as error_context:
            future.result()

        first_exception = error_context.exception

        assert len(error_context.exception.actions[0].errors) == 1

        error = error_context.exception.actions[0].errors[0]
        assert error.code == 'BROKEN'
        assert error.message == 'Broken, too'

        with self.assertRaises(client.CallActionError) as error_context:
            future.result()

        assert error_context.exception is first_exception

        assert len(error_context.exception.actions[0].errors) == 1

        error = error_context.exception.actions[0].errors[0]
        assert error.code == 'BROKEN'
        assert error.message == 'Broken, too'

        with self.assertRaises(client.CallActionError) as error_context:
            future.result()

        assert error_context.exception is first_exception

        assert len(error_context.exception.actions[0].errors) == 1

        error = error_context.exception.actions[0].errors[0]
        assert error.code == 'BROKEN'
        assert error.message == 'Broken, too'

        mock_present_sounds.assert_called_once_with({'where': 'here'})
        mock_past_sounds.assert_called_once_with({'where': 'there'})

    @stub_action('future_service', 'past_sounds', body={'when': 'past'})
    @stub_action('future_service', 'present_sounds', body={'when': 'present'})
    def test_call_actions_parallel_future_success(self, mock_present_sounds, mock_past_sounds):
        client = Client({})

        future = client.call_actions_parallel_future(
            'future_service',
            [
                {'action': 'present_sounds', 'body': {'where': 'here'}},
                {'action': 'past_sounds', 'body': {'where': 'there'}},
            ],
        )

        mock_present_sounds.assert_called_once_with({'where': 'here'})
        mock_past_sounds.assert_called_once_with({'where': 'there'})

        assert isinstance(future.result(), types.GeneratorType)

        responses = list(future.result())

        assert len(responses) == 2

        assert responses[0].errors == []
        assert responses[0].action == 'present_sounds'
        assert responses[0].body == {'when': 'present'}

        assert responses[1].errors == []
        assert responses[1].action == 'past_sounds'
        assert responses[1].body == {'when': 'past'}

    @stub_action('future_service', 'past_sounds', errors=[{'code': 'BROKEN', 'message': 'Broken, too'}])
    @stub_action('future_service', 'present_sounds', body={'when': 'present'})
    def test_call_jobs_parallel_future_error(self, mock_present_sounds, mock_past_sounds):
        client = Client({})

        future = client.call_jobs_parallel_future(
            [
                {'service_name': 'future_service', 'actions': [
                    {'action': 'present_sounds', 'body': {'where': 'here'}},
                ]},
                {'service_name': 'future_service', 'actions': [
                    {'action': 'past_sounds', 'body': {'where': 'there'}},
                ]},
            ],
        )

        mock_present_sounds.assert_called_once_with({'where': 'here'})
        mock_past_sounds.assert_called_once_with({'where': 'there'})

        with self.assertRaises(client.CallActionError) as error_context:
            assert future.result()

        first_exception = error_context.exception

        assert len(error_context.exception.actions[0].errors) == 1

        error = error_context.exception.actions[0].errors[0]
        assert error.code == 'BROKEN'
        assert error.message == 'Broken, too'

        with self.assertRaises(client.CallActionError) as error_context:
            assert future.result()

        assert error_context.exception is first_exception

        assert len(error_context.exception.actions[0].errors) == 1

        error = error_context.exception.actions[0].errors[0]
        assert error.code == 'BROKEN'
        assert error.message == 'Broken, too'

        with self.assertRaises(client.CallActionError) as error_context:
            assert future.result()

        assert error_context.exception is first_exception

        assert len(error_context.exception.actions[0].errors) == 1

        error = error_context.exception.actions[0].errors[0]
        assert error.code == 'BROKEN'
        assert error.message == 'Broken, too'

        mock_present_sounds.assert_called_once_with({'where': 'here'})
        mock_past_sounds.assert_called_once_with({'where': 'there'})

    @stub_action('future_service', 'past_sounds', body={'when': 'past'})
    @stub_action('future_service', 'present_sounds', body={'when': 'present'})
    def test_call_jobs_parallel_future_success(self, mock_present_sounds, mock_past_sounds):
        client = Client({})

        future = client.call_jobs_parallel_future(
            [
                {'service_name': 'future_service', 'actions': [
                    {'action': 'present_sounds', 'body': {'where': 'here'}},
                ]},
                {'service_name': 'future_service', 'actions': [
                    {'action': 'past_sounds', 'body': {'where': 'there'}},
                ]},
            ],
        )

        mock_present_sounds.assert_called_once_with({'where': 'here'})
        mock_past_sounds.assert_called_once_with({'where': 'there'})

        assert len(future.result()) == 2

        assert future.result()[0].actions[0].errors == []
        assert future.result()[0].actions[0].action == 'present_sounds'
        assert future.result()[0].actions[0].body == {'when': 'present'}

        assert future.result()[1].actions[0].errors == []
        assert future.result()[1].actions[0].action == 'past_sounds'
        assert future.result()[1].actions[0].body == {'when': 'past'}


# noinspection PyProtectedMember
class TestClientMiddleware(object):
    """Test that the client calls its middleware correctly."""

    @staticmethod
    def create_client(*middleware):
        return Client({
            SERVICE_NAME: {
                'transport': {
                    'path': 'pysoa.test.stub_service:StubClientTransport',
                    'kwargs': {
                        'action_map': {
                            'action_1': {'body': {}},
                        },
                    },
                },
                'middleware': [
                    {'path': 'tests.integration.test_send_receive:{}'.format(m)} for m in middleware
                ],
            }
        })

    def test_request_single_middleware(self):
        # Need to manually set the middleware on the handler, since the middleware is defined in this file
        # and cannot be
        client = self.create_client('RaiseExceptionOnRequestMiddleware')
        with pytest.raises(RaiseExceptionOnRequestMiddleware.MiddlewareProcessedRequest):
            client.call_action(SERVICE_NAME, 'action_1', body={'middleware_was_here': True})

    def test_request_multiple_middleware_order(self):
        # The first middleware mutates the response so that the second raises an exception
        client = self.create_client('MutateRequestMiddleware', 'RaiseExceptionOnRequestMiddleware')
        with pytest.raises(RaiseExceptionOnRequestMiddleware.MiddlewareProcessedRequest):
            client.call_action(SERVICE_NAME, 'action_1', control_extra={'test_request_middleware': True})

        # If the order is reversed, no exception is raised
        client = self.create_client('RaiseExceptionOnRequestMiddleware', 'MutateRequestMiddleware')
        client.call_action(SERVICE_NAME, 'action_1', control_extra={'test_request_middleware': True})

    def test_request_middleware_handle_exception(self):
        # the exception handler must be on the outer layer of the onion
        client = self.create_client(
            'CatchExceptionOnRequestMiddleware',
            'MutateRequestMiddleware',
            'RaiseExceptionOnRequestMiddleware',
        )
        with pytest.raises(RaiseExceptionOnRequestMiddleware.MiddlewareProcessedRequest):
            client.call_action(SERVICE_NAME, 'action_1', control_extra={'test_request_middleware': True})
        assert client.handlers[SERVICE_NAME]._middleware[0].request_count == 1
        assert client.handlers[SERVICE_NAME]._middleware[0].error_count == 1

    def test_response_single_middleware(self):
        client = self.create_client('RaiseExceptionOnResponseMiddleware')
        client._get_handler(SERVICE_NAME).transport.stub_action('action_1', body={'middleware_was_here': True})
        with pytest.raises(RaiseExceptionOnResponseMiddleware.MiddlewareProcessedResponse):
            client.call_action(SERVICE_NAME, 'action_1')

    def test_response_multiple_middleware_order(self):
        client = self.create_client('RaiseExceptionOnResponseMiddleware', 'MutateResponseMiddleware')
        with pytest.raises(RaiseExceptionOnResponseMiddleware.MiddlewareProcessedResponse):
            client.call_action(SERVICE_NAME, 'action_1')

    def test_response_middleware_handle_exception(self):
        client = self.create_client(
            'CatchExceptionOnResponseMiddleware',
            'RaiseExceptionOnResponseMiddleware',
            'MutateResponseMiddleware',
        )
        with pytest.raises(RaiseExceptionOnResponseMiddleware.MiddlewareProcessedResponse):
            client.call_action(SERVICE_NAME, 'action_1')
        assert client.handlers[SERVICE_NAME]._middleware[0].request_count == 1
        assert client.handlers[SERVICE_NAME]._middleware[0].error_count == 1
