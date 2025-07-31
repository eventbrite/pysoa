import six
from functools import wraps
import re
from typing import List, Any, Callable, TypeVar
ReturnType = TypeVar('ReturnType')
import warnings

from _pytest import fixtures
from _pytest._code.code import TracebackEntry
from _pytest._code.source import Source
from _pytest.mark import MARK_GEN
import py
import pytest

from pysoa.test.compatibility import mock
from pysoa.test.plan import (
    FixtureTestCaseData,
    ServicePlanTestCase,
)
from pysoa.test.plan.errors import StatusError


try:
    from _pytest.warning_types import PytestCollectionWarning
except ImportError:
    PytestCollectionWarning = None  # type: ignore

try:
    import pyparsing
    TEST_PLANS_ENABLED = True
except ImportError:
    pyparsing = None  # type: ignore
    TEST_PLANS_ENABLED = False


__test_plan_prune_traceback = True  # ensure code in this file is not included in failure stack traces


def _get_unpacked_marks(obj):
    """
    Copied/modified from _pytest.mark.structures, which is not available on all platforms
    """
    # noinspection SpellCheckingInspection
    mark_list = getattr(obj, 'pytestmark', [])
    if not isinstance(mark_list, list):
        mark_list = [mark_list]
    return (getattr(mark, 'mark', mark) for mark in mark_list)


# PLUGIN_STATISTICS is used to track the number of collected, executed, and skipped fixture tests for plugin stats tests.
# This is legacy logic for plugin statistics tests and may be refactored in the future.
PLUGIN_STATISTICS = {
    'fixture_tests_collected': 0,
    'fixture_tests_executed': 0,
    'fixture_tests_skipped': 0,
}


def pytest_addoption(parser):
    """
    A hook called by the PyTest plugin system to add configuration options before the command line arguments are parsed
    We use this to add all of the ``--pysoa-*`` command line options.

    :param parser: The PyTest wrapper around the ``argparse`` library parser
    """
    if not TEST_PLANS_ENABLED:
        return

    group = parser.getgroup('pysoa', 'pysoa test plans')
    group.addoption(
        '--pysoa-fixture',
        action='append',
        dest='pysoa_fixture',
        metavar='fixture',
        default=[],
        help='Only run tests in this fixture filename (multiple uses allowed)',
    )
    group.addoption(
        '--pysoa-test-case',
        action='append',
        dest='pysoa_test_case',
        metavar='plan',
        default=[],
        help='Only run the test case or cases with this name or description (multiple uses allowed); matches tests in '
             'any fixture (unless --pysoa-fixture); mutually exclusive with --pysoa-test-case-regex',
    )
    group.addoption(
        '--pysoa-test-case-regex',
        action='append',
        dest='pysoa_test_case_regex',
        metavar='pattern',
        default=None,
        type=lambda pattern: None if not pattern else re.compile('^{}'.format(pattern)),
        help='Only run the test case or cases whose name or description matches this pattern (multiple uses allowed); '
             'matches tests in any fixture (unless --pysoa-fixture); mutually exclusive with --pysoa-test-case',
    )
    group.addoption(
        '--pysoa-disable-tb-prune',
        action='store_true',
        dest='pysoa_disable_tb_prune',
        default=False,
        help='By default, traceback frames containing PySOA test plan parsing and execution code are pruned from the '
             'error report before display, giving you a less cluttered view when errors occur. This behavior can make '
             'it difficult to track down bugs in the PySOA test plan code itself. Setting this option disables this '
             'pruning, giving you the full stacktrace.',
    )

    # noinspection PyProtectedMember
    parser_class = type(parser._getparser())
    original_parse_args = parser_class.parse_args

    @wraps(parser_class.parse_args)
    def parse_args(self, args=None, namespace=None):
        # Parse wrapper to raise error for mutually-exclusive arguments at the correct time
        args = original_parse_args(self, args=args, namespace=namespace)
        if args.pysoa_test_case and args.pysoa_test_case_regex:
            self.error('use of mutually exclusive arguments: --pysoa-test-case, --pysoa-test-case-regex')
        return args
    parser_class.parse_args = parse_args


