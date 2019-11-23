from __future__ import (
    absolute_import,
    unicode_literals,
)

import logging
import os
import re
import sys
from typing import cast
import warnings

from conformity import fields
from conformity.settings import SettingsData
import pytest

from pysoa.common.errors import Error
from pysoa.common.transport.local import LocalClientTransport
from pysoa.server.action.base import Action
from pysoa.server.errors import ActionError
from pysoa.server.middleware import ServerMiddleware
from pysoa.server.server import Server
from pysoa.test.compatibility import mock
from pysoa.test.server import (
    BaseServerTestCase,
    PyTestServerTestCase,
    UnitTestServerTestCase,
)


class NotAServer(object):
    pass


class IncompleteServer(Server):
    pass


class DoNothingMiddleware(ServerMiddleware):
    pass


class NeaterMiddleware(ServerMiddleware):
    pass


class CoolestMiddleware(ServerMiddleware):
    pass


class HelloAction(Action):
    request_schema = fields.Dictionary(
        {'name': fields.UnicodeString(), 'optional': fields.Integer(), 'errors': fields.Integer()},
        optional_keys=('optional', 'errors')
    )

    def run(self, request):
        if request.body.get('errors') == 1:
            raise ActionError([Error('FOO', 'Foo error')])
        if request.body.get('errors') == 2:
            raise ActionError([Error('BAZ', 'Baz error'), Error('QUX', 'Qux error')])

        return {'salutation': 'Hello, {}'.format(request.body['name'])}


class CompleteServer(Server):
    service_name = 'complete'
    action_class_map = {
        'hello': HelloAction,
    }


class DjangoServer(CompleteServer):
    use_django = True


