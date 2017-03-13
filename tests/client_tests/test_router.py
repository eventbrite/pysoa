from pysoa.client.router import ClientRouter
from pysoa.client import Client

from unittest import TestCase


class TestClientRouter(TestCase):

    def setUp(self):
        self.config = {
            'test': {
                'transport': {
                    'path': u'pysoa.common.transport:ClientTransport',
                },
                'serializer': {
                    'path': u'pysoa.common.serializer:Serializer',
                },
            }
        }

    def test_get_non_cacheable_client(self):
        router = ClientRouter(self.config)
        client = router.get_client('test')
        self.assertTrue(isinstance(client, Client))
        client_again = router.get_client('test')
        self.assertTrue(client is not client_again)

    def test_get_cacheable_client(self):
        self.config['test']['cacheable'] = True
        router = ClientRouter(self.config)
        client = router.get_client('test')
        self.assertTrue(isinstance(client, Client))
        client_again = router.get_client('test')
        self.assertTrue(client is client_again)

    def test_unknown_service(self):
        router = ClientRouter(self.config)
        with self.assertRaises(router.ImproperlyConfigured):
            router.get_client('foo')
