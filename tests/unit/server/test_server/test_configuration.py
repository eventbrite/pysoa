from __future__ import (
    absolute_import,
    unicode_literals,
)

from unittest import TestCase

from pysoa.server.server import Server
from pysoa.test import factories
from pysoa.test.compatibility import mock


class BaseTestServiceServer(Server):
    service_name = 'test_service'


class TestServerInitialization(TestCase):

    def setUp(self):
        self.settings = factories.ServerSettingsFactory.build()

    def test_valid_configuration(self):
        BaseTestServiceServer(self.settings)

    def test_service_name_not_set(self):
        TestServiceServer = type(
            str('TestServiceServer'),
            (BaseTestServiceServer,),
            {
                str('service_name'): None,
            },
        )

        with self.assertRaises(AttributeError):
            TestServiceServer(self.settings)

    def test_middleware(self):
        self.settings['middleware'].clear()
        BaseTestServiceServer(self.settings)
