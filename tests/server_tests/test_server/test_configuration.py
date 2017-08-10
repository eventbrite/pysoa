import mock
from unittest import TestCase

from pysoa.server.server import Server
from pysoa.test import factories


class BaseTestServiceServer(Server):
    service_name = 'test_service'


class ServerInitializationTests(TestCase):

    def setUp(self):
        self.settings = factories.ServerSettingsFactory()

    def test_valid_configuration(self):
        BaseTestServiceServer(self.settings)

    def test_service_name_not_set(self):
        TestServiceServer = type(
            'TestServiceServer',
            (BaseTestServiceServer,),
            {
                'service_name': None,
            },
        )

        with self.assertRaises(AttributeError):
            TestServiceServer(self.settings)

    def test_settings_middleware_instantiation(self):
        test_class = mock.MagicMock()
        test_kwargs = {
            'key': 'val',
        }
        self.settings['middleware'].append({
            'object': test_class,
            'kwargs': test_kwargs,
        })
        BaseTestServiceServer(self.settings)
        test_class.assert_called_once_with(**test_kwargs)
