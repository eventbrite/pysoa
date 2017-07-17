from __future__ import unicode_literals

from unittest import TestCase
import mock
import pytest

from pysoa.client.router import ClientRouter
from pysoa.client import Client
from pysoa.test.stub_service import StubClient


class TestClientRouter(TestCase):
    def setUp(self):
        self.config = {
            'clients': {
                'test': {
                    'transport': {
                        'path': 'pysoa.common.transport.base:ClientTransport',
                    },
                    'serializer': {
                        'path': 'pysoa.common.serializer.base:Serializer',
                    },
                    'middleware': [
                        {
                            'path': 'pysoa.client.middleware:ClientMiddleware',
                        },
                    ],
                },
            },
            'expansions': {
                'type_routes': {
                    'foo': {
                        'service': 'foo',
                        'action': 'get_foo',
                        'request_field': 'id',
                        'response_field': 'foo',
                    },
                    'bar': {
                        'service': 'bar',
                        'action': 'get_bar',
                        'request_field': 'id',
                        'response_field': 'bar',
                    },
                    'baz': {
                        'service': 'baz',
                        'action': 'get_baz',
                        'request_field': 'id',
                        'response_field': 'baz',
                    },
                    'qux': {
                        'service': 'qux',
                        'action': 'get_qux',
                        'request_field': 'id',
                        'response_field': 'qux',
                    },
                },
                'type_expansions': {
                    'foo': {
                        'bar': {
                            'type': 'bar',
                            'source_field': 'bar_id',
                            'dest_field': 'bar',
                        },
                        'baz': {
                            'type': 'baz',
                            'source_field': 'baz_id',
                            'dest_field': 'baz',
                        },
                    },
                    'baz': {
                        'qux': {
                            'type': 'qux',
                            'source_field': 'qux_id',
                            'dest_field': 'qux',
                        },
                    },
                },
            },
        }

    def test_client_initialized(self):
        router = ClientRouter(self.config)
        client = router.get_client('test')
        assert client.transport
        assert client.serializer
        assert client.middleware

    def test_get_non_cacheable_client(self):
        router = ClientRouter(self.config)
        client = router.get_client('test')
        assert isinstance(client, Client)
        client_again = router.get_client('test')
        assert client is not client_again

    def test_get_cacheable_client(self):
        self.config['clients']['test']['cacheable'] = True
        router = ClientRouter(self.config)
        client = router.get_client('test')
        assert isinstance(client, Client)
        client_again = router.get_client('test')
        assert client is client_again

    def test_unknown_service(self):
        router = ClientRouter(self.config)
        with self.assertRaises(router.ImproperlyConfigured):
            router.get_client('foo')

    @mock.patch('pysoa.client.Client.call_actions')
    def test_call_action(self, mock_call_actions):
        router = ClientRouter(self.config)
        action_request = {
            'action': 'action_request',
            'body': {
                'test_key': 'test_value',
            },
        }

        response = router.call_action(
            service_name='test',
            action_name=action_request['action'],
            body=action_request['body'],
        )

        mock_call_actions.assert_called_once_with(
            [action_request],
            context=mock.ANY,
            continue_on_error=False,
        )
        self.assertEqual(
            response,
            mock_call_actions.return_value,
        )

    @mock.patch('pysoa.client.router.ClientRouter.get_client')
    def test_call_action_with_expansions(self, mock_get_client):
        router = ClientRouter(self.config)
        expected_response = {
            'foo': {
                '_type': 'foo',
                'id': 1,
                'bar': {
                    '_type': 'bar',
                    'id': 2,
                },
                'baz': {
                    '_type': 'baz',
                    'id': 3,
                    'qux': {
                        '_type': 'qux',
                        'id': 4,
                    },
                },
            },
        }

        foo_client = StubClient('foo')
        foo_client.stub_action(
            'get_foo',
            body={
                'foo': {
                    '_type': 'foo',
                    'id': 1,
                    'bar_id': 2,
                    'baz_id': 3,
                },
            },
        )
        bar_client = StubClient('bar')
        bar_client.stub_action(
            'get_bar',
            body={
                'bar': {
                    '_type': 'bar',
                    'id': 2,
                },
            },
        )
        baz_client = StubClient('baz')
        baz_client.stub_action(
            'get_baz',
            body={
                'baz': {
                    '_type': 'baz',
                    'id': 3,
                    'qux_id': 4,
                },
            },
        )
        qux_client = StubClient('qux')
        qux_client.stub_action(
            'get_qux',
            body={
                'qux': {
                    '_type': 'qux',
                    'id': 4,
                },
            },
        )

        mock_clients = {
            'foo': foo_client,
            'bar': bar_client,
            'baz': baz_client,
            'qux': qux_client,
        }
        mock_get_client.side_effect = lambda x: mock_clients[x]

        response = router.call_action(
            service_name='foo',
            action_name='get_foo',
            body={
                'id': 1,
            },
            expansions={
                'foo': ['bar', 'baz.qux'],
            },
        )

        self.assertEqual(
            response.actions[0].body,
            expected_response,
        )
