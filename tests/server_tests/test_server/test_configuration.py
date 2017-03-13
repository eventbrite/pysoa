from unittest import TestCase

from pysoa.server.server import Server
from pysoa.common.serializer import Serializer
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
