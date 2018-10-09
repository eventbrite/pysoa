from __future__ import (
    absolute_import,
    unicode_literals,
)

import random

from pysoa.client import Client
from pysoa.common.types import (
    ActionRequest,
    ActionResponse,
    Error,
    JobResponse,
)
from pysoa.server.action import Action
from pysoa.server.errors import (
    ActionError,
    JobError,
)
from pysoa.server.server import Server
from pysoa.test.compatibility import mock
from pysoa.test.factories import ActionFactory
from pysoa.test.server import ServerTestCase
from pysoa.test.stub_service import stub_action


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


class TestStubAction(ServerTestCase):
    server_class = _TestServiceServer
    server_settings = {}

    def setUp(self):
        super(TestStubAction, self).setUp()

        self.secondary_stub_client = Client(_secondary_stub_client_settings)

    @stub_action('test_service', 'test_action_1')
    def test_one_stub_as_decorator(self, stub_test_action_1):
        stub_test_action_1.return_value = {'value': 1}

        response = self.client.call_action('test_service', 'test_action_1')
        self.assertEqual({'value': 1}, response.body)

        self.assertEqual(1, stub_test_action_1.call_count)
        self.assertEqual({}, stub_test_action_1.call_body)
        stub_test_action_1.assert_called_once_with({})

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
            [Error(code='BAD_ACTION', message='You are a bad actor')],
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
            [Error(code='BAD_ACTION', message='You are a bad actor')],
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

        request_id1 = self.client.send_request(
            'test_service',
            [
                {'action': 'test_action_1', 'body': {'menu': 'look'}},
                {'action': 'test_action_2'},
                {'action': 'test_action_1', 'body': {'pizza': 'pepperoni'}},
                {'action': 'test_action_2'},
                {'action': 'test_action_2'},
            ],
            continue_on_error=True,
        )
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
        self.assertEqual([Error(code='COOL', message='Another error')], response.actions[0].errors)

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
class TestStubActionAsDecoratedClass(ServerTestCase):
    server_class = _TestServiceServer
    server_settings = {}

    def setUp(self):
        super(TestStubActionAsDecoratedClass, self).setUp()

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
class TestStubActionAsStubAndPatchDecoratedClass(ServerTestCase):
    server_class = _TestServiceServer
    server_settings = {}

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