# noinspection SpellCheckingInspection
def pytest_pycollect_makeitem(collector, name, obj):
    """
    A hook called by the PyTest main collector when collecting test plans. We use this to find all classes extending
    ``ServicePlanTestCase`` and return new, custom collector objects for them.

    :param collector: The main collector, which must be the parent of any collector object returned
    :type collector: PyCollector
    :param name: The name of the item to potentially be collected
    :type name: str
    :param obj: The item to potentially be collected

    :return: A new collector object, or ``None`` if this plugin does not recognize the item type, in which case the
             collector system will call the next available plugin or hook to do the same.
    :rtype: PyCollector
    """
    if not TEST_PLANS_ENABLED:
        return

    if not isinstance(obj, type):
        return

    try:
        if not issubclass(obj, ServicePlanTestCase):
            return
        if obj == ServicePlanTestCase:
            # Don't collect the parent class
            return IgnoreBaseServicePlanTestCaseClassCollector.from_parent(parent=collector, name=name)
    except TypeError:
        return

    return ServicePlanTestClassCollector.from_parent(parent=collector, name=name)


class IgnoreBaseServicePlanTestCaseClassCollector(pytest.Class):
    @classmethod
    def from_parent(cls, parent, **kwargs):
        return super().from_parent(parent=parent, **kwargs)
    def collect(self):
        return []


def has_init(obj):
    init = getattr(obj, '__init__', None)
    if init:
        return init != object.__init__


def has_new(obj):
    new = getattr(obj, '__new__', None)
    if new:
        return new != object.__new__


class ServicePlanTestClassCollector(pytest.Class):
    """
    A specialized collector for collecting PySOA test plans and all of their fixtures and test cases. It yields all of
    the test cases that its parent collects (normal ``test_`` methods in ``unittest`` fashion), and then yields all of
    test fixture tests defined by the class extending ``ServicePlanTestCase``.
    """
    @classmethod
    def from_parent(cls, parent, **kwargs):
        return super().from_parent(parent=parent, **kwargs)
    def collect(self):
        """
        Responsible for collecting all the items (tests, in this case traditional test methods and fixture test cases)
        in this item (a ``ServicePlanTestCase`` class). Copied from (but adapted to use the extended instance
        collector) https://github.com/pytest-dev/pytest/blob/5.2.2/src/_pytest/python.py#L687-L712.
        """
        if not getattr(self.obj, '__test__', True):
            return

        if has_init(self.obj):
            warning = (
                'Cannot collect test class %r because it has a __init__ constructor (from: %s)' %
                (self.obj.__name__, self.parent.nodeid if self.parent is not None else 'unknown')
            )
            # Use explicit bool() check for PytestCollectionWarning
            if PytestCollectionWarning is not None:
                self.warn(PytestCollectionWarning(warning))
            else:
                warnings.warn(UserWarning(warning))
            return []
        elif has_new(self.obj):
            warning = (
                'Cannot collect test class %r because it has a __new__ constructor (from: %s)' %
                (self.obj.__name__, self.parent.nodeid if self.parent is not None else 'unknown')
            )
            # Use explicit bool() check for PytestCollectionWarning
            if PytestCollectionWarning is not None:
                self.warn(PytestCollectionWarning(warning))
            else:
                warnings.warn(UserWarning(warning))
            return []

        # Check if this class is skipped
        class_skipped = False
        for mark in _get_unpacked_marks(self.obj):
            if mark.name == 'skip' or (mark.name == 'skipif' and mark.args and mark.args[0]):
                class_skipped = True
                break

        self._inject_setup_class_fixture()
        self._inject_setup_method_fixture()
        # Collect normal test methods
        collected = list(super().collect() or [])
        # Collect fixture test cases
        for test_data in self.obj.get_fixture_test_information():
            test_name = f"plan__{test_data.fixture_name}__{test_data.name}"
            test_data.callable.__doc__ = test_data.description
            setattr(self.obj, test_name, test_data.callable)
            collected.append(ServicePlanTestCaseTestFunction.from_parent(parent=self, name=test_name, fixture_test_case_data=test_data))
            PLUGIN_STATISTICS['fixture_tests_collected'] += 1
        return collected


