from __future__ import (
    absolute_import,
    unicode_literals,
)

from unittest import TestCase

from pysoa.common.constants import ERROR_CODE_INVALID
from pysoa.common.errors import Error
from pysoa.server.errors import ActionError
from pysoa.server.middleware import ServerMiddleware
from pysoa.server.server import Server
from pysoa.test import factories


class ProcessJobServer(Server):
    """
    Stub server to test against.
    """
    service_name = 'test_service'
    action_class_map = {
        'respond_actionerror': factories.ActionFactory(exception=ActionError(errors=[Error(
            code=ERROR_CODE_INVALID,
            message='This field is invalid.',
            field='body.field',
        )])),
        'respond_empty': factories.ActionFactory(),
    }


class ProcessJobMiddleware(ServerMiddleware):
    """
    Test middleware that fiddles with responses.
    """

    class SuccessException(Exception):
        """Raised when a middleware successfully intercepts something."""

    def job(self, process):
        def handler(request):
            if request.control.get('test_job_middleware'):
                result = process(request)
                result.actions[0].body['middleware'] = True
                return result
            else:
                return process(request)
        return handler

    def action(self, process):
        def handler(request):
            if request.body.get('test_action_middleware'):
                result = process(request)
                result.body['middleware'] = True
                return result
            else:
                return process(request)
        return handler


class TestProcessJob(TestCase):
    """
    Main process_job test suite.
    """

    def setUp(self):
        # Make a new server instance each time
        settings = factories.ServerSettingsFactory()
        settings['middleware'].append({'object': ProcessJobMiddleware})
        self.server = ProcessJobServer(settings=settings)

    def make_job(self, action, body):
        """
        Makes a basic job request object.
        """
        return {
            'control': {
                'continue_on_error': False,
            },
            'context': {
                'switches': [],
                'correlation_id': '1',
            },
            'actions': [{
                'action': action,
                'body': body,
            }],
        }

    def test_invalid_job_request_returns_job_response_error(self):
        """
        Tests that removing "switches" from the control header triggers
        the schema checker for it.
        """
        # Make a bad request
        job_request = self.make_job('respond_empty', {})
        del job_request['context']['switches']
        # Process it
        job_response = self.server.process_job(job_request)
        # Make sure we got an error
        self.assertEqual(len(job_response.errors), 1)
        self.assertEqual(job_response.errors[0].field, 'context.switches')

    def test_invalid_action_name_returns_action_response_with_error(self):
        """
        Tests that sending an invalid action name triggers an error.
        """
        # Make a bad request
        job_request = self.make_job('invalid_action', {})
        job_response = self.server.process_job(job_request)
        # Make sure there's an error in that action's section
        self.assertEqual(len(job_response.actions), 1)
        self.assertEqual(len(job_response.actions[0].errors), 1)
        self.assertEqual(job_response.actions[0].errors[0].field, 'action')

    def test_action_error_returns_action_response_with_error(self):
        """
        Tests that an ActionError raised from an action comes through correctly
        """
        # We send to a premade failure action
        job_request = self.make_job('respond_actionerror', {})
        job_response = self.server.process_job(job_request)
        # Check it came through right
        self.assertEqual(len(job_response.actions), 1)
        self.assertEqual(len(job_response.actions[0].errors), 1)
        self.assertEqual(job_response.actions[0].errors[0].field, 'body.field')

    def test_job_middleware(self):
        """
        Tests that the job middleware runs
        """
        # Send an empty request/response set with a control header set
        job_request = self.make_job('respond_empty', {})
        job_request['control']['test_job_middleware'] = True
        job_response = self.server.process_job(job_request)
        # Make sure the middleware set a flag in it
        self.assertEqual(len(job_response.actions), 1)
        self.assertEqual(job_response.actions[0].body, {'middleware': True})

    def test_action_middleware(self):
        """
        Tests that the action middleware runs
        """
        # Send an empty request/response set with body data
        job_request = self.make_job('respond_empty', {})
        job_request['actions'][0]['body']['test_action_middleware'] = True
        job_response = self.server.process_job(job_request)
        # Make sure the middleware set a flag in it
        self.assertEqual(len(job_response.actions), 1)
        self.assertEqual(job_response.actions[0].body, {'middleware': True})
