from __future__ import unicode_literals

import os
import unittest

import six

from pysoa.client import Client


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
        try:
            self.call_action(action, body, **kwargs)
            # If we got here, it ran with no errors, so fail
            raise self.failureException('Action ran without any of the expected errors')
        except self.client.CallActionError as e:
            return e.actions[0].errors

    def assertActionRunsWithFieldErrors(self, action, body, field_errors, only=False, **kwargs):
        raised_errors = self.assertActionRunsWithAndReturnErrors(action, body, **kwargs)

        unexpected_errors = []
        missing_errors = []

        # Provide the flexibility for them to pass it a set or list of error codes, or a single code, per field
        for field, errors in six.iteritems(field_errors):
            if not isinstance(errors, set):
                if isinstance(errors, list):
                    field_errors[field] = set(errors)
                else:
                    field_errors[field] = {errors}

        # Go through all the errors returned by the action, mark any that are unexpected, remove any that match
        for error in raised_errors:
            if not getattr(error, 'field', None):
                unexpected_errors.append((error.code, error.message))
                continue

            if error.field not in field_errors:
                unexpected_errors.append({error.field: (error.code, error.message)})
                continue

            if error.code not in field_errors[error.field]:
                unexpected_errors.append({error.field: (error.code, error.message)})
                continue

            field_errors[error.field].remove(error.code)
            if not field_errors[error.field]:
                del field_errors[error.field]

        # Go through all the remaining expected errors that weren't matched
        for field, errors in six.iteritems(field_errors):
            for error in errors:
                missing_errors.append({field: error})

        error_msg = ''
        if missing_errors:
            error_msg = 'Expected field errors not found in response: {}'.format(str(missing_errors))

        if only and unexpected_errors:
            if error_msg:
                error_msg += '\n'
            error_msg += 'Unexpected errors found in response: {}'.format(str(unexpected_errors))

        if error_msg:
            # If we have any cause to error, do so
            raise self.failureException(error_msg)

    def assertActionRunsWithOnlyFieldErrors(self, action, body, field_errors, **kwargs):
        self.assertActionRunsWithFieldErrors(action, body, field_errors, only=True, **kwargs)

    def assertActionRunsWithErrorCodes(self, action, body, error_codes, only=False, **kwargs):
        raised_errors = self.assertActionRunsWithAndReturnErrors(action, body, **kwargs)

        if not isinstance(error_codes, set):
            if isinstance(error_codes, list):
                error_codes = set(error_codes)
            else:
                error_codes = {error_codes}

        unexpected_errors = []
        missing_errors = []

        # Go through all the errors returned by the action, mark any that are unexpected, remove any that match
        for error in raised_errors:
            if getattr(error, 'field', None):
                unexpected_errors.append({error.field: (error.code, error.message)})
                continue

            if error.code not in error_codes:
                unexpected_errors.append((error.code, error.message))
                continue

            error_codes.remove(error.code)

        # Go through all the remaining expected errors that weren't matched
        for error in error_codes:
            missing_errors.append(error)

        error_msg = ''
        if missing_errors:
            error_msg = 'Expected errors not found in response: {}'.format(str(missing_errors))

        if only and unexpected_errors:
            if error_msg:
                error_msg += '\n'
            error_msg += 'Unexpected errors found in response: {}'.format(str(unexpected_errors))

        if error_msg:
            # If we have any cause to error, do so
            raise self.failureException(error_msg)

    def assertActionRunsWithOnlyErrorCodes(self, action, body, error_codes, **kwargs):
        self.assertActionRunsWithErrorCodes(action, body, error_codes, only=True, **kwargs)
