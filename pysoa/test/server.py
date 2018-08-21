from __future__ import (
    absolute_import,
    unicode_literals,
)

import importlib
import os
import unittest

from pysoa.client import Client
from pysoa.test.assertions import (
    raises_call_action_error,
    raises_error_codes,
    raises_field_errors,
)


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
                settings_module = os.environ.get('PYSOA_SETTINGS_MODULE', None)
                if not settings_module:
                    self.fail('PYSOA_SETTINGS_MODULE environment variable must be set to run tests.')
                try:
                    thing = importlib.import_module(settings_module)
                    settings = thing.SOA_SERVER_SETTINGS
                except (ImportError, AttributeError) as e:
                    self.fail('Could not access {}.SOA_SERVER_SETTINGS: {}'.format(settings_module, e))

        self.client = Client(
            {
                self.server_class.service_name: {
                    'transport': {
                        'path': 'pysoa.common.transport.local:LocalClientTransport',
                        'kwargs': {
                            'server_class': self.server_class,
                            'server_settings': settings,
                        },
                    },
                },
            },
        )

    def call_action(self, action, body=None, service_name=None, **kwargs):
        # Using this enables tests that call the same action dozens of times to not have to code in the service name
        # for every single action call (but they still can by passing in `service_name`)
        return self.client.call_action(service_name or self.server_class.service_name, action, body=body, **kwargs)

    def assertActionRunsWithAndReturnErrors(self, action, body, **kwargs):
        with raises_call_action_error() as exc_info:
            self.call_action(action, body, **kwargs)
        return exc_info.soa_errors

    def assertActionRunsWithFieldErrors(self, action, body, field_errors, only=False, **kwargs):
        with raises_field_errors(field_errors, only=only):
            self.call_action(action, body, **kwargs)

    def assertActionRunsWithOnlyFieldErrors(self, action, body, field_errors, **kwargs):
        self.assertActionRunsWithFieldErrors(action, body, field_errors, only=True, **kwargs)

    def assertActionRunsWithErrorCodes(self, action, body, error_codes, only=False, **kwargs):
        with raises_error_codes(error_codes, only=only):
            self.call_action(action, body, **kwargs)

    def assertActionRunsWithOnlyErrorCodes(self, action, body, error_codes, **kwargs):
        self.assertActionRunsWithErrorCodes(action, body, error_codes, only=True, **kwargs)
