from __future__ import absolute_import, unicode_literals

import random

import mock

from pysoa.client import Client
from pysoa.common.types import (
    ActionRequest,
    Error,
)
from pysoa.server.action import Action
from pysoa.server.errors import ActionError
from pysoa.server.server import Server
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
