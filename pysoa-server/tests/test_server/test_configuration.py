from unittest import TestCase

from soaserver.server import Server
from soacommon.serializer import Serializer
from soacommon.transport import ServerTransport


class BaseTestServiceServer(Server):
    service_name = 'test_service'
    serializer = Serializer()
    transport = ServerTransport()


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

    def test_serializer_not_set(self):
        TestServiceServer = type(
            'TestServiceServer',
            (BaseTestServiceServer,),
            {
                'serializer': None,
            },
        )

        with self.assertRaises(AttributeError):
            TestServiceServer()

    def test_transport_not_set(self):
        TestServiceServer = type(
            'TestServiceServer',
            (BaseTestServiceServer,),
            {
                'transport': None,
            },
        )

        with self.assertRaises(AttributeError):
            TestServiceServer()
