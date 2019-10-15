from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
)

import platform
import sys
import unittest

import conformity
import six

import pysoa
from pysoa.client.client import Client
from pysoa.common.errors import Error
from pysoa.common.transport.errors import MessageReceiveTimeout
from pysoa.common.types import (
    ActionResponse,
    JobResponse,
)
from pysoa.server.action.status import (
    BaseStatusAction,
    StatusActionFactory,
    make_default_status_action_class,
)
from pysoa.server.server import Server
from pysoa.server.types import EnrichedActionRequest
from pysoa.test.compatibility import mock
from pysoa.test.stub_service import stub_action


class _ComplexStatusAction(BaseStatusAction):
    _version = '7.8.9'

    _build = 'complex_service-28381-7.8.9-16_04'

    def check_good(self, _request):
        self.diagnostics['check_good_called'] = True

    @staticmethod
    def check_warnings(_request):
        return (
            (False, 'FIRST_CODE', 'First warning'),
            (False, 'SECOND_CODE', 'Second warning'),
        )

    @staticmethod
    def check_errors(_request):
        return [
            [True, 'ANOTHER_CODE', 'This is an error'],
        ]


class _CheckOtherServicesAction(BaseStatusAction):
    _version = '8.71.2'

    check_client_settings = BaseStatusAction._check_client_settings


class TestBaseStatusAction(unittest.TestCase):
    def test_cannot_instantiate_base_action(self):
        with self.assertRaises(TypeError):
            BaseStatusAction()  # type: ignore

    def test_basic_status_works(self):
        action_request = EnrichedActionRequest(action='status', body={})

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
        action_request = EnrichedActionRequest(action='status', body={})

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
        action_request = EnrichedActionRequest(action='status', body={})

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
        action_request = EnrichedActionRequest(action='status', body={'verbose': True})

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
        action_request = EnrichedActionRequest(action='status', body={'verbose': False})

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
        class TestServer1(Server):
            pass

        class TestServer2(Server):
            pass

        module1 = mock.MagicMock()
        module1.__name__ = 'neat_service'
        module1.__version__ = '1.6.3'
        module2 = mock.MagicMock()
        module2.__name__ = 'cooler_service'
        module2.__version__ = '3.15.5'
        module2.__build__ = 'cooler_service-3.15.5-af7ed3c'

        TestServer1.__module__ = 'neat_service.server'
        TestServer2.__module__ = 'cooler_service.further.lower.server'

        with mock.patch.dict(sys.modules, {'neat_service': module1, 'cooler_service': module2}):
            action_class = make_default_status_action_class(TestServer1)
            assert action_class is not None
            assert issubclass(action_class, BaseStatusAction)

            # noinspection PyArgumentList
            action = action_class()
            assert action is not None
            assert isinstance(action, BaseStatusAction)
            assert action._version == '1.6.3'
            assert action._build is None

            action_class = make_default_status_action_class(TestServer2)
            assert action_class is not None
            assert issubclass(action_class, BaseStatusAction)

            # noinspection PyArgumentList
            action = action_class()
            assert action is not None
            assert isinstance(action, BaseStatusAction)
            assert action._version == '3.15.5'
            assert action._build == 'cooler_service-3.15.5-af7ed3c'

    def test_check_client_settings_no_settings(self):
        client = Client({})

        action_request = EnrichedActionRequest(action='status', body={}, client=client)

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
            'foo': {'transport': {'path': 'pysoa.test.stub_service:StubClientTransport'}},
            'bar': {'transport': {'path': 'pysoa.test.stub_service:StubClientTransport'}},
            'baz': {'transport': {'path': 'pysoa.test.stub_service:StubClientTransport'}},
            'qux': {'transport': {'path': 'pysoa.test.stub_service:StubClientTransport'}},
        })

        action_request = EnrichedActionRequest(action='status', body={}, client=client)

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