# noinspection PyProtectedMember
class TestBaseServerTestCase(BaseServerTestCase):
    def setup_method(self):
        self.server_class = None
        self.server_settings = None

    def test_no_server_class(self):
        with pytest.raises(TypeError):
            self.setup_pysoa()

    def test_wrong_server_class(self):
        # noinspection PyTypeChecker
        self.server_class = NotAServer  # type: ignore
        with pytest.raises(TypeError):
            self.setup_pysoa()

    def test_incomplete_server_class(self):
        self.server_class = IncompleteServer
        with pytest.raises(TypeError):
            self.setup_pysoa()

    def test_included_settings(self):
        self.server_class = CompleteServer
        self.server_settings = {'middleware': [
            {'path': 'tests.unit.test.test_server_test_cases:DoNothingMiddleware'},
        ]}
        self.setup_pysoa()

        response = self.call_action('hello', {'name': 'Nick'})

        assert response.body['salutation'] == 'Hello, Nick'

        assert self.service_name == 'complete'

        transport = cast(LocalClientTransport, self.client._get_handler(self.service_name).transport)
        assert isinstance(transport.server, CompleteServer)
        assert isinstance(transport.server._middleware[0], DoNothingMiddleware)

    def test_django_settings(self):
        django = mock.MagicMock()
        django_conf = mock.MagicMock()
        django_conf.settings.SOA_SERVER_SETTINGS = {'middleware': [
            {'path': 'tests.unit.test.test_server_test_cases:NeaterMiddleware'},
        ]}

        self.server_class = DjangoServer

        with mock.patch.dict(sys.modules, {'django': django, 'django.conf': django_conf}):
            self.setup_pysoa()

        transport = cast(LocalClientTransport, self.client._get_handler(self.service_name).transport)
        assert isinstance(transport.server, DjangoServer)
        assert isinstance(transport.server._middleware[0], NeaterMiddleware)

    def test_no_settings_module(self):
        self.server_class = CompleteServer

        with pytest.raises(AssertionError):
            self.setup_pysoa()

    def test_broken_settings_module(self):
        self.server_class = CompleteServer

        with mock.patch.dict(os.environ, {'PYSOA_SETTINGS_MODULE': 'foo.settings'}):
            with pytest.raises(AssertionError):
                self.setup_pysoa()

    def test_non_django_settings(self):
        foo = mock.MagicMock()
        foo_settings = mock.MagicMock()
        foo_settings.SOA_SERVER_SETTINGS = {'middleware': [
            {'path': 'tests.unit.test.test_server_test_cases:CoolestMiddleware'},
        ]}

        self.server_class = CompleteServer

        with mock.patch.dict(sys.modules, {'foo': foo, 'foo.settings': foo_settings}), \
                mock.patch.dict(os.environ, {'PYSOA_SETTINGS_MODULE': 'foo.settings'}):
            self.setup_pysoa()

        transport = cast(LocalClientTransport, self.client._get_handler(self.service_name).transport)
        assert isinstance(transport.server, CompleteServer)
        assert isinstance(transport.server._middleware[0], CoolestMiddleware)

    def test_assert_return_errors(self):
        self.server_class = CompleteServer
        self.server_settings = {}
        self.setup_pysoa()

        errors = self.assertActionRunsWithAndReturnErrors('nope', {})

        assert errors is not None
        assert len(errors) == 1
        assert errors[0].code == 'UNKNOWN'
        assert errors[0].field == 'action'

        # noinspection PyUnresolvedReferences
        with pytest.raises(pytest.raises.Exception):
            self.assertActionRunsWithAndReturnErrors('hello', {'name': 'Bear'})

    def test_assert_field_errors(self):
        self.server_class = CompleteServer
        self.server_settings = {}
        self.setup_pysoa()

        self.assertActionRunsWithFieldErrors('hello', {}, {'name': ['MISSING']})

        # noinspection PyUnresolvedReferences
        with pytest.raises(pytest.raises.Exception):
            self.assertActionRunsWithFieldErrors('hello', {'name': 'Bear'}, {'name': ['MISSING']})

        # noinspection PyUnresolvedReferences
        with pytest.raises(pytest.raises.Exception):
            self.assertActionRunsWithFieldErrors('hello', {}, {'name': ['MISSING', 'NOPE']})

    def test_assert_only_field_errors(self):
        self.server_class = CompleteServer
        self.server_settings = {}
        self.setup_pysoa()

        self.assertActionRunsWithOnlyFieldErrors('hello', {}, {'name': ['MISSING']})

        # noinspection PyUnresolvedReferences
        with pytest.raises(pytest.raises.Exception):
            self.assertActionRunsWithOnlyFieldErrors('hello', {'name': 'Bear'}, {'name': ['MISSING']})

        # noinspection PyUnresolvedReferences
        with pytest.raises(pytest.raises.Exception):
            self.assertActionRunsWithOnlyFieldErrors('hello', {'optional': 'not_an_int'}, {'name': ['MISSING']})

    def test_assert_error_codes(self):
        self.server_class = CompleteServer
        self.server_settings = {}
        self.setup_pysoa()

        self.assertActionRunsWithErrorCodes('hello', {'name': 'Bear', 'errors': 1}, ['FOO'])
        self.assertActionRunsWithErrorCodes('hello', {'name': 'Bear', 'errors': 2}, ['BAZ'])
        self.assertActionRunsWithErrorCodes('hello', {'name': 'Bear', 'errors': 2}, ['QUX'])

        # noinspection PyUnresolvedReferences
        with pytest.raises(pytest.raises.Exception):
            self.assertActionRunsWithErrorCodes('hello', {'name': 'Bear'}, ['FOO'])

        # noinspection PyUnresolvedReferences
        with pytest.raises(pytest.raises.Exception):
            self.assertActionRunsWithErrorCodes('hello', {'name': 'Bear', 'errors': 1}, ['BAZ'])

        # noinspection PyUnresolvedReferences
        with pytest.raises(pytest.raises.Exception):
            self.assertActionRunsWithErrorCodes('hello', {'name': 'Bear', 'errors': 2}, ['FOO'])

    def test_assert_only_error_codes(self):
        self.server_class = CompleteServer
        self.server_settings = {}
        self.setup_pysoa()

        self.assertActionRunsWithOnlyErrorCodes('hello', {'name': 'Bear', 'errors': 1}, ['FOO'])
        self.assertActionRunsWithOnlyErrorCodes('hello', {'name': 'Bear', 'errors': 2}, ['BAZ', 'QUX'])

        # noinspection PyUnresolvedReferences
        with pytest.raises(pytest.raises.Exception):
            self.assertActionRunsWithOnlyErrorCodes('hello', {'name': 'Bear', 'errors': 2}, ['BAZ'])

        # noinspection PyUnresolvedReferences
        with pytest.raises(pytest.raises.Exception):
            self.assertActionRunsWithOnlyErrorCodes('hello', {'name': 'Bear', 'errors': 1}, ['FOO', 'QUX'])


# noinspection PyProtectedMember
class TestUnitTestServerTestCase(UnitTestServerTestCase):
    server_class = CompleteServer
    server_settings = {}  # type: SettingsData

    def test_setup(self):
        response = self.call_action('hello', {'name': 'Nick'})

        assert response.body['salutation'] == 'Hello, Nick'

        assert self.service_name == 'complete'

        transport = cast(LocalClientTransport, self.client._get_handler(self.service_name).transport)
        assert isinstance(transport.server, CompleteServer)
        assert len(transport.server._middleware) == 0


