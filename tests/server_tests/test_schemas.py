from __future__ import unicode_literals

import six
import uuid
from unittest import TestCase

from pysoa.server.schemas import (
    ActionRequestSchema,
    ControlHeaderSchema,
    JobRequestSchema,
)


class ControlHeaderSchemaTests(TestCase):
    def setUp(self):
        self.control_header = {
            'switches': [1, 2, 3],
            'continue_on_error': False,
            'correlation_id': six.u(str(uuid.uuid4())),
        }

    def test_valid_control_header(self):
        errors = ControlHeaderSchema.errors(self.control_header)
        self.assertFalse(errors)

    def test_missing_switches(self):
        del self.control_header['switches']
        errors = ControlHeaderSchema.errors(self.control_header)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].pointer, 'switches')

    def test_invalid_switches(self):
        self.control_header['switches'] = '1, 2, 3'
        errors = ControlHeaderSchema.errors(self.control_header)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].pointer, 'switches')

    def test_empty_switches(self):
        self.control_header['switches'] = []
        errors = ControlHeaderSchema.errors(self.control_header)
        self.assertFalse(errors)

    def test_invalid_switch(self):
        self.control_header['switches'][2] = 'three'
        errors = ControlHeaderSchema.errors(self.control_header)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].pointer, 'switches.2')

    def test_missing_continue_on_error(self):
        del self.control_header['continue_on_error']
        errors = ControlHeaderSchema.errors(self.control_header)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].pointer, 'continue_on_error')

    def test_invalid_continue_on_error(self):
        self.control_header['continue_on_error'] = 'True'
        errors = ControlHeaderSchema.errors(self.control_header)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].pointer, 'continue_on_error')

    def test_missing_correlation_id(self):
        del self.control_header['correlation_id']
        errors = ControlHeaderSchema.errors(self.control_header)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].pointer, 'correlation_id')

    def test_invalid_correlation_id(self):
        self.control_header['correlation_id'] = 1
        errors = ControlHeaderSchema.errors(self.control_header)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].pointer, 'correlation_id')


class ActionRequestSchemaTests(TestCase):
    def setUp(self):
        self.action = {
            'action': 'test_action_name',
            'body': {
                'first_name': 'Bob',
                'last_name': 'Mueller',
            },
        }

    def test_valid_action(self):
        errors = ActionRequestSchema.errors(self.action)
        self.assertFalse(errors)

    def test_missing_action(self):
        del self.action['action']
        errors = ActionRequestSchema.errors(self.action)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].pointer, 'action')

    def test_invalid_action(self):
        self.action['action'] = b'non-unicode_action_name'
        errors = ActionRequestSchema.errors(self.action)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].pointer, 'action')

    def test_optional_body(self):
        del self.action['body']
        errors = ActionRequestSchema.errors(self.action)
        self.assertFalse(errors)

    def test_invalid_body(self):
        self.action['body'] = 'invalid body'
        errors = ActionRequestSchema.errors(self.action)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].pointer, 'body')


class JobRequestSchemaTests(TestCase):
    def setUp(self):
        self.job = {
            'control': {
                'switches': [1, 2, 3],
                'continue_on_error': False,
                'correlation_id': six.u(str(uuid.uuid4())),
            },
            'actions': [{
                'action': 'test_action_name',
                'body': {
                    'first_name': 'Bob',
                    'last_name': 'Mueller',
                },
            }],
        }

    def test_valid_job(self):
        errors = JobRequestSchema.errors(self.job)
        self.assertFalse(errors)

    def test_missing_control(self):
        del self.job['control']
        errors = JobRequestSchema.errors(self.job)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].pointer, 'control')

    def test_invalid_control(self):
        self.job['control'] = 'invalid control type'
        errors = JobRequestSchema.errors(self.job)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].pointer, 'control')

    def test_missing_actions(self):
        del self.job['actions']
        errors = JobRequestSchema.errors(self.job)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].pointer, 'actions')

    def test_invalid_actions(self):
        self.job['actions'] = 'invalid actions type'
        errors = JobRequestSchema.errors(self.job)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].pointer, 'actions')

    def test_empty_actions(self):
        self.job['actions'] = []
        errors = JobRequestSchema.errors(self.job)
        self.assertFalse(errors)
