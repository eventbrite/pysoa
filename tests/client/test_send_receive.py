from __future__ import absolute_import, unicode_literals

from unittest import TestCase

from pysoa.client.client import Client
from pysoa.client.middleware import ClientMiddleware
from pysoa.common.constants import (
    ERROR_CODE_INVALID,
    ERROR_CODE_SERVER_ERROR,
)
from pysoa.common.transport.base import (
    ClientTransport,
)
from pysoa.common.transport.exceptions import (
    MessageReceiveError,
    MessageSendError,
)
from pysoa.common.types import (
    ActionRequest,
    ActionResponse,
    JobResponse,
    Error,
)
from pysoa.server.errors import JobError
from pysoa.server.server import Server
from pysoa.test.compatibility import mock


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


class ErrorServer(Server):
    service_name = 'error_service'

    # noinspection PyTypeChecker
    action_class_map = {
        'job_error': lambda *_, **__: (_ for _ in ()).throw(
            JobError(errors=[Error(code='BAD_JOB', message='You are a bad job')])
        ),
    }


class SendErrorTransport(ClientTransport):
    def send_request_message(self, request_id, meta, body, message_expiry_in_seconds=None):
        raise MessageSendError('The message failed to send')

    def receive_response_message(self, receive_timeout_in_seconds=None):
        raise AssertionError('Something weird happened; receive should not have been called')


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
            response = client.call_actions(SERVICE_NAME, actions, timeout=2)
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
                    'path': 'tests.client.test_send_receive:SendErrorTransport',
                }
            },
            'receive_error_service': {
                'transport': {
                    'path': 'tests.client.test_send_receive:ReceiveErrorTransport',
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

        action_responses = list(action_responses)
        self.assertEqual(3, len(action_responses))
        self.assertEqual({'foo': 'bar'}, action_responses[0].body)
        self.assertEqual({'baz': 3}, action_responses[1].body)
        self.assertEqual({'foo': 'bar'}, action_responses[2].body)

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
            continue_on_error=True,
        )

        self.assertIsNotNone(action_responses)

        action_responses = list(action_responses)
        self.assertEqual(3, len(action_responses))
        self.assertEqual({'cat': 'dog'}, action_responses[0].body)
        self.assertEqual({}, action_responses[1].body)
        self.assertEqual(
            [Error(code=ERROR_CODE_INVALID, message='Invalid input', field='foo')],
            action_responses[1].errors,
        )
        self.assertEqual({'selected': True, 'count': 7}, action_responses[2].body)

    def test_call_actions_parallel_with_prohibited_arguments(self):
        """
        Test that call_actions_parallel doesn't permit raise_job_errors or catch_transport_error arguments
        """
        with self.assertRaises(TypeError):
            self.client.call_actions_parallel(
                'service_2',
                [ActionRequest(action='action_3')],
                raise_job_errors=False,
            )

        with self.assertRaises(TypeError):
            self.client.call_actions_parallel(
                'service_2',
                [ActionRequest(action='action_3')],
                catch_transport_errors=False,
            )

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
            [Error(code=ERROR_CODE_INVALID, message='Invalid input', field='foo')],
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
        self.assertIsInstance(job_responses[1], MessageSendError)
        self.assertEqual('The message failed to send', job_responses[1].args[0])
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
        self.assertIsInstance(job_responses[1], MessageReceiveError)
        self.assertEqual('Could not receive a message', job_responses[1].args[0])
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
        self.assertIsInstance(job_responses[1], MessageSendError)
        self.assertEqual('The message failed to send', job_responses[1].args[0])
        self.assertEqual(1, len(job_responses[2].actions))
        self.assertEqual({'cat': 'dog'}, job_responses[2].actions[0].body)
        self.assertIsInstance(job_responses[3], MessageSendError)
        self.assertEqual('The message failed to send', job_responses[3].args[0])
        self.assertIsInstance(job_responses[4], MessageReceiveError)
        self.assertEqual('Could not receive a message', job_responses[4].args[0])
        self.assertEqual(1, len(job_responses[5].actions))
        self.assertEqual({'selected': True, 'count': 7}, job_responses[5].actions[0].body)
        self.assertIsInstance(job_responses[6], MessageReceiveError)
        self.assertEqual('Could not receive a message', job_responses[6].args[0])
        self.assertIsInstance(job_responses[7], MessageReceiveError)
        self.assertEqual('Could not receive a message', job_responses[7].args[0])


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
