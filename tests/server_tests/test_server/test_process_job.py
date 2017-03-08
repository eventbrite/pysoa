from unittest import TestCase
from mock import MagicMock

from pysoa.server.server import Server
from pysoa.server.errors import (
    JobError,
    ActionError,
)
from pysoa.server.types import Error
from pysoa.server.constants import ERROR_CODE_INVALID
from pysoa.common.serializer import Serializer
from pysoa.common.transport import ServerTransport


class TestServiceServer(Server):
    service_name = 'test_service'
    serializer = Serializer()
    transport = ServerTransport(service_name)

    action_class_map = {
        u'test_action': MagicMock(),
    }


class ProcessJobTests(TestCase):
    def setUp(self):
        self.job_request = {
            'control': {
                'switches': [],
                'continue_on_error': False,
                'correllation_id': u'1',
            },
            'actions': [{
                'action': u'test_action',
                'body': {
                    'field': 'value',
                },
            }],
        }
        self.server = TestServiceServer()

    def test_invalid_job_request_raises_job_error(self):
        # Invalidate the ControlHeader
        del self.job_request['control']['switches']

        with self.assertRaises(JobError) as e:
            self.server.process_request(self.job_request)

        self.assertEqual(len(e.exception.errors), 1)
        self.assertEqual(e.exception.errors[0].field, 'control.switches')

    def test_invalid_action_name_returns_action_response_with_error(self):
        # Invalidate the Action name
        self.job_request['actions'][0]['action'] = u'invalid_action'

        job_response = self.server.process_request(self.job_request)
        self.assertEqual(len(job_response.actions[0].errors), 1)
        self.assertEqual(job_response.actions[0].errors[0].field, 'action')

    def test_action_error_returns_action_response_with_error(self):
        # Make the Action return an ActionError
        self.server.action_class_map[u'test_action'].return_value.run.side_effect = ActionError(errors=[Error(
            code=ERROR_CODE_INVALID,
            message='This field is invalid.',
            field='body.field',
        )])

        job_response = self.server.process_request(self.job_request)
        self.assertEqual(len(job_response.actions[0].errors), 1)
        self.assertEqual(job_response.actions[0].errors[0].field, 'body.field')
