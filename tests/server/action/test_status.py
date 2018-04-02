from __future__ import absolute_import, print_function, unicode_literals

import platform
import unittest

import conformity
from conformity.fields.basic import Boolean
import six

import pysoa
from pysoa.common.types import ActionResponse
from pysoa.server.action.status import (
    BaseStatusAction,
    make_default_status_action_class,
    StatusActionFactory,
)
from pysoa.server.types import EnrichedActionRequest


class _ComplexStatusAction(BaseStatusAction):
    _version = '7.8.9'

    _build = 'complex_service-28381-7.8.9-16_04'

    def check_good(self):
        self.diagnostics['check_good_called'] = True

    @staticmethod
    def check_warnings():
        return (
            (False, 'FIRST_CODE', 'First warning'),
            (False, 'SECOND_CODE', 'Second warning'),
        )

    @staticmethod
    def check_errors():
        return [
            [True, 'ANOTHER_CODE', 'This is an error'],
        ]


class TestBaseStatusAction(unittest.TestCase):
    def test_cannot_instantiate_base_action(self):
        with self.assertRaises(TypeError):
            BaseStatusAction()

    def test_basic_status_works(self):
        action_request = EnrichedActionRequest(action='status', body={}, switches=None)

        response = StatusActionFactory('1.2.3', 'example_service-72-1.2.3-python3')()(action_request)

        self.assertIsInstance(response, ActionResponse)
        self.assertEqual(
            {
                'build': 'example_service-72-1.2.3-python3',
                'conformity': six.text_type(conformity.__version__),
                'healthcheck': {'diagnostics': {}, 'errors': [], 'warnings': []},
                'pysoa': six.text_type(pysoa.__version__),
                'python': six.text_type(platform.python_version()),
                'version': '1.2.3',
            },
            response.body,
        )

    def test_complex_status_body_none_works(self):
        action_request = EnrichedActionRequest(action='status', body=None, switches=None)

        response = _ComplexStatusAction()(action_request)

        self.assertIsInstance(response, ActionResponse)
        self.assertEqual(
            {
                'build': 'complex_service-28381-7.8.9-16_04',
                'conformity': six.text_type(conformity.__version__),
                'healthcheck': {
                    'diagnostics': {'check_good_called': True},
                    'errors': [('ANOTHER_CODE', 'This is an error')],
                    'warnings': [('FIRST_CODE', 'First warning'), ('SECOND_CODE', 'Second warning')],
                },
                'pysoa': six.text_type(pysoa.__version__),
                'python': six.text_type(platform.python_version()),
                'version': '7.8.9',
            },
            response.body,
        )

    def test_complex_status_verbose_omitted_works(self):
        action_request = EnrichedActionRequest(action='status', body={}, switches=None)

        response = _ComplexStatusAction()(action_request)

        self.assertIsInstance(response, ActionResponse)
        self.assertEqual(
            {
                'build': 'complex_service-28381-7.8.9-16_04',
                'conformity': six.text_type(conformity.__version__),
                'healthcheck': {
                    'diagnostics': {'check_good_called': True},
                    'errors': [('ANOTHER_CODE', 'This is an error')],
                    'warnings': [('FIRST_CODE', 'First warning'), ('SECOND_CODE', 'Second warning')],
                },
                'pysoa': six.text_type(pysoa.__version__),
                'python': six.text_type(platform.python_version()),
                'version': '7.8.9',
            },
            response.body,
        )

    def test_complex_status_verbose_true_works(self):
        action_request = EnrichedActionRequest(action='status', body={'verbose': True}, switches=None)

        response = _ComplexStatusAction()(action_request)

        self.assertIsInstance(response, ActionResponse)
        self.assertEqual(
            {
                'build': 'complex_service-28381-7.8.9-16_04',
                'conformity': six.text_type(conformity.__version__),
                'healthcheck': {
                    'diagnostics': {'check_good_called': True},
                    'errors': [('ANOTHER_CODE', 'This is an error')],
                    'warnings': [('FIRST_CODE', 'First warning'), ('SECOND_CODE', 'Second warning')],
                },
                'pysoa': six.text_type(pysoa.__version__),
                'python': six.text_type(platform.python_version()),
                'version': '7.8.9',
            },
            response.body,
        )

    def test_complex_status_verbose_false_works(self):
        action_request = EnrichedActionRequest(action='status', body={'verbose': False}, switches=None)

        response = _ComplexStatusAction()(action_request)

        self.assertIsInstance(response, ActionResponse)
        self.assertEqual(
            {
                'build': 'complex_service-28381-7.8.9-16_04',
                'conformity': six.text_type(conformity.__version__),
                'pysoa': six.text_type(pysoa.__version__),
                'python': six.text_type(platform.python_version()),
                'version': '7.8.9',
            },
            response.body,
        )

    def test_make_default_status_action_class(self):
        action_class = make_default_status_action_class(ActionResponse)
        self.assertIsNotNone(action_class)
        self.assertTrue(issubclass(action_class, BaseStatusAction))

        action = action_class({})
        self.assertEqual(six.text_type(pysoa.__version__), action._version)
        self.assertIsNone(action._build)

        action_class = make_default_status_action_class(Boolean)
        self.assertIsNotNone(action_class)
        self.assertTrue(issubclass(action_class, BaseStatusAction))

        action = action_class({})
        self.assertEqual(six.text_type(conformity.__version__), action._version)
        self.assertIsNone(action._build)
