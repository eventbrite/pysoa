from unittest import TestCase

from pysoa.server.server import Server
from pysoa.common.serializer import Serializer
from pysoa.common.transport import ServerTransport


class BaseTestServiceServer(Server):
    service_name = 'test_service'


class ServerInitializationTests(TestCase):
    def test_valid_configuration(self):
        BaseTestServiceServer()

    def test_service_name_not_set(self):
        TestServiceServer = type(
            'TestServiceServer',
            (BaseTestServiceServer,),
            {
                'service_name': None,
            },
        )

        with self.assertRaises(AttributeError):
            TestServiceServer()
