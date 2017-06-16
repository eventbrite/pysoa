from __future__ import unicode_literals

from pysoa.client.router import ClientRouter
from pysoa.client import Client

import pytest


class TestClientRouter:

    @pytest.fixture()
    def config(self):
        return {
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
        }

    def test_client_initialized(self, config):
        router = ClientRouter(config)
        client = router.get_client('test')
        assert client.transport
        assert client.serializer
        assert client.middleware

    def test_get_non_cacheable_client(self, config):
        router = ClientRouter(config)
        client = router.get_client('test')
        assert isinstance(client, Client)
        client_again = router.get_client('test')
        assert client is not client_again

    def test_get_cacheable_client(self, config):
        config['test']['cacheable'] = True
        router = ClientRouter(config)
        client = router.get_client('test')
        assert isinstance(client, Client)
        client_again = router.get_client('test')
        assert client is client_again

    def test_unknown_service(self, config):
        router = ClientRouter(config)
        with pytest.raises(router.ImproperlyConfigured):
            router.get_client('foo')
