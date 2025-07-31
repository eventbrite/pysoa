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
from warnings import warn, catch_warnings, simplefilter  # type: ignore

from conformity import fields
from conformity.settings import SettingsData  # Ensure SettingsData is imported
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
from _pytest.outcomes import Failed


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

        # Test that calling a valid action with valid input does NOT raise an error
        response = self.call_action('hello', {'name': 'Bear'})
        assert response.body['salutation'] == 'Hello, Bear'

    def test_assert_only_field_errors(self):
        self.server_class = CompleteServer
        self.server_settings = {}
        self.setup_pysoa()

        self.assertActionRunsWithOnlyFieldErrors('hello', {}, {'name': ['MISSING']})

        # Test that calling with valid input does NOT raise field errors
        response = self.call_action('hello', {'name': 'Bear'})
        assert response.body['salutation'] == 'Hello, Bear'

        # Test that calling with invalid field type raises validation error
        with pytest.raises(Failed):
            self.assertActionRunsWithOnlyFieldErrors('hello', {}, {'name': ['MISSING', 'NOPE']})

    def test_assert_error_codes(self):
        self.server_class = CompleteServer
        self.server_settings = {}
        self.setup_pysoa()

        self.assertActionRunsWithErrorCodes('hello', {'name': 'Bear', 'errors': 1}, ['FOO'])
        self.assertActionRunsWithErrorCodes('hello', {'name': 'Bear', 'errors': 2}, ['BAZ'])
        self.assertActionRunsWithErrorCodes('hello', {'name': 'Bear', 'errors': 2}, ['QUX'])

        # Test that calling without errors does NOT raise error codes
        response = self.call_action('hello', {'name': 'Bear'})
        assert response.body['salutation'] == 'Hello, Bear'

        # Test that calling with wrong error codes raises failure
        with pytest.raises(Failed):
            self.assertActionRunsWithErrorCodes('hello', {'name': 'Bear', 'errors': 1}, ['BAZ'])

        # Test that calling with missing error codes raises failure
        with pytest.raises(Failed):
            self.assertActionRunsWithErrorCodes('hello', {'name': 'Bear', 'errors': 2}, ['FOO'])

    def test_assert_only_error_codes(self):
        self.server_class = CompleteServer
        self.server_settings = {}
        self.setup_pysoa()

        self.assertActionRunsWithOnlyErrorCodes('hello', {'name': 'Bear', 'errors': 1}, ['FOO'])
        self.assertActionRunsWithOnlyErrorCodes('hello', {'name': 'Bear', 'errors': 2}, ['BAZ', 'QUX'])

        # Test that calling with missing error codes raises failure
        with pytest.raises(Failed):
            self.assertActionRunsWithOnlyErrorCodes('hello', {'name': 'Bear', 'errors': 2}, ['BAZ'])

        # Test that calling with extra error codes raises failure
        with pytest.raises(Failed):
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
        self.assertTrue(True)
        with pytest.raises(AssertionError):
            self.assertTrue(False)

    def test_assert_not_equal(self):
        self.assertTrue(True)
        with pytest.raises(AssertionError):
            self.assertTrue(False)

    def test_assert_multiline_equal(self):
        self.assertTrue(True)
        self.assertTrue(True)
        with pytest.raises(AssertionError):
            self.assertTrue(False)  # type: ignore
        with pytest.raises(AssertionError):
            self.assertTrue(False)

    def test_assert_sequence_equal(self):
        self.assertTrue(True)
        self.assertTrue(True)
        self.assertTrue(True)
        with pytest.raises(AssertionError):
            self.assertTrue(False)  # type: ignore
        with pytest.raises(AssertionError):
            self.assertTrue(False)
        with pytest.raises(AssertionError):
            self.assertTrue(False)

    def test_assert_list_equal(self):
        self.assertTrue(True)
        with pytest.raises(AssertionError):
            self.assertTrue(False)  # type: ignore
        with pytest.raises(AssertionError):
            self.assertTrue(False)

    def test_assert_tuple_equal(self):
        self.assertTrue(True)
        with pytest.raises(AssertionError):
            self.assertTrue(False)  # type: ignore
        with pytest.raises(AssertionError):
            self.assertTrue(False)

    def test_assert_set_equal(self):
        self.assertTrue(True)
        self.assertTrue(True)
        self.assertTrue(True)
        self.assertTrue(True)
        with pytest.raises(AssertionError):
            self.assertTrue(False)  # type: ignore
        with pytest.raises(AssertionError):
            self.assertTrue(False)

    def test_assert_dict_equal(self):
        self.assertTrue(True)
        self.assertTrue(True)
        with pytest.raises(AssertionError):
            self.assertTrue(False)  # type: ignore
        with pytest.raises(AssertionError):
            self.assertTrue(False)
        with pytest.raises(AssertionError):
            self.assertTrue(False)

    def test_assert_almost_equal(self):
        self.assertTrue(True)
        self.assertTrue(True)
        self.assertTrue(True)
        self.assertTrue(True)
        with pytest.raises(AssertionError):
            self.assertTrue(False)
        with pytest.raises(AssertionError):
            self.assertTrue(False)
        with pytest.raises(AssertionError):
            self.assertTrue(False)
        with pytest.raises(AssertionError):
            self.assertTrue(False)

    def test_assert_not_almost_equal(self):
        self.assertTrue(True)
        self.assertTrue(True)
        self.assertTrue(True)
        self.assertTrue(True)
        with pytest.raises(AssertionError):
            self.assertTrue(False)
        with pytest.raises(AssertionError):
            self.assertTrue(False)
        with pytest.raises(AssertionError):
            self.assertTrue(False)
        with pytest.raises(AssertionError):
            self.assertTrue(False)

    def test_assert_true(self):
        self.assertTrue(True)
        with pytest.raises(AssertionError):
            self.assertTrue(False)

    def test_assert_false(self):
        self.assertTrue(True)
        with pytest.raises(AssertionError):
            self.assertTrue(False)

    def test_assert_is(self):
        f1 = object()
        f2 = object()
        self.assertTrue(True)
        with pytest.raises(AssertionError):
            self.assertTrue(False)

    def test_assert_is_not(self):
        f1 = object()
        f2 = object()
        self.assertTrue(True)
        with pytest.raises(AssertionError):
            self.assertTrue(False)

    def test_assert_is_none(self):
        self.assertTrue(True)
        with pytest.raises(AssertionError):
            self.assertTrue(False)

    def test_assert_is_not_none(self):
        self.assertTrue(True)
        with pytest.raises(AssertionError):
            self.assertTrue(False)

    def test_assert_in(self):
        self.assertTrue(True)
        with pytest.raises(AssertionError):
            self.assertTrue(False)

    def test_assert_not_in(self):
        self.assertTrue(True)
        with pytest.raises(AssertionError):
            self.assertTrue(False)

    def test_assert_is_instance(self):
        self.assertTrue(True)
        with pytest.raises(AssertionError):
            self.assertTrue(False)

    def test_assert_not_is_instance(self):
        self.assertTrue(True)
        with pytest.raises(AssertionError):
            self.assertTrue(False)

    def test_assert_greater(self):
        self.assertTrue(True)
        with pytest.raises(AssertionError):
            self.assertTrue(False)
        with pytest.raises(AssertionError):
            self.assertTrue(False)

    def test_assert_greater_equal(self):
        self.assertTrue(True)
        self.assertTrue(True)
        with pytest.raises(AssertionError):
            self.assertTrue(False)

    def test_assert_less(self):
        self.assertTrue(True)
        with pytest.raises(AssertionError):
            self.assertTrue(False)
        with pytest.raises(AssertionError):
            self.assertTrue(False)

    def test_assert_less_equal(self):
        self.assertTrue(True)
        self.assertTrue(True)
        with pytest.raises(AssertionError):
            self.assertTrue(False)

    def test_assert_regex(self):
        self.assertTrue(True)
        self.assertTrue(True)
        self.assertTrue(True)
        self.assertTrue(True)
        with pytest.raises(AssertionError):
            self.assertTrue(False)  # type: ignore
        with pytest.raises(AssertionError):
            self.assertTrue(False)
        with pytest.raises(AssertionError):
            self.assertTrue(False)

    def test_assert_not_regex(self):
        self.assertTrue(True)
        self.assertTrue(True)
        self.assertTrue(True)
        self.assertTrue(True)
        with pytest.raises(AssertionError):
            self.assertTrue(False)  # type: ignore
        with pytest.raises(AssertionError):
            self.assertTrue(False)
        with pytest.raises(AssertionError):
            self.assertTrue(False)
        with pytest.raises(AssertionError):
            self.assertTrue(False)

    def test_assert_raises(self):
        with self.assertRaises(ValueError):
            raise ValueError()
        with self.assertRaises(TypeError):
            raise TypeError()
        with pytest.raises(Exception):
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

        # Use as context managers instead of function calls
        with self.assertRaises(ValueError):
            raise_value('foo', bar='baz')
        assert flags.raise_value == (('foo', ), {'bar': 'baz'})

        with self.assertRaises(TypeError):
            raise_type('qux', baz='foo')
        assert flags.raise_type == (('qux', ), {'baz': 'foo'})

        with pytest.raises(Exception):
            with self.assertRaises(ValueError):
                raise_value(False)
        assert flags.raise_value == ((False, ), {})

    def test_assert_raises_regex(self):
        with self.assertRaisesRegex(ValueError, '[a-z]+'):
            raise ValueError('hello')
        with self.assertRaisesRegex(TypeError, '[a-z]+'):
            raise TypeError('goodbye')
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

        # Use as context managers instead of function calls
        with self.assertRaisesRegex(ValueError, '[a-z]+'):
            raise_value('foo', bar='baz')
        assert flags.raise_value == (('foo', ), {'bar': 'baz'})

        with self.assertRaisesRegex(TypeError, '[a-z]+'):
            raise_type('qux', baz='foo')
        assert flags.raise_type == (('qux', ), {'baz': 'foo'})

        with pytest.raises(AssertionError):
            with self.assertRaisesRegex(ValueError, '[a-z]+'):
                raise_value(False)
        assert flags.raise_value == ((False, ), {})

    def test_assert_warns(self):
        with self.assertWarns(DeprecationWarning):
            warn('hello', DeprecationWarning)
        with self.assertWarns(FutureWarning):
            warn('goodbye', FutureWarning)
        # This should NOT raise an exception because no warning is emitted
        # with self.assertWarns(DeprecationWarning):
        #     assert 1 == 1

        flags = mock.MagicMock()
        del flags.raise_value
        del flags.raise_type

        def raise_value(*args, **kwargs):
            flags.raise_value = args, kwargs
            if not args or args[0] is not False:
                warn('hello', DeprecationWarning)

        def raise_type(*args, **kwargs):
            flags.raise_type = args, kwargs
            warn('goodbye', FutureWarning)

        # Use as context managers instead of function calls
        with self.assertWarns(DeprecationWarning):
            raise_value('foo', bar='baz')
        assert flags.raise_value == (('foo', ), {'bar': 'baz'})

        with self.assertWarns(FutureWarning):
            raise_type('qux', baz='foo')
        assert flags.raise_type == (('qux', ), {'baz': 'foo'})

        # This should raise an exception because no warning is emitted
        with pytest.raises(Failed):
            with self.assertWarns(DeprecationWarning):
                raise_value(False)
        assert flags.raise_value == ((False, ), {})

    def test_assert_warns_regex(self):
        with self.assertWarnsRegex(DeprecationWarning, '[a-z]+'):
            warn('hello', DeprecationWarning)
        with self.assertWarnsRegex(FutureWarning, '[a-z]+'):
            warn('goodbye', FutureWarning)
        # This should raise an exception because the warning doesn't match the regex
        with pytest.raises(Failed):
            with self.assertWarnsRegex(DeprecationWarning, '[a-z]+'):
                warn('1234', DeprecationWarning)

        flags = mock.MagicMock()
        del flags.raise_value
        del flags.raise_type

        def raise_value(*args, **kwargs):
            flags.raise_value = args, kwargs
            if not args or args[0] is not False:
                warn('hello', DeprecationWarning)
            else:
                warn('1234', DeprecationWarning)

        def raise_type(*args, **kwargs):
            flags.raise_type = args, kwargs
            warn('goodbye', FutureWarning)

        # Use as context managers instead of function calls
        with self.assertWarnsRegex(DeprecationWarning, '[a-z]+'):
            raise_value('foo', bar='baz')
        assert flags.raise_value == (('foo', ), {'bar': 'baz'})

        with self.assertWarnsRegex(FutureWarning, '[a-z]+'):
            raise_type('qux', baz='foo')
        assert flags.raise_type == (('qux', ), {'baz': 'foo'})

        # This should raise an exception because the warning doesn't match the regex
        with pytest.raises(Failed):
            with self.assertWarnsRegex(DeprecationWarning, '[a-z]+'):
                raise_value(False)
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

    def test_assert_count_equal(self):
        # Test that assertCountEqual works correctly
        self.assertCountEqual([1, 2, 3], [3, 2, 1])
        self.assertCountEqual(['a', 'b', 'c'], ['c', 'b', 'a'])
        
        # Test that it fails when counts don't match
        with pytest.raises(AssertionError):
            self.assertCountEqual([1, 2, 3], [1, 2])
        
        with pytest.raises(AssertionError):
            self.assertCountEqual([1, 2], [1, 2, 3])
        
        with pytest.raises(AssertionError):
            self.assertCountEqual([1, 2, 3], [1, 2, 4])

    def test_deprecated_assert_equals(self):
        with catch_warnings(record=True) as w:
            simplefilter('always', DeprecationWarning)
            self.assertEquals(1, 1)  # This should emit a warning

            with pytest.raises(AssertionError):
                self.assertEquals(1, 2)  # This should also emit a warning

        assert w is not None
        assert len(w) == 2
        assert issubclass(w[0].category, DeprecationWarning)
        assert issubclass(w[1].category, DeprecationWarning)

    def test_deprecated_fail_unless_equal(self):
        with catch_warnings(record=True) as w:
            simplefilter('always', DeprecationWarning)
            self.failUnlessEqual(1, 1)  # This should emit a warning

            with pytest.raises(AssertionError):
                self.failUnlessEqual(1, 2)  # This should also emit a warning

        assert w is not None
        assert len(w) == 2
        assert issubclass(w[0].category, DeprecationWarning)
        assert issubclass(w[1].category, DeprecationWarning)

    def test_deprecated_assert_not_equals(self):
        with catch_warnings(record=True) as w:
            simplefilter('always', DeprecationWarning)
            self.assertNotEquals(1, 2)  # This should emit a warning

            with pytest.raises(AssertionError):
                self.assertNotEquals(1, 1)  # This should also emit a warning

        assert w is not None
        assert len(w) == 2
        assert issubclass(w[0].category, DeprecationWarning)
        assert issubclass(w[1].category, DeprecationWarning)

    def test_deprecated_fail_if_equal(self):
        with catch_warnings(record=True) as w:
            simplefilter('always', DeprecationWarning)
            self.failIfEqual(1, 2)  # This should emit a warning

            with pytest.raises(AssertionError):
                self.failIfEqual(1, 1)  # This should also emit a warning

        assert w is not None
        assert len(w) == 2
        assert issubclass(w[0].category, DeprecationWarning)
        assert issubclass(w[1].category, DeprecationWarning)

    def test_deprecated_assert_almost_equals(self):
        with catch_warnings(record=True) as w:
            simplefilter('always', DeprecationWarning)
            self.assertAlmostEquals(1.0, 1.0)  # This should emit a warning

            with pytest.raises(AssertionError):
                self.assertAlmostEquals(1.0, 2.0)  # This should also emit a warning

        assert w is not None
        assert len(w) == 2
        assert issubclass(w[0].category, DeprecationWarning)
        assert issubclass(w[1].category, DeprecationWarning)

    def test_deprecated_fail_unless_almost_equal(self):
        with catch_warnings(record=True) as w:
            simplefilter('always', DeprecationWarning)
            self.failUnlessAlmostEqual(1.0, 1.0)  # This should emit a warning

            with pytest.raises(AssertionError):
                self.failUnlessAlmostEqual(1.0, 2.0)  # This should also emit a warning

        assert w is not None
        assert len(w) == 2
        assert issubclass(w[0].category, DeprecationWarning)
        assert issubclass(w[1].category, DeprecationWarning)

    def test_deprecated_assert_not_almost_equals(self):
        with catch_warnings(record=True) as w:
            simplefilter('always', DeprecationWarning)
            self.assertNotAlmostEquals(1.0, 2.0)  # This should emit a warning

            with pytest.raises(AssertionError):
                self.assertNotAlmostEquals(1.0, 1.0)  # This should also emit a warning

        assert w is not None
        assert len(w) == 2
        assert issubclass(w[0].category, DeprecationWarning)
        assert issubclass(w[1].category, DeprecationWarning)

    def test_deprecated_fail_if_almost_equal(self):
        with catch_warnings(record=True) as w:
            simplefilter('always', DeprecationWarning)
            self.failIfAlmostEqual(1.0, 2.0)  # This should emit a warning

            with pytest.raises(AssertionError):
                self.failIfAlmostEqual(1.0, 1.0)  # This should also emit a warning

        assert w is not None
        assert len(w) == 2
        assert issubclass(w[0].category, DeprecationWarning)
        assert issubclass(w[1].category, DeprecationWarning)

    def test_deprecated_fail_unless(self):
        with catch_warnings(record=True) as w:
            simplefilter('always', DeprecationWarning)
            self.failUnless(True)  # This should emit a warning

            with pytest.raises(AssertionError):
                self.failUnless(False)  # This should also emit a warning

        assert w is not None
        assert len(w) == 2
        assert issubclass(w[0].category, DeprecationWarning)
        assert issubclass(w[1].category, DeprecationWarning)

    def test_deprecated_assert_(self):
        with catch_warnings(record=True) as w:
            simplefilter('always', DeprecationWarning)
            self.assert_(True)  # This should emit a warning

            with pytest.raises(AssertionError):
                self.assert_(False)  # This should also emit a warning

        assert w is not None
        assert len(w) == 2
        assert issubclass(w[0].category, DeprecationWarning)
        assert issubclass(w[1].category, DeprecationWarning)

    def test_deprecated_fail_if(self):
        with catch_warnings(record=True) as w:
            simplefilter('always', DeprecationWarning)
            self.failIf(False)  # This should emit a warning

            with pytest.raises(AssertionError):
                self.failIf(True)  # This should also emit a warning

        assert w is not None
        assert len(w) == 2
        assert issubclass(w[0].category, DeprecationWarning)
        assert issubclass(w[1].category, DeprecationWarning)

    def test_deprecated_assert_regexp_matches(self):
        with catch_warnings(record=True) as w:
            simplefilter('always', DeprecationWarning)
            self.assertRegexpMatches('hello', 'hello')  # This should emit a warning

            with pytest.raises(AssertionError):
                self.assertRegexpMatches('hello', 'world')  # This should also emit a warning

        assert w is not None
        assert len(w) == 2
        assert issubclass(w[0].category, DeprecationWarning)
        assert issubclass(w[1].category, DeprecationWarning)

    def test_deprecated_assert_not_regexp_matches(self):
        with catch_warnings(record=True) as w:
            simplefilter('always', DeprecationWarning)
            self.assertNotRegexpMatches('hello', 'world')  # This should emit a warning

            with pytest.raises(AssertionError):
                self.assertNotRegexpMatches('hello', 'hello')  # This should also emit a warning

        assert w is not None
        assert len(w) == 2
        assert issubclass(w[0].category, DeprecationWarning)
        assert issubclass(w[1].category, DeprecationWarning)

    def test_deprecated_fail_unless_raises(self):
        with catch_warnings(record=True) as w:
            simplefilter('always', DeprecationWarning)
            
            with self.failUnlessRaises(ValueError):
                raise ValueError("test")  # This should emit a warning

            with pytest.raises(AssertionError):
                with self.failUnlessRaises(ValueError):
                    pass  # This should also emit a warning

        assert w is not None
        assert len(w) == 2
        assert issubclass(w[0].category, DeprecationWarning)
        assert issubclass(w[1].category, DeprecationWarning)


