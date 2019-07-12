from __future__ import (
    absolute_import,
    unicode_literals,
)

import uuid

import pytest
import six

from pysoa.server.schemas import (
    ActionRequestSchema,
    ContextHeaderSchema,
    ControlHeaderSchema,
    JobRequestSchema,
)


class TestControlHeaderSchema:

    @pytest.fixture()
    def control_header(self):
        return {'continue_on_error': False}

    def test_valid_control_header(self, control_header):
        errors = ControlHeaderSchema.errors(control_header)
        assert not errors

    def test_missing_continue_on_error(self, control_header):
        del control_header['continue_on_error']
        errors = ControlHeaderSchema.errors(control_header)
        assert len(errors) == 1
        assert errors[0].pointer == 'continue_on_error'

    def test_invalid_continue_on_error(self, control_header):
        control_header['continue_on_error'] = 'True'
        errors = ControlHeaderSchema.errors(control_header)
        assert len(errors) == 1
        assert errors[0].pointer == 'continue_on_error'


class TestContextHeaderSchema:

    @pytest.fixture()
    def context_header(self):
        return {
            'switches': [1, 2, 3],
            'correlation_id': six.u(str(uuid.uuid4())),
        }

    def test_missing_switches(self, context_header):
        del context_header['switches']
        errors = ContextHeaderSchema.errors(context_header)
        assert len(errors) == 1
        assert errors[0].pointer == 'switches'

    def test_invalid_switches(self, context_header):
        context_header['switches'] = '1, 2, 3'
        errors = ContextHeaderSchema.errors(context_header)
        assert len(errors) == 1
        assert errors[0].pointer == 'switches'

    def test_empty_switches(self, context_header):
        context_header['switches'] = []
        errors = ContextHeaderSchema.errors(context_header)
        assert not errors

    def test_invalid_switch(self, context_header):
        context_header['switches'][2] = 'three'
        errors = ContextHeaderSchema.errors(context_header)
        assert len(errors) == 1
        assert errors[0].pointer == 'switches.2'

    def test_missing_correlation_id(self, context_header):
        del context_header['correlation_id']
        errors = ContextHeaderSchema.errors(context_header)
        assert len(errors) == 1
        assert errors[0].pointer == 'correlation_id'

    def test_invalid_correlation_id(self, context_header):
        context_header['correlation_id'] = 1
        errors = ContextHeaderSchema.errors(context_header)
        assert len(errors) == 1
        assert errors[0].pointer == 'correlation_id'


class TestActionRequestSchema:

    @pytest.fixture()
    def action(self):
        return {
            'action': 'test_action_name',
            'body': {
                'first_name': 'Bob',
                'last_name': 'Mueller',
            },
        }

    def test_valid_action(self, action):
        errors = ActionRequestSchema.errors(action)
        assert not errors

    def test_missing_action(self, action):
        del action['action']
        errors = ActionRequestSchema.errors(action)
        assert len(errors) == 1
        assert errors[0].pointer == 'action'

    def test_invalid_action(self, action):
        action['action'] = b'non-unicode_action_name'
        errors = ActionRequestSchema.errors(action)
        assert len(errors) == 1
        assert errors[0].pointer == 'action'

    def test_optional_body(self, action):
        del action['body']
        errors = ActionRequestSchema.errors(action)
        assert not errors

    def test_invalid_body(self, action):
        action['body'] = 'invalid body'
        errors = ActionRequestSchema.errors(action)
        assert len(errors) == 1
        assert errors[0].pointer == 'body'


class TestJobRequestSchema:

    @pytest.fixture()
    def job(self):
        return {
            'control': {
                'continue_on_error': False,
            },
            'context': {
                'switches': [1, 2, 3],
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

    def test_valid_job(self, job):
        errors = JobRequestSchema.errors(job)
        assert not errors

    def test_missing_control(self, job):
        del job['control']
        errors = JobRequestSchema.errors(job)
        assert len(errors) == 1
        assert errors[0].pointer == 'control'

    def test_invalid_control(self, job):
        job['control'] = 'invalid control type'
        errors = JobRequestSchema.errors(job)
        assert len(errors) == 1
        assert errors[0].pointer == 'control'

    def test_missing_actions(self, job):
        del job['actions']
        errors = JobRequestSchema.errors(job)
        assert len(errors) == 1
        assert errors[0].pointer == 'actions'

    def test_invalid_actions(self, job):
        job['actions'] = 'invalid actions type'
        errors = JobRequestSchema.errors(job)
        assert len(errors) == 1
        assert errors[0].pointer == 'actions'

    def test_empty_actions(self, job):
        job['actions'] = []
        errors = JobRequestSchema.errors(job)
        assert len(errors) == 1
        assert errors[0].pointer == 'actions'