class ServicePlanTestCaseTestFunction(pytest.Function):
    """
    A test item that PyTest executes. Largely behaves like a traditional ``unittest` test method, but overrides some
    behavior to ensure the following:

    - That the specialized testing code is run, and that the test fixture name and path are included in result output
    - That test skips are handled properly
    - That unhelpful stacktrace elements from this test plan code are pruned from result output
    - That helpful information is displayed with test failures
    """
    @classmethod
    def from_parent(cls, parent, **kwargs):
        return super().from_parent(parent=parent, **kwargs)
    def __init__(self, *args, fixture_test_case_data=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fixture_test_case_data = fixture_test_case_data
        # Add a type check before accessing .obj on Node | None
        if self.parent is not None and hasattr(self.parent, 'obj'):
            cls = self.parent.obj
            test_name = self.name
            # Only check for actual test methods, not just any attribute
            if hasattr(cls, test_name) and callable(getattr(cls, test_name, None)):
                # Check if it's actually a test method (starts with 'test_')
                if test_name.startswith('test_'):
                    raise StatusError('Duplicate test name "{name}" in fixture "{fixture}"'.format(
                        name=fixture_test_case_data.name,
                        fixture=fixture_test_case_data.fixture_file),
                    )
        skipped = False
        if self.parent is not None and hasattr(self.parent, 'obj'):
            for mark in _get_unpacked_marks(self.parent.obj):
                mark_copy = getattr(MARK_GEN, mark.name)(*mark.args, **mark.kwargs)
                self.add_marker(mark_copy)

                if mark.name == 'skip' or (mark.name == 'skipif' and mark.args and mark.args[0]):
                    skipped = True

        if not skipped and fixture_test_case_data.skip:
            self.add_marker(pytest.mark.skip(reason=fixture_test_case_data.skip))
            skipped = True

        # Track skipped fixture tests for plugin statistics
        if skipped and fixture_test_case_data:
            PLUGIN_STATISTICS['fixture_tests_skipped'] += 1

    def setup(self) -> None:
        super().setup()

        # Ensure setup_class is called for the test class if it hasn't been called yet
        if self.parent is not None and hasattr(self.parent, 'obj'):
            test_class = self.parent.obj
            if not hasattr(test_class, '_setup_class_called'):
                test_class.setup_class()
                setattr(test_class, '_setup_class_called', True)

        if self.fixture_test_case_data.is_first_fixture_case:
            # Add a type check before accessing .obj on Node | None
            if self.parent is not None and hasattr(self.parent, 'obj'):
                setattr(self.parent.obj, '_pytest_first_fixture_case', self.fixture_test_case_data)

        if self.fixture_test_case_data.is_last_fixture_case:
            # Add a type check before accessing .obj on Node | None
            if self.parent is not None and hasattr(self.parent, 'obj'):
                setattr(self.parent.obj, '_pytest_last_fixture_case', self.fixture_test_case_data)

        # Removed call to fixtures.fillfixtures(self) as it is no longer available in pytest 7+.
        # Rely on pytest's public fixture injection and request.getfixturevalue if needed.

    # noinspection SpellCheckingInspection
    def runtest(self):
        """
        PyTest calls this to actually run the test.
        """
        PLUGIN_STATISTICS['fixture_tests_executed'] += 1
        super().runtest()

    def teardown(self) -> None:
        """
        PyTest calls this to clean up after the test.
        """
        super().teardown()


# noinspection SpellCheckingInspection
class ServicePlanFixtureTestTracebackEntry(TracebackEntry):
    """
    A special traceback entry for displaying the relevant test fixture file contents instead of Python code when a
    fixture test case fails.
    """
    def __init__(
        self,
        name,
        line_number,
        path,
        local_variables,
        fixture_source,
        test_source,
        raw_entry,
    ):
        super().__init__(raw_entry)

        self._name = name
        self._lineno = line_number - 1
        self._path = path
        self._locals = local_variables
        self._fixture_source = Source(fixture_source)
        self._test_source = test_source

        self._frame = mock.Mock(spec=object)
        self._frame.statement = self.statement
        self._frame.getargs = lambda *_, **__: list(six.iteritems(local_variables))
        self._frame.f_locals = local_variables
        self._frame.code = mock.Mock(spec=object)
        self._frame.code.path = path
        self._frame.code.raw = mock.Mock(spec=object)
        self._frame.code.raw.co_filename = str(path)

    @property
    def frame(self):
        return self._frame

    @property
    def lineno(self):
        return self._lineno

    @property
    def statement(self):
        return self._fixture_source[self.lineno]

    @property
    def path(self):
        return self._path

    def getlocals(self):
        return self._locals
    locals = property(getlocals, None, None, str('locals of underlying frame'))

    def getfirstlinesource(self):
        return max(self.lineno - 3, 0)

    def getsource(self, astcache=None):
        start = self.getfirstlinesource()
        end = start + len(self._test_source) + 5
        return self._fixture_source[start:end]
    source = property(getsource, None, None, str('source code of failing test'))

    def ishidden(self, excinfo=None):
        return False

    def getname(self):
        return self._name
    name = property(getname, None, None, str('name of underlaying code'))

    def __str__(self):
        return '  File {path} line {line_number} (approximate) in {test}\n  {source}\n'.format(
            path=self.path,
            line_number=self.lineno + 1,
            test=self.name,
            source=self._test_source,
        )

    def __repr__(self):
        return '<TracebackEntry {}:{}>'.format(self.path, self.lineno + 1)


def pytest_collection_modifyitems(config, items):
    """
    A hook called by the PyTest main collector immediately after collecting test plans. We use this to "deselect"
    test cases that do not match the supplied ``--pysoa-*`` filter command line arguments.

    :param config: The PyTest config object
    :param items: The list of collected test items, which includes all tests (regular tests collected by PyTest and
                  other plugins as well as fixture test cases). Any modifications must happen against this argument
                  directly (a new array can't be created and returned).
    """
    if not TEST_PLANS_ENABLED:
        return

    reporter = None
    # noinspection PyBroadException
    try:
        reporter = config.pluginmanager.get_plugin('terminalreporter')
    except Exception:
        pass

    soa_test_case = config.getoption('pysoa_test_case')
    soa_test_case_regex = config.getoption('pysoa_test_case_regex')
    soa_fixture = config.getoption('pysoa_fixture')

    deselected = []
    remaining = []

    for test in items:
        if soa_test_case or soa_test_case_regex or soa_fixture:
            if not isinstance(test, ServicePlanTestCaseTestFunction):
                # At least one of the plugin filtering arguments were specified, but this is not a service plan test
                deselected.append(test)
            else:
                test_data = test.fixture_test_case_data
                if (
                    # The fixture argument(s) was specified, but the fixture name does not match the argument(s)
                    (soa_fixture and test_data.fixture_name not in soa_fixture) or
                    # The test case argument(s) was specified, but the test name does not match the argument(s)
                    (
                        soa_test_case and
                        test_data.name not in soa_test_case and
                        test_data.description not in soa_test_case
                    ) or
                    # The test regex argument(s) was specified, but the test name does not match the argument pattern(s)
                    (soa_test_case_regex and not any(
                        p.match(test_data.name) or p.match(test_data.description) for p in soa_test_case_regex
                    ))
                ):
                    deselected.append(test)
                else:
                    remaining.append(test)

    if deselected:
        config.hook.pytest_deselected(items=deselected)
        if reporter:
            reporter.report_collect()
        items[:] = remaining


def pytest_runtest_logreport(report):
    # This hook increments the skipped count for plugin statistics when a fixture test is skipped.
    if report.when == 'call' and report.skipped:
        # Check if this is a fixture test that was skipped
        if hasattr(report, 'nodeid') and 'plan__' in report.nodeid:
            PLUGIN_STATISTICS['fixture_tests_skipped'] += 1


# Remove or replace the invalid some_function using ReturnType
