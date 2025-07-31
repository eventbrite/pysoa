from __future__ import (
    absolute_import,
    unicode_literals,
)

import collections
import importlib
import logging
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
    NamedTuple,
    Optional,
    Pattern,
    Sequence,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
)
import unittest
# noinspection PyProtectedMember
from unittest.util import (
    _count_diff_all_purpose,
    _count_diff_hashable,
)
import warnings
from warnings import warn, catch_warnings, simplefilter  # type: ignore

from _pytest._code.code import ExceptionInfo
import pytest
import six

from pysoa.client.client import Client
from pysoa.common.errors import Error
from pysoa.common.transport.local import LocalClientTransport
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
from conformity.settings import SettingsData  # Added for mypy compatibility


try:
    from typing import Literal  # type: ignore
except ImportError:
    from typing_extensions import Literal  # type: ignore

try:
    from typing import NoReturn  # type: ignore
except ImportError:
    from typing_extensions import NoReturn  # type: ignore


__all__ = (
    'BaseServerTestCase',
    'PyTestServerTestCase',
    'ServerTestCase',
    'UnitTestServerTestCase',
)


# noinspection PyPep8Naming,PyAttributeOutsideInit,PyMethodMayBeStatic
class BaseServerTestCase(object):
    """
    Base class for all test classes that need to call the server. It runs calls to actions through the server stack so
    configured middleware runs and requests and responses go through the normal validation cycles. Note that this uses
    the local transports, so requests and responses are not serialized.
    """

    server_class = None  # type: Optional[Type[Server]]
    """The reference to your `Server` class, which must be set in order to use the service helpers in this class."""

    server_settings = None  # type: Optional[SettingsData]
    """
    A settings dict to use when instantiating your `Server` class. If not specified, the service helpers in this
    class will attempt to get settings from the configured Django or PySOA settings module.
    """

    def setup_pysoa(self):  # type: () -> None
        """
        Sets up `self.client` for use in calling the local testing service. Requires you to configure `server_class`
        and `server_settings` class attributes.
        """
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
        # noinspection PyProtectedMember
        cast(
            LocalClientTransport,
            self.client._get_handler(self.service_name).transport,
        ).server._skip_django_database_cleanup = True

    def call_action(self, action, body: Optional[dict[str, Any]] = None, service_name=None, **kwargs) -> ActionResponse:
        """
        A convenience method alternative to calling `self.client.call_action` that allows you to omit the service name.

        :param action: The required action name to call
        :param body: The optional request body to send to the action
        :param service_name: The optional service name if you need to call a service other than the configured local
                             testing service.
        :param kwargs: Additional keyword arguments to send to :meth:`pysoa.client.client.Client.call_action`.

        :return: The value returned from :meth:`pysoa.client.client.Client.call_action`.
        """
        return self.client.call_action(service_name or self.service_name, action, body=body, **kwargs)

    def assertActionRunsWithAndReturnErrors(self, action, body, **kwargs):
        # type: (six.text_type, Body, **Any) -> List[Error]
        """
        Calls `self.call_action` and asserts that it runs with errors, and returns those errors.
        """
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
        """
        Calls `self.call_action` and asserts that it runs with the specified field errors.

        :param action: The name of the action to call
        :param body: The request body to send to the action
        :param field_errors: A dictionary of field name keys to error codes or iterables of error codes for the fields
                             (all of the specified errors must be present in the response).
        :param only: If `True` additional errors cause a failure (defaults to `False`, so additional errors are
                     ignored).
        :param kwargs: Additional keyword arguments to send to :meth:`pysoa.client.client.Client.call_action`.
        """
        with raises_field_errors(field_errors, only=only):
            self.call_action(action, body, **kwargs)

    def assertActionRunsWithOnlyFieldErrors(
        self,
        action,  # type: six.text_type
        body,  # type: Body
        field_errors,  # type: Dict[six.text_type, Union[Iterable[six.text_type], six.text_type]]
        **kwargs  # type: Any
    ):  # type: (...) -> None
        """
        Convenient alternative to calling :meth:`assertActionRunsWithFieldErrors` that sets the `only` argument to
        `True`.
        """
        self.assertActionRunsWithFieldErrors(action, body, field_errors, only=True, **kwargs)

    def assertActionRunsWithErrorCodes(
        self,
        action,  # type: six.text_type
        body,  # type: Body
        error_codes,  # type: Union[Iterable[six.text_type], six.text_type]
        only=False,  # type: bool
        **kwargs  # type: Any
    ):  # type: (...) -> None
        """
        Calls `self.call_action` and asserts that it runs with the specified error codes.

        :param action: The name of the action to call
        :param body: The request body to send to the action
        :param error_codes: A single error code or iterable of multiple error codes (all of the specified errors must
                            be present in the response).
        :param only: If `True` additional errors cause a failure (defaults to `False`, so additional errors are
                     ignored).
        :param kwargs: Additional keyword arguments to send to :meth:`pysoa.client.client.Client.call_action`.
        """
        with raises_error_codes(error_codes, only=only):
            self.call_action(action, body, **kwargs)

    def assertActionRunsWithOnlyErrorCodes(
        self,
        action,  # type: six.text_type
        body,  # type: Body
        error_codes,  # type: Union[Iterable[six.text_type], six.text_type]
        **kwargs  # type: Any
    ):  # type: (...) -> None
        """
        Convenient alternative to calling :meth:`assertActionRunsWithErrorCodes` that sets the `only` argument to
        `True`.
        """
        self.assertActionRunsWithErrorCodes(action, body, error_codes, only=True, **kwargs)