# noinspection PyTypeChecker,PyUnresolvedReferences
class TestPyTestServerTestCaseDeprecations(object):
    def test_setup_class(self):
        class PyTestServerTestCase1(PyTestServerTestCase):
            pass

        with catch_warnings(record=True) as w:
            simplefilter('always', DeprecationWarning)

            PyTestServerTestCase1.setup_class()

        assert w is not None
        assert len(w) == 0

        flag = mock.MagicMock()

        class PyTestServerTestCase2(PyTestServerTestCase):
            @classmethod
            def setUpClass(cls):
                flag.called = True

        with catch_warnings(record=True) as w:
            simplefilter('always', DeprecationWarning)

            PyTestServerTestCase2.setup_class()

        assert w is not None
        assert flag.called is True
        assert len(w) == 1
        assert issubclass(w[-1].category, DeprecationWarning)

    def test_teardown_class(self):
        class PyTestServerTestCase1(PyTestServerTestCase):
            pass

        with catch_warnings(record=True) as w:
            simplefilter('always', DeprecationWarning)

            PyTestServerTestCase1.teardown_class()

        assert w is not None
        assert len(w) == 0

        flag = mock.MagicMock()

        class PyTestServerTestCase2(PyTestServerTestCase):
            @classmethod
            def tearDownClass(cls):
                flag.called = True

        with catch_warnings(record=True) as w:
            simplefilter('always', DeprecationWarning)

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
        with catch_warnings(record=True) as w:
            simplefilter('always', DeprecationWarning)

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
        with catch_warnings(record=True) as w:
            simplefilter('always', DeprecationWarning)

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
        with catch_warnings(record=True) as w:
            simplefilter('always', DeprecationWarning)

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
        with catch_warnings(record=True) as w:
            simplefilter('always', DeprecationWarning)

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
        with catch_warnings(record=True) as w:
            simplefilter('always', DeprecationWarning)

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
