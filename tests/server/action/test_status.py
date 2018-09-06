from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
)

import platform
import unittest

import conformity
from conformity.fields.basic import Boolean
import six

import pysoa
from pysoa.client.client import Client
from pysoa.common.transport.exceptions import MessageReceiveTimeout
from pysoa.common.types import (
    ActionResponse,
    Error,
    JobResponse,
)
from pysoa.server.action.status import (
    BaseStatusAction,
    StatusActionFactory,
    make_default_status_action_class,
)
from pysoa.server.types import EnrichedActionRequest
from pysoa.test.stub_service import stub_action


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


class _CheckOtherServicesAction(BaseStatusAction):
    _version = '8.71.2'

    check_client_settings = BaseStatusAction._check_client_settings


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

    def test_check_client_settings_no_settings(self):
        client = Client({})

        action_request = EnrichedActionRequest(action='status', body={}, switches=None, client=client)

        response = _CheckOtherServicesAction()(action_request)

        self.assertIsInstance(response, ActionResponse)
        self.assertEqual(
            {
                'conformity': six.text_type(conformity.__version__),
                'pysoa': six.text_type(pysoa.__version__),
                'python': six.text_type(platform.python_version()),
                'version': '8.71.2',
                'healthcheck': {'diagnostics': {}, 'errors': [], 'warnings': []},
            },
            response.body,
        )

    def test_check_client_settings_with_settings(self):
        client = Client({
            'foo': {'transport': {'path': 'pysoa.common.transport.base:ClientTransport'}},
            'bar': {'transport': {'path': 'pysoa.common.transport.base:ClientTransport'}},
            'baz': {'transport': {'path': 'pysoa.common.transport.base:ClientTransport'}},
            'qux': {'transport': {'path': 'pysoa.common.transport.base:ClientTransport'}},
        })

        action_request = EnrichedActionRequest(action='status', body={}, switches=None, client=client)

        baz_body = {
            'conformity': '1.2.3',
            'pysoa': '1.0.2',
            'python': '3.7.4',
            'version': '9.7.8',
        }

        with stub_action('foo', 'status') as foo_stub,\
                stub_action('bar', 'status', errors=[Error('BAR_ERROR', 'Bar error')]),\
                stub_action('baz', 'status', body=baz_body),\
                stub_action('qux', 'status') as qux_stub:
            foo_stub.return_value = JobResponse(errors=[Error('FOO_ERROR', 'Foo error')])
            qux_stub.side_effect = MessageReceiveTimeout('Timeout calling qux')

            response = _CheckOtherServicesAction()(action_request)

        self.assertIsInstance(response, ActionResponse)
        self.assertEqual(six.text_type(conformity.__version__), response.body['conformity'])
        self.assertEqual(six.text_type(pysoa.__version__), response.body['pysoa'])
        self.assertEqual(six.text_type(platform.python_version()), response.body['python'])
        self.assertEqual('8.71.2', response.body['version'])
        self.assertIn('healthcheck', response.body)
        self.assertEqual([], response.body['healthcheck']['warnings'])
        self.assertIn(
            ('FOO_CALL_ERROR', six.text_type([Error('FOO_ERROR', 'Foo error')])),
            response.body['healthcheck']['errors'],
        )
        self.assertIn(
            ('BAR_STATUS_ERROR', six.text_type([Error('BAR_ERROR', 'Bar error')])),
            response.body['healthcheck']['errors'],
        )
        self.assertIn(
            ('QUX_TRANSPORT_ERROR', 'Timeout calling qux'),
            response.body['healthcheck']['errors'],
        )
        self.assertEqual(3, len(response.body['healthcheck']['errors']))
        self.assertEqual(
            {
                'services': {
                    'baz': {
                        'conformity': '1.2.3',
                        'pysoa': '1.0.2',
                        'python': '3.7.4',
                        'version': '9.7.8',
                    },
                },
            },
            response.body['healthcheck']['diagnostics'],
        )