class UnitTestServerTestCase(unittest.TestCase, BaseServerTestCase):
    """
    An extension of :class:`BaseServerTestCase` that calls :meth:`BaseServerTestCase.setup_pysoa` in :meth:`setUp`.
    If you override `setUp` in your test class, you must call `super().setUp()`, or else it will not work properly.
    """
    def setUp(self):  # type: () -> None
        super(UnitTestServerTestCase, self).setUp()

        self.setup_pysoa()


# noinspection PyShadowingBuiltins
_S = TypeVar('_S', six.text_type, six.binary_type)
_C = TypeVar('_C', bound=Callable)


def _deprecate(original_func):  # type: (_C) -> _C
    def deprecated_func(*args, **kwargs):
        warn(
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


if six.PY2:
    # noinspection PyUnresolvedReferences
    _string_types = (str, unicode)  # type: Tuple[Type, ...] # noqa
else:
    # noinspection PyUnresolvedReferences
    _string_types = (str, bytes)  # noqa


# noinspection PyPep8Naming,PyAttributeOutsideInit,PyMethodMayBeStatic
class PyTestServerTestCase(BaseServerTestCase):
    """
    An extension of :class:`BaseServerTestCase` that calls :meth:`BaseServerTestCase.setup_pysoa` in
    :meth:`setup_method`. If you override `setup_method` in your test class, you must call `super().setup_method()`, or
    else it will not work properly.

    This class will detect in your test class and call, if present, implementations of `unittest`-like `setUpClass`,
    `tearDownClass`, `setUp`, and `tearDown` from `setup_class`, `teardown_class`, `setup_method`, and
    `teardown_method`, respectively, and issue a deprecation warning in doing so. You should migrate to the standard
    PyTest form of these methods if you wish to use this class. This class also provides :meth:`addCleanup`, which
    behaves the same as the same-named method in `unittest` and also issues a deprecation warning. All of these
    polyfills will be removed in PySOA 2.0.

    This class also provides polyfills for `unittest`-like `self.assert*` and `self.fail*` methods. There is currently
    no plan to deprecate and remove this, but that may happen by PySOA 2.0, and you should endeavor to adopt standard
    `assert`-style assertions, as they provide better failure output in PyTest results.
    """
    @classmethod
    def setUpClass(cls):  # type: () -> None
        """
        Deprecated, to be removed in PySOA 2.0. Override :meth:`setup_class`, instead, and be sure to still call
        `super().setup_class()`.
        """

    @classmethod
    def setup_class(cls):  # type: () -> None
        # noinspection PyUnresolvedReferences
        if cls.setUpClass.__func__ is not PyTestServerTestCase.setUpClass.__func__:  # type: ignore
            warn(
                '`ServerTestCase.setUpClass` is deprecated. `ServerTestCase` no longer inherits from '
                '`unittest.TestCase`. Your test setup has been run, but you should change the `setUpClass` method name '
                'to `setup_class` and be sure to still call `super` within it. This will be removed in PySOA 2.0.',
                DeprecationWarning,
            )
            cls.setUpClass()

    @classmethod
    def tearDownClass(cls):  # type: () -> None
        """
        Deprecated, to be removed in PySOA 2.0. Override :meth:`teardown_class`, instead, and be sure to still call
        `super().teardown_class()`.
        """

    @classmethod
    def teardown_class(cls):  # type: () -> None
        # noinspection PyUnresolvedReferences
        if cls.tearDownClass.__func__ is not PyTestServerTestCase.tearDownClass.__func__:  # type: ignore
            warn(
                '`ServerTestCase.tearDownClass` is deprecated. `ServerTestCase` no longer inherits from '
                '`unittest.TestCase`. Your test setup has been run, but you should change the `tearDownClass` method '
                'name to `teardown_class` and be sure to still call `super` within it. This will be removed in PySOA '
                '2.0.',
                DeprecationWarning,
            )
            cls.tearDownClass()

    def setUp(self):  # type: () -> None
        """
        Deprecated, to be removed in PySOA 2.0. Override :meth:`setup_method`, instead, and be sure to still call
        `super().setup_method()`.
        """

    def setup_method(self):  # type: () -> None
        self._cleanups = []  # type: List[Tuple[Callable, Tuple[Any, ...], Dict[str, Any]]]

        self.setup_pysoa()

        if _methods_are_not_same(self.__class__.setUp, PyTestServerTestCase.setUp):
            warn(
                '`ServerTestCase.setUp` is deprecated. `ServerTestCase` no longer inherits from `unittest.TestCase`. '
                'Your test setup has been run, but you should change the `setUp` method name to `setup_method` and '
                'be sure to still call `super` within it. This will be removed in PySOA 2.0.',
                DeprecationWarning,
            )
            self.setUp()

    def tearDown(self):  # type: () -> None
        """
        Deprecated, to be removed in PySOA 2.0. Override :meth:`teardown_method`, instead, and be sure to still call
        `super().teardown_method()`.
        """

    def teardown_method(self):  # type: () -> None
        if _methods_are_not_same(self.__class__.tearDown, PyTestServerTestCase.tearDown):
            warn(
                '`ServerTestCase.tearDown` is deprecated. `ServerTestCase` no longer inherits from '
                '`unittest.TestCase`. Your test setup has been run, but you should change the `tearDown` method name '
                'to `teardown_method` and be sure to still call `super` within it. This will be removed in PySOA 2.0.',
                DeprecationWarning,
            )
            self.tearDown()

        self.doCleanups()

    def addCleanup(self, function, *args, **kwargs):
        # type: (Callable, *Any, **Any) -> None
        """
        Deprecated, to be removed in PySOA 2.0.
        """
        warn(
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

    # noinspection PyTypeChecker
    def fail(self, msg=None):
        # type: (Optional[object]) -> NoReturn
        if msg:
            raise AssertionError(msg)
        raise AssertionError()

    def assertEqual(self, first, second, msg=None):
        # type: (Any, Any, Optional[object]) -> None
        assert first == second, msg or ''

    def assertNotEqual(self, first, second, msg=None):
        # type: (Any, Any, Optional[object]) -> None
        assert first != second, msg or ''

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
        # type: (Union[Iterable], Union[Iterable], Optional[object]) -> None
        warn(
            'PyTestServerTestCase.assertCountEqual is deprecated, because it cannot be implemented practicably. '
            'There is no replacement. It will be removed in PySOA 2.0',
            DeprecationWarning,
        )
        first_list, second_list = list(first), list(second)
        try:
            first_counter = collections.Counter(first_list)
            second_counter = collections.Counter(second_list)
        except TypeError:
            assert _count_diff_all_purpose(first_list, second_list) == []
        else:
            assert first_counter == second_counter, msg or ''
            assert _count_diff_hashable(first_list, second_list) == []

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

    def assertTrue(self, expr, msg=None):
        # type: (Any, Optional[object]) -> None
        assert expr, msg or ''

    def assertFalse(self, expr, msg=None):
        # type: (Any, Optional[object]) -> None
        assert not expr, msg or ''

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
        assert regex is not None, 'Regex must not be None'  # do this first to prevent a warning
        assert regex, 'Regex must not be empty'
        if isinstance(regex, _string_types):
            regex = re.compile(regex)
        assert regex.search(text) is not None, (  # type: ignore
            msg or 'Pattern: {}\nDoes not match text: {!r}'.format(regex.pattern, text)  # type: ignore
        )

    def assertNotRegex(self, text, regex, msg=None):
        # type: (_S, Union[Pattern[_S], _S], Optional[object]) -> None
        assert regex is not None, 'Regex must not be None'  # do this first to prevent a warning
        assert regex, 'Regex must not be empty'
        if isinstance(regex, _string_types):
            regex = re.compile(regex)
        assert regex.search(text) is None, (  # type: ignore
            msg or 'Pattern: {}\nUnexpectedly matches text: {!r}'.format(regex.pattern, text)  # type: ignore
        )

    # noinspection PyShadowingBuiltins
    def assertRaises(self, exception, callable=None, *args, **kwargs):
        if callable:
            with pytest.raises(exception) as exc_info:
                callable(*args, **kwargs)
            return
        # Create a wrapper that provides the same interface as unittest's assertRaises
        class _UnittestRaisesContext:
            def __init__(self, exception_type):
                self.exception_type = exception_type
                self.exception = None
                
            def __enter__(self):
                return self
                
            def __exit__(self, exc_type, exc_value, traceback):
                if exc_type is None:
                    raise AssertionError(f"{self.exception_type.__name__} not raised")
                if not issubclass(exc_type, self.exception_type):
                    raise exc_value
                self.exception = exc_value
                return True
        
        return _UnittestRaisesContext(exception)

    # noinspection PyShadowingBuiltins
    def assertRaisesRegex(self, exception, regex, callable=None, *args, **kwargs):
        if callable:
            # Ensure regex is str or Pattern[str]
            if isinstance(regex, bytes):
                regex = regex.decode()
            with pytest.raises(exception, match=regex):
                callable(*args, **kwargs)
            return
        # Create a wrapper that provides the same interface as unittest's assertRaisesRegex
        class _UnittestRaisesRegexContext:
            def __init__(self, exception_type, regex):
                self.exception_type = exception_type
                self.regex = regex
                self.exception = None
                
            def __enter__(self):
                return self
                
            def __exit__(self, exc_type, exc_value, traceback):
                if exc_type is None:
                    raise AssertionError(f"{self.exception_type.__name__} not raised")
                if not issubclass(exc_type, self.exception_type):
                    raise exc_value
                # Check if the exception message matches the regex
                import re
                if not re.search(self.regex, str(exc_value)):
                    raise AssertionError(f"'{self.regex}' does not match '{str(exc_value)}'")
                self.exception = exc_value
                return True
        
        if isinstance(regex, bytes):
            regex = regex.decode()
        return _UnittestRaisesRegexContext(exception, regex)

    def assertWarns(self, exception, callable=None, *args, **kwargs):
        if callable:
            with pytest.warns(exception):
                callable(*args, **kwargs)
            return
        # Return pytest's warning context manager directly
        return pytest.warns(exception)

    # noinspection PyShadowingBuiltins
    def assertWarnsRegex(self, exception, regex, callable=None, *args, **kwargs):
        if callable:
            if isinstance(regex, bytes):
                regex = regex.decode()
            with pytest.warns(exception, match=regex):
                callable(*args, **kwargs)
            return
        # Return pytest's warning context manager directly
        if isinstance(regex, bytes):
            regex = regex.decode()
        return pytest.warns(exception, match=regex)

    def assertLogs(
        self,
        logger=None,  # type: Union[six.text_type, six.binary_type, logging.Logger, None]
        level=None,  # type: Union[six.text_type, six.binary_type, int, None]
    ):
        # type: (...) -> _AssertLogsContext
        return _AssertLogsContext(logger, level)

    # Deprecated unittest assertion methods for legacy test compatibility
    # TODO: Remove these methods in the future when all tests are modernized
    def assertEquals(self, a, b, msg=None):
        """Deprecated. Use assertEqual instead."""
        warn('assertEquals is deprecated, use assertEqual', DeprecationWarning, stacklevel=2)
        return self.assertEqual(a, b, msg)

    def failUnlessEqual(self, a, b, msg=None):
        """Deprecated. Use assertEqual instead."""
        warn('failUnlessEqual is deprecated, use assertEqual', DeprecationWarning, stacklevel=2)
        return self.assertEqual(a, b, msg)

    def assertNotEquals(self, a, b, msg=None):
        """Deprecated. Use assertNotEqual instead."""
        warn('assertNotEquals is deprecated, use assertNotEqual', DeprecationWarning, stacklevel=2)
        return self.assertNotEqual(a, b, msg)

    def failIfEqual(self, a, b, msg=None):
        """Deprecated. Use assertNotEqual instead."""
        warn('failIfEqual is deprecated, use assertNotEqual', DeprecationWarning, stacklevel=2)
        return self.assertNotEqual(a, b, msg)

    def assertAlmostEquals(self, a, b, places=None, msg=None):
        """Deprecated. Use assertAlmostEqual instead."""
        warn('assertAlmostEquals is deprecated, use assertAlmostEqual', DeprecationWarning, stacklevel=2)
        return self.assertAlmostEqual(a, b, places=places, msg=msg)

    def failUnlessAlmostEqual(self, a, b, places=None, msg=None):
        """Deprecated. Use assertAlmostEqual instead."""
        warn('failUnlessAlmostEqual is deprecated, use assertAlmostEqual', DeprecationWarning, stacklevel=2)
        return self.assertAlmostEqual(a, b, places=places, msg=msg)

    def assertNotAlmostEquals(self, a, b, places=None, msg=None):
        """Deprecated. Use assertNotAlmostEqual instead."""
        warn('assertNotAlmostEquals is deprecated, use assertNotAlmostEqual', DeprecationWarning, stacklevel=2)
        return self.assertNotAlmostEqual(a, b, places=places, msg=msg)

    def failIfAlmostEqual(self, a, b, places=None, msg=None):
        """Deprecated. Use assertNotAlmostEqual instead."""
        warn('failIfAlmostEqual is deprecated, use assertNotAlmostEqual', DeprecationWarning, stacklevel=2)
        return self.assertNotAlmostEqual(a, b, places=places, msg=msg)

    def failUnless(self, expr, msg=None):
        """Deprecated. Use assertTrue instead."""
        warn('failUnless is deprecated, use assertTrue', DeprecationWarning, stacklevel=2)
        return self.assertTrue(expr, msg)

    def failIf(self, expr, msg=None):
        """Deprecated. Use assertFalse instead."""
        warn('failIf is deprecated, use assertFalse', DeprecationWarning, stacklevel=2)
        return self.assertFalse(expr, msg)

    def assert_(self, expr, msg=None):
        """Deprecated. Use assertTrue instead."""
        warn('assert_ is deprecated, use assertTrue', DeprecationWarning, stacklevel=2)
        return self.assertTrue(expr, msg)

    def assertRegexpMatches(self, text, regex, msg=None):
        """Deprecated. Use assertRegex instead."""
        warn('assertRegexpMatches is deprecated, use assertRegex', DeprecationWarning, stacklevel=2)
        return self.assertRegex(text, regex, msg)

    def assertNotRegexpMatches(self, text, regex, msg=None):
        """Deprecated. Use assertNotRegex instead."""
        warn('assertNotRegexpMatches is deprecated, use assertNotRegex', DeprecationWarning, stacklevel=2)
        return self.assertNotRegex(text, regex, msg)

    def failUnlessRaises(self, excClass, callableObj=None, *args, **kwargs):
        """Deprecated. Use assertRaises instead."""
        warn('failUnlessRaises is deprecated, use assertRaises', DeprecationWarning, stacklevel=2)
        return self.assertRaises(excClass, callableObj, *args, **kwargs)


_LoggingWatcher = NamedTuple('_LoggingWatcher', (
    ('records', List[logging.LogRecord]),
    ('output', List[six.text_type]),
))


class _CapturingHandler(logging.Handler):
    def __init__(self):
        super(_CapturingHandler, self).__init__()
        self.watcher = _LoggingWatcher([], [])

    def flush(self):
        """Does nothing"""

    def emit(self, record):
        self.watcher.records.append(record)
        self.watcher.output.append(self.format(record))


class _AssertLogsContext(object):
    LOGGING_FORMAT = '%(levelname)s:%(name)s:%(message)s'

    def __init__(
        self,
        logger,  # type: Union[six.text_type, six.binary_type, logging.Logger, None]
        level,  # type: Union[six.text_type, six.binary_type, int, None]
    ):
        if isinstance(logger, logging.Logger):
            self.logger = logger
            self.logger_name = logger.name  # type: Union[six.text_type, six.binary_type, None]
        else:
            # noinspection PyTypeChecker
            self.logger = logging.getLogger(logger)  # type: ignore
            self.logger_name = logger

        if level:
            if isinstance(level, int):
                self.level = level
            else:
                if six.PY2:
                    # noinspection PyProtectedMember,PyUnresolvedReferences
                    self.level = logging._levelNames[level]  # type: ignore
                else:
                    # noinspection PyProtectedMember
                    self.level = logging._nameToLevel[level]  # type: ignore
        else:
            self.level = logging.INFO

    def __enter__(self):  # type: () -> _LoggingWatcher
        formatter = logging.Formatter(self.LOGGING_FORMAT)
        handler = _CapturingHandler()
        handler.setFormatter(formatter)
        self.watcher = handler.watcher

        self._old_handlers = self.logger.handlers[:]
        self._old_level = self.logger.level
        self._old_propagate = self.logger.propagate
        self.logger.handlers = [handler]
        self.logger.setLevel(self.level)
        self.logger.propagate = False

        return handler.watcher

    def __exit__(self, exc_type, exc_value, tb):  # type: (Any, Any, Any) -> Literal[False]
        self.logger.handlers = self._old_handlers
        self.logger.setLevel(self._old_level)
        self.logger.propagate = self._old_propagate

        if exc_type is not None or len(self.watcher.records) > 0:
            # let unexpected exceptions pass through
            # noinspection PyTypeChecker
            return False

        raise AssertionError('No logs of level {} or higher triggered on {}'.format(  # type: ignore
            logging.getLevelName(self.level),
            self.logger_name,
        ))


ServerTestCase = PyTestServerTestCase
