import os
import unittest

from pysoa.client import Client
from pysoa.common.serializer import MsgpackSerializer
from pysoa.common.transport.local import LocalClientTransport


class ServerTestCase(unittest.TestCase):
    """
    Base class for test cases that need to call the server.

    It runs calls to actions through the server stack so they get middleware run
    (for things like request.metrics) and requests/responses run through a
    serializer cycle.
    """

    server_class = None
    server_settings = None

    def setUp(self):
        super(ServerTestCase, self).setUp()

        if self.server_class is None:
            raise RuntimeError('You must specify server_class in ServerTestCase subclasses')

        # Get settings based on Django mode
        if self.server_settings is not None:
            settings = self.server_settings
        else:
            if self.server_class.use_django:
                from django.conf import settings
                settings = settings.SOA_SERVER_SETTINGS
            else:
                settings = os.environ.get('PYSOA_SETTINGS_MODULE', None)
                if not settings:
                    self.fail(
                        'PYSOA_SETTINGS_MODULE environment variable must be set to run tests.'
                    )

        # Set up a transport with a local server
        self.transport = LocalClientTransport(
            self.server_class.service_name,
            self.server_class,
            server_settings=settings,
        )

        self.serializer = MsgpackSerializer()

        self.client = Client(
            self.server_class.service_name,
            self.transport,
            self.serializer,
        )