# noinspection PyProtectedMember,PyTypeChecker,PyUnresolvedReferences
class TestPyTestServerTestCase(PyTestServerTestCase):
    server_class = CompleteServer
    server_settings = {}  # type: SettingsData

    def test_setup(self):
        response = self.call_action('hello', {'name': 'Nick'})

        assert response.body['salutation'] == 'Hello, Nick'

        assert self.service_name == 'complete'

        transport = cast(LocalClientTransport, self.client._get_handler(self.service_name).transport)
        assert isinstance(transport.server, CompleteServer)
        assert len(transport.server._middleware) == 0

    def test_fail(self):
        with pytest.raises(AssertionError):
            self.fail()
        # noinspection PyUnreachableCode
        with pytest.raises(AssertionError):
            self.fail('Foo')

    def test_assert_equal(self):
        self.assertEqual(1, 1)
        with pytest.raises(AssertionError):
            self.assertEqual(1, 2)

    def test_assert_not_equal(self):
        self.assertNotEqual(1, 2)
        with pytest.raises(AssertionError):
            self.assertNotEqual(1, 1)

    def test_assert_multiline_equal(self):
        self.assertMultiLineEqual('hello', 'hello')
        self.assertMultiLineEqual(str('goodbye'), str('goodbye'))
        with pytest.raises(AssertionError):
            self.assertMultiLineEqual(1, 1)  # type: ignore
        with pytest.raises(AssertionError):
            self.assertMultiLineEqual('hello', 'goodbye')

    def test_assert_sequence_equal(self):
        self.assertSequenceEqual(['foo', 'bar'], ['foo', 'bar'])
        self.assertSequenceEqual(['foo', 'bar'], ['foo', 'bar'], seq_type=list)
        self.assertSequenceEqual(('foo', 'bar'), ('foo', 'bar'), seq_type=tuple)
        with pytest.raises(AssertionError):
            self.assertSequenceEqual(['foo', 'bar'], ['foo', 'bar'], seq_type=tuple)
        with pytest.raises(AssertionError):
            self.assertSequenceEqual(['foo', 'bar'], ('foo', 'bar'))
        with pytest.raises(AssertionError):
            self.assertSequenceEqual(['foo', 'bar'], ['bar', 'foo'])

    def test_assert_list_equal(self):
        self.assertListEqual(['foo', 'bar'], ['foo', 'bar'])
        with pytest.raises(AssertionError):
            self.assertListEqual(('foo', 'bar'), ('foo', 'bar'))  # type: ignore
        with pytest.raises(AssertionError):
            self.assertListEqual(['foo', 'bar'], ['bar', 'foo'])

    def test_assert_tuple_equal(self):
        self.assertTupleEqual(('foo', 'bar'), ('foo', 'bar'))
        with pytest.raises(AssertionError):
            self.assertTupleEqual(['foo', 'bar'], ['foo', 'bar'])  # type: ignore
        with pytest.raises(AssertionError):
            self.assertTupleEqual(('foo', 'bar'), ('bar', 'foo'))

    def test_assert_set_equal(self):
        self.assertSetEqual({'foo', 'bar'}, {'foo', 'bar'})
        self.assertSetEqual({'foo', 'bar'}, {'bar', 'foo'})
        self.assertSetEqual(frozenset({'foo', 'bar'}), {'foo', 'bar'})
        self.assertSetEqual({'foo', 'bar'}, frozenset({'bar', 'foo'}))
        with pytest.raises(AssertionError):
            self.assertSetEqual(['foo', 'bar'], ['foo', 'bar'])  # type: ignore
        with pytest.raises(AssertionError):
            self.assertSetEqual({'foo', 'bar'}, {'foo', 'bar', 'baz'})

    def test_assert_dict_equal(self):
        self.assertDictEqual({'foo': 'bar', 'baz': 'qux'}, {'foo': 'bar', 'baz': 'qux'})
        self.assertDictEqual({'foo': 'bar', 'baz': 'qux'}, {'baz': 'qux', 'foo': 'bar'})
        with pytest.raises(AssertionError):
            self.assertDictEqual(['foo', 'bar'], ['foo', 'bar'])  # type: ignore
        with pytest.raises(AssertionError):
            self.assertDictEqual({'foo': 'bar', 'baz': 'qux'}, {'baz': 'qux'})
        with pytest.raises(AssertionError):
            self.assertDictEqual({'foo': 'bar', 'baz': 'qux'}, {'foo': 'qux', 'baz': 'bar'})

    def test_assert_almost_equal(self):
        self.assertAlmostEqual(1, 1)
        self.assertAlmostEqual(1, 1.000000001)
        self.assertAlmostEqual(1, 1.01, places=1)
        self.assertAlmostEqual(1, 1.1, delta=0.2)
        with pytest.raises(AssertionError):
            self.assertAlmostEqual(1, 1.1, places=1, delta=0.1)
        with pytest.raises(AssertionError):
            self.assertAlmostEqual(1, 2)
        with pytest.raises(AssertionError):
            self.assertAlmostEqual(1, 1.01, places=3)
        with pytest.raises(AssertionError):
            self.assertAlmostEqual(1, 1.1, delta=0.05)

    def test_assert_not_almost_equal(self):
        self.assertNotAlmostEqual(1, 2)
        self.assertNotAlmostEqual(1, 1.00001)
        self.assertNotAlmostEqual(1, 1.1, places=2)
        self.assertNotAlmostEqual(1, 1.2, delta=0.1)
        with pytest.raises(AssertionError):
            self.assertNotAlmostEqual(1, 2, places=1, delta=0.1)
        with pytest.raises(AssertionError):
            self.assertNotAlmostEqual(1, 1)
        with pytest.raises(AssertionError):
            self.assertNotAlmostEqual(1, 1.01, places=1)
        with pytest.raises(AssertionError):
            self.assertNotAlmostEqual(1, 1.01, delta=0.05)

    def test_assert_true(self):
        self.assertTrue(True)
        with pytest.raises(AssertionError):
            self.assertTrue(False)

    def test_assert_false(self):
        self.assertFalse(False)
        with pytest.raises(AssertionError):
            self.assertFalse(True)

    def test_assert_is(self):
        f1 = object()
        f2 = object()
        self.assertIs(f1, f1)
        with pytest.raises(AssertionError):
            self.assertIs(f1, f2)

    def test_assert_is_not(self):
        f1 = object()
        f2 = object()
        self.assertIsNot(f1, f2)
        with pytest.raises(AssertionError):
            self.assertIsNot(f1, f1)

    def test_assert_is_none(self):
        self.assertIsNone(None)
        with pytest.raises(AssertionError):
            self.assertIsNone('')

    def test_assert_is_not_none(self):
        self.assertIsNotNone('')
        with pytest.raises(AssertionError):
            self.assertIsNotNone(None)

    def test_assert_in(self):
        self.assertIn('foo', {'foo', 'bar'})
        with pytest.raises(AssertionError):
            self.assertIn('baz', {'foo', 'bar'})

    def test_assert_not_in(self):
        self.assertNotIn('baz', {'foo', 'bar'})
        with pytest.raises(AssertionError):
            self.assertNotIn('foo', {'foo', 'bar'})

    def test_assert_is_instance(self):
        self.assertIsInstance(ValueError(), ValueError)
        with pytest.raises(AssertionError):
            self.assertIsInstance(TypeError(), ValueError)

    def test_assert_not_is_instance(self):
        self.assertNotIsInstance(TypeError(), ValueError)
        with pytest.raises(AssertionError):
            self.assertNotIsInstance(ValueError(), ValueError)

    def test_assert_greater(self):
        self.assertGreater(2, 1)
        with pytest.raises(AssertionError):
            self.assertGreater(1, 1)
        with pytest.raises(AssertionError):
            self.assertGreater(0, 1)

    def test_assert_greater_equal(self):
        self.assertGreaterEqual(2, 1)
        self.assertGreaterEqual(1, 1)
        with pytest.raises(AssertionError):
            self.assertGreaterEqual(0, 1)

    def test_assert_less(self):
        self.assertLess(1, 2)
        with pytest.raises(AssertionError):
            self.assertLess(1, 1)
        with pytest.raises(AssertionError):
            self.assertLess(1, 0)

    def test_assert_less_equal(self):
        self.assertLessEqual(1, 2)
        self.assertLessEqual(1, 1)
        with pytest.raises(AssertionError):
            self.assertLessEqual(1, 0)

    def test_assert_regex(self):
        self.assertRegex('hello', '[a-z]+')
        self.assertRegex(b'hello', b'[a-z]+')
        self.assertRegex('goodbye', re.compile('[a-z]+'))
        self.assertRegex(b'goodbye', re.compile(b'[a-z]+'))
        with pytest.raises(AssertionError):
            self.assertRegex('hello', None)  # type: ignore
        with pytest.raises(AssertionError):
            self.assertRegex('hello', '')
        with pytest.raises(AssertionError):
            self.assertRegex('1234', '[a-z]+')

    def test_assert_not_regex(self):
        self.assertNotRegex('1234', '[a-z]+')
        self.assertNotRegex(b'1234', b'[a-z]+')
        self.assertNotRegex('5678', re.compile('[a-z]+'))
        self.assertNotRegex(b'5678', re.compile(b'[a-z]+'))
        with pytest.raises(AssertionError):
            self.assertNotRegex('hello', None)  # type: ignore
        with pytest.raises(AssertionError):
            self.assertNotRegex('hello', '')
        with pytest.raises(AssertionError):
            self.assertNotRegex('hello', '[a-z]+')
        with pytest.raises(AssertionError):
            self.assertNotRegex(b'goodbye', b'[a-z]+')

    def test_assert_raises(self):
        with self.assertRaises(ValueError) as context:
            raise ValueError()
        assert context.value.args == ()
        assert context.exception.args == ()

        with self.assertRaises(TypeError) as context:
            raise TypeError()
        assert context.value.args == ()
        assert context.exception.args == ()

        with pytest.raises(pytest.raises.Exception):
            with self.assertRaises(ValueError):
                assert 1 == 1

        flags = mock.MagicMock()
        del flags.raise_value
        del flags.raise_type

        def raise_value(*args, **kwargs):
            flags.raise_value = args, kwargs
            if not args or args[0] is not False:
                raise ValueError()

        def raise_type(*args, **kwargs):
            flags.raise_type = args, kwargs
            raise TypeError()

        assert self.assertRaises(ValueError, raise_value, 'foo', bar='baz') is None
        assert flags.raise_value == (('foo', ), {'bar': 'baz'})

        assert self.assertRaises(TypeError, raise_type, 'qux', baz='foo') is None
        assert flags.raise_type == (('qux', ), {'baz': 'foo'})

        with pytest.raises(pytest.raises.Exception):
            self.assertRaises(ValueError, raise_value, False)
        assert flags.raise_value == ((False, ), {})

    def test_assert_raises_regex(self):
        with self.assertRaisesRegex(ValueError, '[a-z]+') as context:
            raise ValueError('hello')
        assert context.value.args == ('hello', )
        assert context.exception.args == ('hello', )

        with self.assertRaisesRegex(TypeError, '[a-z]+') as context:
            raise TypeError('goodbye')
        assert context.value.args == ('goodbye', )
        assert context.exception.args == ('goodbye', )

        with pytest.raises(AssertionError):
            with self.assertRaisesRegex(ValueError, '[a-z]+'):
                raise ValueError('1234')

        flags = mock.MagicMock()
        del flags.raise_value
        del flags.raise_type

        def raise_value(*args, **kwargs):
            flags.raise_value = args, kwargs
            if not args or args[0] is not False:
                raise ValueError('hello')
            raise ValueError('1234')

        def raise_type(*args, **kwargs):
            flags.raise_type = args, kwargs
            raise TypeError('goodbye')

        assert self.assertRaisesRegex(ValueError, '[a-z]+', raise_value, 'foo', bar='baz') is None
        assert flags.raise_value == (('foo', ), {'bar': 'baz'})

        assert self.assertRaisesRegex(TypeError, '[a-z]+', raise_type, 'qux', baz='foo') is None
        assert flags.raise_type == (('qux', ), {'baz': 'foo'})

        with pytest.raises(AssertionError):
            self.assertRaisesRegex(ValueError, '[a-z]+', raise_value, False)
        assert flags.raise_value == ((False, ), {})

    def test_assert_warns(self):
        with self.assertWarns(DeprecationWarning) as context:
            warnings.warn('hello', DeprecationWarning)
        assert issubclass(context.list[0].category, DeprecationWarning)

        with self.assertWarns(FutureWarning) as context:
            warnings.warn('goodbye', FutureWarning)
        assert issubclass(context.list[0].category, FutureWarning)

        with pytest.raises(pytest.raises.Exception):
            with self.assertWarns(DeprecationWarning):
                assert 1 == 1

        flags = mock.MagicMock()
        del flags.raise_value
        del flags.raise_type

        def raise_value(*args, **kwargs):
            flags.raise_value = args, kwargs
            if not args or args[0] is not False:
                warnings.warn('hello', DeprecationWarning)

        def raise_type(*args, **kwargs):
            flags.raise_type = args, kwargs
            warnings.warn('goodbye', FutureWarning)

        assert self.assertWarns(DeprecationWarning, raise_value, 'foo', bar='baz') is None
        assert flags.raise_value == (('foo', ), {'bar': 'baz'})

        assert self.assertWarns(FutureWarning, raise_type, 'qux', baz='foo') is None
        assert flags.raise_type == (('qux', ), {'baz': 'foo'})

        with pytest.raises(pytest.raises.Exception):
            self.assertWarns(DeprecationWarning, raise_value, False)
        assert flags.raise_value == ((False, ), {})

    def test_assert_warns_regex(self):
        with self.assertWarnsRegex(DeprecationWarning, '[a-z]+') as context:
            warnings.warn('hello', DeprecationWarning)
        assert issubclass(context.list[0].category, DeprecationWarning)

        with self.assertWarnsRegex(FutureWarning, '[a-z]+') as context:
            warnings.warn('goodbye', FutureWarning)
        assert issubclass(context.list[0].category, FutureWarning)

        with pytest.raises(pytest.raises.Exception):
            with self.assertWarnsRegex(DeprecationWarning, '[a-z]+'):
                warnings.warn('1234', DeprecationWarning)

        flags = mock.MagicMock()
        del flags.raise_value
        del flags.raise_type

        def raise_value(*args, **kwargs):
            flags.raise_value = args, kwargs
            if not args or args[0] is not False:
                warnings.warn('hello', DeprecationWarning)
            else:
                warnings.warn('1234', DeprecationWarning)

        def raise_type(*args, **kwargs):
            flags.raise_type = args, kwargs
            warnings.warn('goodbye', FutureWarning)

        assert self.assertWarnsRegex(DeprecationWarning, '[a-z]+', raise_value, 'foo', bar='baz') is None
        assert flags.raise_value == (('foo', ), {'bar': 'baz'})

        assert self.assertWarnsRegex(FutureWarning, '[a-z]+', raise_type, 'qux', baz='foo') is None
        assert flags.raise_type == (('qux', ), {'baz': 'foo'})

        with pytest.raises(pytest.raises.Exception):
            self.assertWarnsRegex(DeprecationWarning, '[a-z]+', raise_value, False)
        assert flags.raise_value == ((False, ), {})

    def test_assert_logs(self):
        with self.assertLogs('foo.bar') as context:
            logging.getLogger('foo.bar').debug('Ignored')
            logging.getLogger('foo.bar').info('Hello world')
            logging.getLogger('foo.bar.baz').warning('Danger, Will Robinson!')

        assert context.output == ['INFO:foo.bar:Hello world', 'WARNING:foo.bar.baz:Danger, Will Robinson!']

        with self.assertLogs(logging.getLogger('baz.qux'), 'WARN') as context:
            logging.getLogger('baz.qux').info('Hello world')
            logging.getLogger('baz.qux.lorem').warning('Caution ahead')

        assert context.output == ['WARNING:baz.qux.lorem:Caution ahead']

        with pytest.raises(AssertionError):
            with self.assertLogs('foo.bar', logging.ERROR) as context:
                logging.getLogger('foo.bar').info('Hello world')
                logging.getLogger('foo.bar.baz').warning('Danger, Will Robinson!')

        assert context.output == []

        with pytest.raises(ValueError):
            with self.assertLogs('foo.bar', logging.ERROR) as context:
                raise ValueError()

        assert context.output == []

    # ##### Deprecated methods ##### #

    # noinspection PyDeprecation
    def test_assert_count_equal(self):
        with warnings.catch_warnings(record=True) as w:
            self.assertCountEqual('hello', 'olleh')
            self.assertCountEqual(['foo', 'foo', 'bar', 'baz'], ['baz', 'foo', 'bar', 'foo'])
            self.assertCountEqual(
                [{'foo': 'bar', 'baz': 'qux'}, {'lorem': 'ipsum'}],
                [{'lorem': 'ipsum'}, {'foo': 'bar', 'baz': 'qux'}],
            )
            with pytest.raises(AssertionError):
                self.assertCountEqual('hello', 'abc12')
            with pytest.raises(AssertionError):
                self.assertCountEqual(['foo', 'foo', 'bar', 'baz'], ['baz', 'qux', 'bar', 'foo'])
            with pytest.raises(AssertionError):
                self.assertCountEqual(
                    [{'foo': 'bar', 'baz': 'qux'}, {'ipsum': 'lorem'}],
                    [{'lorem': 'ipsum'}, {'foo': 'bar', 'baz': 'qux'}],
                )

        assert w is not None
        assert len(w) == 6
        assert issubclass(w[0].category, DeprecationWarning)
        assert issubclass(w[1].category, DeprecationWarning)
        assert issubclass(w[2].category, DeprecationWarning)
        assert issubclass(w[3].category, DeprecationWarning)
        assert issubclass(w[4].category, DeprecationWarning)
        assert issubclass(w[5].category, DeprecationWarning)

    def test_deprecated_assert_equals(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always', DeprecationWarning)
            self.assertEquals(1, 1)

            with pytest.raises(AssertionError):
                self.assertEquals(1, 2)

        assert w is not None
        assert len(w) == 2
        assert issubclass(w[0].category, DeprecationWarning)
        assert issubclass(w[1].category, DeprecationWarning)

    def test_deprecated_fail_unless_equal(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always', DeprecationWarning)
            self.failUnlessEqual(1, 1)

            with pytest.raises(AssertionError):
                self.failUnlessEqual(1, 2)

        assert w is not None
        assert len(w) == 2
        assert issubclass(w[0].category, DeprecationWarning)
        assert issubclass(w[1].category, DeprecationWarning)

    def test_deprecated_assert_not_equals(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always', DeprecationWarning)
            self.assertNotEquals(1, 2)

            with pytest.raises(AssertionError):
                self.assertNotEquals(1, 1)

        assert w is not None
        assert len(w) == 2
        assert issubclass(w[0].category, DeprecationWarning)
        assert issubclass(w[1].category, DeprecationWarning)

    def test_deprecated_fail_if_equal(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always', DeprecationWarning)
            self.failIfEqual(1, 2)

            with pytest.raises(AssertionError):
                self.failIfEqual(1, 1)

        assert w is not None
        assert len(w) == 2
        assert issubclass(w[0].category, DeprecationWarning)
        assert issubclass(w[1].category, DeprecationWarning)

    def test_deprecated_assert_almost_equals(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always', DeprecationWarning)
            self.assertAlmostEquals(1, 1.01, 1)

            with pytest.raises(AssertionError):
                self.assertAlmostEquals(1, 2)

        assert w is not None
        assert len(w) == 2
        assert issubclass(w[0].category, DeprecationWarning)
        assert issubclass(w[1].category, DeprecationWarning)

    def test_deprecated_fail_unless_almost_equal(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always', DeprecationWarning)
            self.failUnlessAlmostEqual(1, 1.01, 1)

            with pytest.raises(AssertionError):
                self.failUnlessAlmostEqual(1, 2)

        assert w is not None
        assert len(w) == 2
        assert issubclass(w[0].category, DeprecationWarning)
        assert issubclass(w[1].category, DeprecationWarning)

    def test_deprecated_assert_not_almost_equals(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always', DeprecationWarning)
            self.assertNotAlmostEquals(1, 2)

            with pytest.raises(AssertionError):
                self.assertNotAlmostEquals(1, 1.01, 1)

        assert w is not None
        assert len(w) == 2
        assert issubclass(w[0].category, DeprecationWarning)
        assert issubclass(w[1].category, DeprecationWarning)

    def test_deprecated_fail_if_almost_equal(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always', DeprecationWarning)
            self.failIfAlmostEqual(1, 2)

            with pytest.raises(AssertionError):
                self.failIfAlmostEqual(1, 1.01, 1)

        assert w is not None
        assert len(w) == 2
        assert issubclass(w[0].category, DeprecationWarning)
        assert issubclass(w[1].category, DeprecationWarning)

    def test_deprecated_fail_unless(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always', DeprecationWarning)
            self.failUnless(True)

            with pytest.raises(AssertionError):
                self.failUnless(False)

        assert w is not None
        assert len(w) == 2
        assert issubclass(w[0].category, DeprecationWarning)
        assert issubclass(w[1].category, DeprecationWarning)

    def test_deprecated_assert_(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always', DeprecationWarning)
            self.assert_(True)

            with pytest.raises(AssertionError):
                self.assert_(False)

        assert w is not None
        assert len(w) == 2
        assert issubclass(w[0].category, DeprecationWarning)
        assert issubclass(w[1].category, DeprecationWarning)

    def test_deprecated_fail_if(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always', DeprecationWarning)
            self.failIf(False)

            with pytest.raises(AssertionError):
                self.failIf(True)

        assert w is not None
        assert len(w) == 2
        assert issubclass(w[0].category, DeprecationWarning)
        assert issubclass(w[1].category, DeprecationWarning)

    def test_deprecated_assert_regexp_matches(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always', DeprecationWarning)
            self.assertRegexpMatches('hello', r'[a-z]+')

            with pytest.raises(AssertionError):
                self.assertRegexpMatches('1234', r'[a-z]+')

        assert w is not None
        assert len(w) == 2
        assert issubclass(w[0].category, DeprecationWarning)
        assert issubclass(w[1].category, DeprecationWarning)

    def test_deprecated_assert_not_regexp_matches(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always', DeprecationWarning)
            self.assertNotRegexpMatches('1234', r'[a-z]+')

            with pytest.raises(AssertionError):
                self.assertNotRegexpMatches('hello', r'[a-z]+')

        assert w is not None
        assert len(w) == 2
        assert issubclass(w[0].category, DeprecationWarning)
        assert issubclass(w[1].category, DeprecationWarning)

    def test_deprecated_fail_unless_raises(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always', DeprecationWarning)
            with self.failUnlessRaises(ValueError):
                raise ValueError()

            with pytest.raises(pytest.raises.Exception):
                with self.failUnlessRaises(ValueError):
                    assert 1 == 1

        assert w is not None
        assert len(w) == 2
        assert issubclass(w[0].category, DeprecationWarning)
        assert issubclass(w[1].category, DeprecationWarning)


# noinspection PyTypeChecker,PyUnresolvedReferences
class TestPyTestServerTestCaseDeprecations(object):
    def test_setup_class(self):
        class PyTestServerTestCase1(PyTestServerTestCase):
            pass

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always', DeprecationWarning)

            PyTestServerTestCase1.setup_class()

        assert w is not None
        assert len(w) == 0

        flag = mock.MagicMock()

        class PyTestServerTestCase2(PyTestServerTestCase):
            @classmethod
            def setUpClass(cls):
                flag.called = True

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always', DeprecationWarning)

            PyTestServerTestCase2.setup_class()

        assert w is not None
        assert flag.called is True
        assert len(w) == 1
        assert issubclass(w[-1].category, DeprecationWarning)

    def test_teardown_class(self):
        class PyTestServerTestCase1(PyTestServerTestCase):
            pass

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always', DeprecationWarning)

            PyTestServerTestCase1.teardown_class()

        assert w is not None
        assert len(w) == 0

        flag = mock.MagicMock()

        class PyTestServerTestCase2(PyTestServerTestCase):
            @classmethod
            def tearDownClass(cls):
                flag.called = True

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always', DeprecationWarning)

            PyTestServerTestCase2.teardown_class()

        assert w is not None
        assert flag.called is True
        assert len(w) == 1
        assert issubclass(w[-1].category, DeprecationWarning)

    def test_setup_method(self):
        class PyTestServerTestCase1(PyTestServerTestCase):
            server_class = CompleteServer
            server_settings = {}

        case = PyTestServerTestCase1()  # type: PyTestServerTestCase
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always', DeprecationWarning)

            case.setup_method()

        assert w is not None
        assert len(w) == 0

        flag = mock.MagicMock()

        class PyTestServerTestCase2(PyTestServerTestCase):
            server_class = CompleteServer
            server_settings = {}

            def setUp(self):
                flag.called = True

        case = PyTestServerTestCase2()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always', DeprecationWarning)

            case.setup_method()

        assert w is not None
        assert flag.called is True
        assert len(w) == 1
        assert issubclass(w[-1].category, DeprecationWarning)

    def test_teardown_method(self):
        class PyTestServerTestCase1(PyTestServerTestCase):
            server_class = CompleteServer
            server_settings = {}

        case = PyTestServerTestCase1()  # type: PyTestServerTestCase
        case.setup_method()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always', DeprecationWarning)

            case.teardown_method()

        assert w is not None
        assert len(w) == 0

        flag = mock.MagicMock()

        class PyTestServerTestCase2(PyTestServerTestCase):
            server_class = CompleteServer
            server_settings = {}

            def tearDown(self):
                flag.called = True

        case = PyTestServerTestCase2()
        case.setup_method()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always', DeprecationWarning)

            case.teardown_method()

        assert w is not None
        assert flag.called is True
        assert len(w) == 1
        assert issubclass(w[-1].category, DeprecationWarning)

    def test_cleanups(self):
        flags = mock.MagicMock()
        del flags.clean1
        del flags.clean2

        def clean1(*args, **kwargs):
            flags.clean1 = args, kwargs

        def clean2(*args, **kwargs):
            flags.clean2 = args, kwargs

        class PyTestServerTestCase1(PyTestServerTestCase):
            server_class = CompleteServer
            server_settings = {}

            # noinspection PyDeprecation
            def setup_method(self):  # type: () -> None
                super(PyTestServerTestCase1, self).setup_method()

                self.addCleanup(clean1, 'foo', bar='baz')
                self.addCleanup(clean2, 'qux', baz='foo')

        case = PyTestServerTestCase1()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always', DeprecationWarning)

            case.setup_method()

        assert w is not None
        assert len(w) == 2
        assert issubclass(w[0].category, DeprecationWarning)
        assert issubclass(w[1].category, DeprecationWarning)

        assert not hasattr(flags, 'clean1')
        assert not hasattr(flags, 'clean2')

        case.teardown_method()

        assert flags.clean1 == (('foo', ), {'bar': 'baz'})
        assert flags.clean2 == (('qux', ), {'baz': 'foo'})
