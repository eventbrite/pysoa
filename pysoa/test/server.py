from __future__ import (
    absolute_import,
    unicode_literals,
)

import collections
import importlib
import os
import re
import traceback
from typing import (
    AbstractSet,
    Any,
    AnyStr,
    Callable,
    Container,
    Dict,
    Iterable,
    List,
    NoReturn,
    Optional,
    Pattern,
    Sequence,
    Sized,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
)
import unittest
import warnings

from _pytest._code.code import ExceptionInfo
from _pytest.python_api import RaisesContext
from _pytest.recwarn import WarningsChecker
from conformity.settings import SettingsData
import pytest
import six

from pysoa.client.client import Client
from pysoa.common.errors import Error
from pysoa.common.types import (
    ActionResponse,
    Body,
)
from pysoa.server.server import Server
from pysoa.test.assertions import (
    raises_call_action_error,
    raises_error_codes,
    raises_field_errors,
)


__all__ = (
    'PyTestServerTestCase',
    'ServerTestCase',
    'UnitTestServerTestCase',
)


# noinspection PyPep8Naming,PyAttributeOutsideInit,PyMethodMayBeStatic
class _BaseServerTestCase(object):
    """
    Base class for test cases that need to call the server.

    It runs calls to actions through the server stack so they get middleware run
    (for things like request.metrics) and requests/responses run through a
    serializer cycle.
    """

    server_class = None  # type: Optional[Type[Server]]
    server_settings = None  # type: Optional[SettingsData]

    def setup_pysoa(self):  # type: () -> None
        if self.server_class is None:
            raise TypeError('You must specify `server_class` in `ServerTestCase` subclasses')
        if not issubclass(self.server_class, Server):
            raise TypeError('`server_class` must be a subclass of `Server` in `ServerTestCase` subclasses')
        if not self.server_class.service_name:
            raise TypeError('`server_class.service_name` must be set in `ServerTestCase` subclasses')

        self.service_name = self.server_class.service_name

        # Get settings based on Django mode
        if self.server_settings is not None:
            settings = self.server_settings
        else:
            if self.server_class.use_django:
                # noinspection PyUnresolvedReferences
                from django.conf import settings as django_settings
                settings = cast(SettingsData, django_settings.SOA_SERVER_SETTINGS)  # type: ignore
            else:
                settings_module = os.environ.get('PYSOA_SETTINGS_MODULE', None)
                if not settings_module:
                    raise AssertionError('PYSOA_SETTINGS_MODULE environment variable must be set to run tests.')
                try:
                    thing = importlib.import_module(settings_module)
                    settings = cast(SettingsData, thing.SOA_SERVER_SETTINGS)  # type: ignore
                except (ImportError, AttributeError) as e:
                    raise AssertionError('Could not access {}.SOA_SERVER_SETTINGS: {}'.format(settings_module, e))

        self.client = Client(
            {
                self.service_name: {
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
        # type: (six.text_type, Body, Optional[six.text_type], **Any) -> ActionResponse
        # Using this enables tests that call the same action dozens of times to not have to code in the service name
        # for every single action call (but they still can by passing in `service_name`)
        return self.client.call_action(service_name or self.service_name, action, body=body, **kwargs)

    def assertActionRunsWithAndReturnErrors(self, action, body, **kwargs):
        # type: (six.text_type, Body, **Any) -> List[Error]
        with raises_call_action_error() as exc_info:
            self.call_action(action, body, **kwargs)
        return exc_info.soa_errors

    def assertActionRunsWithFieldErrors(
        self,
        action,  # type: six.text_type
        body,  # type: Body
        field_errors,  # type: Dict[six.text_type, Union[Iterable[six.text_type], six.text_type]]
        only=False,  # type: bool
        **kwargs  # type: Any
    ):  # type: (...) -> None
        with raises_field_errors(field_errors, only=only):
            self.call_action(action, body, **kwargs)

    def assertActionRunsWithOnlyFieldErrors(
        self,
        action,  # type: six.text_type
        body,  # type: Body
        field_errors,  # type: Dict[six.text_type, Union[Iterable[six.text_type], six.text_type]]
        **kwargs  # type: Any
    ):  # type: (...) -> None
        self.assertActionRunsWithFieldErrors(action, body, field_errors, only=True, **kwargs)

    def assertActionRunsWithErrorCodes(
        self,
        action,  # type: six.text_type
        body,  # type: Body
        error_codes,  # type: Union[Iterable[six.text_type], six.text_type]
        only=False,  # type: bool
        **kwargs  # type: Any
    ):  # type: (...) -> None
        with raises_error_codes(error_codes, only=only):
            self.call_action(action, body, **kwargs)

    def assertActionRunsWithOnlyErrorCodes(
        self,
        action,  # type: six.text_type
        body,  # type: Body
        error_codes,  # type: Union[Iterable[six.text_type], six.text_type]
        **kwargs  # type: Any
    ):  # type: (...) -> None
        self.assertActionRunsWithErrorCodes(action, body, error_codes, only=True, **kwargs)


class UnitTestServerTestCase(unittest.TestCase, _BaseServerTestCase):
    def setUp(self):  # type: () -> None
        super(UnitTestServerTestCase, self).setUp()

        self.setup_pysoa()


# noinspection PyShadowingBuiltins
_S = TypeVar('_S', six.text_type, six.binary_type)
_C = TypeVar('_C', bound=Callable)


def _deprecate(original_func):  # type: (_C) -> _C
    def deprecated_func(*args, **kwargs):
        warnings.warn(
            'Please use {0} instead. This will be removed in PySOA 2.0.'.format(original_func.__name__),
            DeprecationWarning,
            2,
        )
        return original_func(*args, **kwargs)

    return cast(_C, deprecated_func)


def _methods_are_not_same(m1, m2):
    if six.PY2:
        return m1.__func__ is not m2.__func__

    return m1 is not m2


# noinspection PyPep8Naming,PyAttributeOutsideInit,PyMethodMayBeStatic
class PyTestServerTestCase(_BaseServerTestCase):
    @classmethod
    def setUpClass(cls):  # type: () -> None
        """
        Deprecated. Override :method:`setup_class`, instead, and be sure to still call `super`.
        """

    @classmethod
    def setup_class(cls):  # type: () -> None
        # noinspection PyUnresolvedReferences
        if cls.setUpClass.__func__ is not PyTestServerTestCase.setUpClass.__func__:  # type: ignore
            warnings.warn(
                '`ServerTestCase.setUpClass` is deprecated. `ServerTestCase` no longer inherits from '
                '`unittest.TestCase`. Your test setup has been run, but you should change the `setUpClass` method name '
                'to `setup_class` and be sure to still call `super` within it. This will be removed in PySOA 2.0.',
                DeprecationWarning,
            )
            cls.setUpClass()

    @classmethod
    def tearDownClass(cls):  # type: () -> None
        """
        Deprecated. Override :method:`teardown_class`, instead, and be sure to still call `super`.
        """

    @classmethod
    def teardown_class(cls):  # type: () -> None
        # noinspection PyUnresolvedReferences
        if cls.tearDownClass.__func__ is not PyTestServerTestCase.tearDownClass.__func__:  # type: ignore
            warnings.warn(
                '`ServerTestCase.tearDownClass` is deprecated. `ServerTestCase` no longer inherits from '
                '`unittest.TestCase`. Your test setup has been run, but you should change the `tearDownClass` method '
                'name to `teardown_class` and be sure to still call `super` within it. This will be removed in PySOA '
                '2.0.',
                DeprecationWarning,
            )
            cls.tearDownClass()

    def setUp(self):  # type: () -> None
        """
        Deprecated. Override :method:`setup_method`, instead, and be sure to still call `super`.
        """

    def setup_method(self):  # type: () -> None
        self._cleanups = []  # type: List[Tuple[Callable, Tuple[Any, ...], Dict[str, Any]]]

        self.setup_pysoa()

        if _methods_are_not_same(self.__class__.setUp, PyTestServerTestCase.setUp):
            warnings.warn(
                '`ServerTestCase.setUp` is deprecated. `ServerTestCase` no longer inherits from `unittest.TestCase`. '
                'Your test setup has been run, but you should change the `setUp` method name to `setup_method` and '
                'be sure to still call `super` within it. This will be removed in PySOA 2.0.',
                DeprecationWarning,
            )
            self.setUp()

    def tearDown(self):  # type: () -> None
        """
        Deprecated. Override :method:`setup_method`, instead, and be sure to still call `super`.
        """

    def teardown_method(self):  # type: () -> None
        if _methods_are_not_same(self.__class__.tearDown, PyTestServerTestCase.tearDown):
            warnings.warn(
                '`ServerTestCase.tearDown` is deprecated. `ServerTestCase` no longer inherits from '
                '`unittest.TestCase`. Your test setup has been run, but you should change the `tearDown` method name '
                'to `teardown_method` and be sure to still call `super` within it. This will be removed in PySOA 2.0.',
                DeprecationWarning,
            )
            self.tearDown()

        self.doCleanups()

    def addCleanup(self, function, *args, **kwargs):
        # type: (Callable, *Any, **Any) -> None
        warnings.warn(
            '`ServerTestCase.addCleanup` is deprecated. `ServerTestCase` no longer inherits from `unittest.TestCase`. '
            'Your test cleanup will be run, but you should stop using `addCleanup` and clean up your tests in '
            '`teardown_method`, instead. This will be removed in PySOA 2.0.',
            DeprecationWarning,
        )
        self._cleanups.append((function, args, kwargs))

    def doCleanups(self):
        # type: () -> bool
        ok = True
        while self._cleanups:
            function, args, kwargs = self._cleanups.pop(-1)
            # noinspection PyBroadException
            try:
                function(*args, **kwargs)
            except KeyboardInterrupt:
                raise
            except:  # noqa: E722
                if not self._cleanups:
                    # If it's the last exception, raise it.
                    raise
                ok = False
                traceback.print_exc()
        return ok

    def fail(self, msg=None):
        # type: (Optional[object]) -> NoReturn
        if msg:
            raise AssertionError(msg)
        raise AssertionError()

    def assertEqual(self, first, second, msg=None):
        # type: (Any, Any, Optional[object]) -> None
        assert first == second, msg or ''

    assertEquals = _deprecate(assertEqual)
    failUnlessEqual = _deprecate(assertEqual)

    def assertNotEqual(self, first, second, msg=None):
        # type: (Any, Any, Optional[object]) -> None
        assert first != second, msg or ''

    assertNotEquals = _deprecate(assertNotEqual)
    failIfEqual = _deprecate(assertNotEqual)

    def assertMultiLineEqual(self, first, second, msg=None):
        # type: (six.text_type, six.text_type, Optional[object]) -> None
        assert isinstance(first, six.string_types), 'First argument is not a string'
        assert isinstance(second, six.string_types), 'Second argument is not a string'
        assert first == second, msg or ''

    def assertSequenceEqual(self, first, second, msg=None, seq_type=None):
        # type: (Sequence[Any], Sequence[Any], Optional[object], Optional[Type[Sequence[Any]]]) -> None
        if seq_type is not None:
            assert isinstance(first, seq_type)
            assert isinstance(second, seq_type)
        assert first == second, msg or ''

    def assertListEqual(self, first, second, msg=None):
        # type: (List[Any], List[Any], Optional[object]) -> None
        self.assertSequenceEqual(first, second, msg, list)

    def assertTupleEqual(self, first, second, msg=None):
        # type: (Tuple[Any, ...], Tuple[Any, ...], Optional[object]) -> None
        self.assertSequenceEqual(first, second, msg, tuple)

    def assertSetEqual(self, first, second, msg=None):
        # type: (AbstractSet[Any], AbstractSet[Any], Optional[object]) -> None
        assert isinstance(first, AbstractSet), 'First argument is not a set'
        assert isinstance(second, AbstractSet), 'Second argument is not a set'
        assert first == second, msg or ''

    def assertDictEqual(self, first, second, msg=None):
        # type: (Dict[Any, Any], Dict[Any, Any], Optional[object]) -> None
        assert isinstance(first, dict), 'First argument is not a dictionary'
        assert isinstance(second, dict), 'Second argument is not a dictionary'
        assert first == second, msg or ''

    def assertCountEqual(self, first, second, msg=None):
        # type: (Union[Sized, Iterable], Union[Sized, Iterable], Optional[object]) -> None
        if isinstance(first, Iterable) and isinstance(second, Iterable):
            first_counter = collections.Counter(first)
            second_counter = collections.Counter(second)
            assert first_counter == second_counter, msg or ''
        else:
            assert len(first) == len(second), msg or ''  # type: ignore

    def assertAlmostEqual(self, first, second, places=None, msg=None, delta=None):
        # type: (float, float, Optional[int], Optional[object], Optional[float]) -> None
        if first == second:
            return
        assert delta is None or places is None, 'Specify delta or places, but not both'
        diff = abs(first - second)
        if delta is not None:
            assert diff <= delta, msg or '{} != {} within {} delta ({} difference)'.format(first, second, delta, diff)
        else:
            if places is None:
                places = 7
            assert round(diff, places) == 0, (
                msg or '{} != {} within {} places ({} difference)'.format(first, second, places, diff)
            )

    assertAlmostEquals = _deprecate(assertAlmostEqual)
    failUnlessAlmostEqual = _deprecate(assertAlmostEqual)

    def assertNotAlmostEqual(self, first, second, places=None, msg=None, delta=None):
        # type: (float, float, Optional[int], Optional[object], Optional[float]) -> None
        assert first != second, msg or ''
        assert delta is None or places is None, 'Specify delta or places, but not both'
        diff = abs(first - second)
        if delta is not None:
            assert diff > delta, msg or '{} == {} within {} delta ({} difference)'.format(first, second, delta, diff)
        else:
            if places is None:
                places = 7
            assert round(diff, places) != 0, (
                msg or '{} == {} within {} places ({} difference)'.format(first, second, places, diff)
            )

    assertNotAlmostEquals = _deprecate(assertNotAlmostEqual)
    failIfAlmostEqual = _deprecate(assertNotAlmostEqual)

    def assertTrue(self, expr, msg=None):
        # type: (Any, Optional[object]) -> None
        assert expr, msg or ''

    failUnless = _deprecate(assertTrue)
    assert_ = _deprecate(assertTrue)

    def assertFalse(self, expr, msg=None):
        # type: (Any, Optional[object]) -> None
        assert not expr, msg or ''

    failIf = _deprecate(assertFalse)

    def assertIs(self, first, second, msg=None):
        # type: (Any, Any, Optional[object]) -> None
        assert first is second, msg or ''

    def assertIsNot(self, first, second, msg=None):
        # type: (Any, Any, Optional[object]) -> None
        assert first is not second, msg or ''

    def assertIsNone(self, expr, msg=None):
        # type: (Any, Optional[object]) -> None
        assert expr is None, msg or ''

    def assertIsNotNone(self, expr, msg=None):
        # type: (Any, Optional[object]) -> None
        assert expr is not None, msg or ''

    def assertIn(self, member, container, msg=None):
        # type: (Any, Union[Iterable[Any], Container[Any]], Optional[object]) -> None
        assert member in container, msg or ''  # type: ignore

    def assertNotIn(self, member, container, msg=None):
        # type: (Any, Union[Iterable[Any], Container[Any]], Optional[object]) -> None
        assert member not in container, msg or ''  # type: ignore

    def assertIsInstance(self, obj, cls, msg=None):
        # type: (Any, Union[Type, Tuple[Type, ...]], Optional[object]) -> None
        assert isinstance(obj, cls), msg or ''

    def assertNotIsInstance(self, obj, cls, msg=None):
        # type: (Any, Union[Type, Tuple[Type, ...]], Optional[object]) -> None
        assert not isinstance(obj, cls), msg or ''

    def assertGreater(self, first, second, msg=None):
        # type: (Any, Any, Optional[object]) -> None
        assert first > second, msg or ''

    def assertGreaterEqual(self, first, second, msg=None):
        # type: (Any, Any, Optional[object]) -> None
        assert first >= second, msg or ''

    def assertLess(self, first, second, msg=None):
        # type: (Any, Any, Optional[object]) -> None
        assert first < second, msg or ''

    def assertLessEqual(self, first, second, msg=None):
        # type: (Any, Any, Optional[object]) -> None
        assert first <= second, msg or ''

    def assertRegex(self, text, regex, msg=None):
        # type: (_S, Union[Pattern[_S], _S], Optional[object]) -> None
        assert regex, 'Regex must not be None or empty'
        if isinstance(regex, six.string_types):
            regex = re.compile(regex)
        assert regex.search(text), (  # type: ignore
            msg or 'Pattern: {}\nDoes not match text: {!r}'.format(regex.pattern, text)  # type: ignore
        )

    assertRegexpMatches = _deprecate(assertRegex)

    def assertNotRegex(self, text, regex, msg=None):
        # type: (_S, Union[Pattern[_S], _S], Optional[object]) -> None
        assert regex, 'Regex must not be None or empty'
        if isinstance(regex, six.string_types):
            regex = re.compile(regex)
        assert not regex.search(text), (  # type: ignore
            msg or 'Pattern: {}\nUnexpectedly matches text: {!r}'.format(regex.pattern, text)  # type: ignore
        )

    assertNotRegexpMatches = _deprecate(assertNotRegex)

    # noinspection PyShadowingBuiltins
    def assertRaises(
        self,
        exception,  # type: Union[Type[BaseException], Tuple[Type[BaseException], ...]]
        callable=None,  # type: Callable
        *args,  # type: Any
        **kwargs  # type: Any
    ):
        # type: (...) -> RaisesContext
        if callable:
            with pytest.raises(exception):
                callable(*args, **kwargs)
            # noinspection PyTypeChecker
            return None  # type: ignore

        ExceptionInfo.exception = ExceptionInfo.value  # alias the property for backwards compatibility
        return pytest.raises(exception, **kwargs)

    failUnlessRaises = _deprecate(assertRaises)

    # noinspection PyShadowingBuiltins
    def assertRaisesRegex(
        self,
        exception,  # type: Union[Type[BaseException], Tuple[Type[BaseException], ...]]
        regex,  # type: Union[Pattern[AnyStr], AnyStr]
        callable=None,  # type: Callable
        *args,  # type: Any
        **kwargs  # type: Any
    ):
        # type: (...) -> RaisesContext
        if callable:
            with pytest.raises(exception, match=regex):
                callable(*args, **kwargs)
            # noinspection PyTypeChecker
            return None  # type: ignore

        ExceptionInfo.exception = ExceptionInfo.value  # alias the property for backwards compatibility
        kwargs['match'] = regex
        return pytest.raises(exception, **kwargs)

    assertRaisesRegexp = _deprecate(assertRaisesRegex)

    # noinspection PyShadowingBuiltins
    def assertWarns(
        self,
        exception,  # type: Union[Type[Warning], Tuple[Type[Warning], ...]]
        callable=None,  # type: Callable
        *args,  # type: Any
        **kwargs  # type: Any
    ):
        # type: (...) -> Optional[WarningsChecker]
        if callable:
            with pytest.warns(exception):
                callable(*args, **kwargs)
            return None

        return pytest.warns(exception, **kwargs)

    # noinspection PyShadowingBuiltins
    def assertWarnsRegex(
        self,
        exception,  # type: Union[Type[Warning], Tuple[Type[Warning], ...]]
        regex,  # type: Union[Pattern[AnyStr], AnyStr]
        callable=None,  # type: Callable
        *args,  # type: Any
        **kwargs  # type: Any
    ):
        # type: (...) -> None
        if callable:
            with pytest.warns(exception, match=regex):
                callable(*args, **kwargs)
            return None

        kwargs['match'] = regex
        return pytest.warns(exception, **kwargs)


# ServerTestCase = UnitTestServerTestCase
ServerTestCase = PyTestServerTestCase
