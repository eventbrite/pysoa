from __future__ import (
    absolute_import,
    unicode_literals,
)

from functools import wraps
import re
import sys
from unittest import SkipTest

from _pytest._code.code import TracebackEntry
from _pytest._code.source import Source
from _pytest.mark import MARK_GEN
from _pytest.unittest import (
    TestCaseFunction,
    UnitTestCase,
)
import py
import six


try:
    import pyparsing
    TEST_PLANS_ENABLED = True
except ImportError:
    pyparsing = None
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

    # Lazy importing ensures that pytest-cov loads up coverage before this plugin loads other classes in PySOA
    from pysoa.test.plan import ServicePlanTestCase

    try:
        if not issubclass(obj, ServicePlanTestCase):
            return
        if obj == ServicePlanTestCase:
            # Don't collect the parent class
            return
    except TypeError:
        return

    return ServicePlanTestCaseCollector(name, parent=collector)


class ServicePlanTestCaseCollector(UnitTestCase):
    """
    A specialized collector for collecting PySOA test plans and all of their fixtures and test cases. It yields all of
    the test cases that its parent collects (normal ``test_`` methods in ``unittest`` fashion), and then yields all of
    test fixture tests defined by the class extending ``ServicePlanTestCase``.
    """
    def collect(self):
        """
        Responsible for collecting all the items (tests, in this case traditional test methods and fixture test cases)
        in this item (a ``ServicePlanTestCase`` class).
        :return:
        """
        if not getattr(self.obj, '__test__', True):
            # Super performs this check, too, but if we yield that return, things get screwy, so we have to duplicate
            # the check first to be sure.
            return

        for item in super(ServicePlanTestCaseCollector, self).collect():
            # We let super collect normal (``unittest``) test methods, and yield each of those as it collects them,
            # just as super does. After this, we can collect the fixtures and fixture tests.
            yield item

        for test_data in self.obj.get_fixture_test_information():
            # Now we collect and field the fixture tests.
            yield ServicePlanTestCaseTestFunction(parent=self, fixture_test_case_data=test_data)
            PLUGIN_STATISTICS['fixture_tests_collected'] += 1


class ServicePlanTestCaseTestFunction(TestCaseFunction):
    """
    A test item that PyTest executes. Largely behaves like a traditional ``unittest` test method, but overrides some
    behavior to ensure the following:

    - That the specialized testing code is run, and that the test fixture name and path are included in result output
    - That test skips are handled properly
    - That unhelpful stacktrace elements from this test plan code are pruned from result output
    - That helpful information is displayed with test failures
    """

    def __init__(self, parent, fixture_test_case_data):
        """
        Construct a test item.

        :param parent: The parent collector
        :type parent: ServicePlanTestCaseCollector
        :param fixture_test_case_data: The test case data
        :type fixture_test_case_data: FixtureTestCaseData
        """
        test_name = 'test__{fixture}__{test}'.format(
            fixture=fixture_test_case_data.fixture_name,
            test=fixture_test_case_data.name,
        )

        # First, we have to give the test plan test case class a method with this name, otherwise the TestCase class
        # cannot be instantiated. However, this should never be called, because the plugin overrides it.
        def fake_test(*_, **__):
            raise TypeError('The incorrect test method was called')

        fake_test.__doc__ = fixture_test_case_data.description
        if hasattr(parent.obj, test_name):
            # Lazy importing ensures that pytest-cov loads up coverage before this plugin loads other classes in PySOA
            from pysoa.test.plan.errors import StatusError
            raise StatusError('Duplicate test name "{name}" in fixture "{fixture}"'.format(
                name=fixture_test_case_data.name,
                fixture=fixture_test_case_data.fixture_file),
            )
        setattr(parent.obj, test_name, fake_test)

        # Next we call super
        super(ServicePlanTestCaseTestFunction, self).__init__(name=test_name, parent=parent)

        # Finally, we do some magic to trick PyTest into accepting and displaying the actual location of the test (the
        # fixture file and the line in that file) instead of the PySOA test plan parsing code.
        self._location = (
            self.session.fspath.bestrelpath(py.path.local(fixture_test_case_data.fixture_file)),
            fixture_test_case_data.line_number,
            self.location[2],
        )
        self.fspath = py.path.local(fixture_test_case_data.fixture_file)
        self._nodeid = '::'.join(
            self.nodeid.split('::', 2)[:2] + [fixture_test_case_data.fixture_name, fixture_test_case_data.name],
        )

        self.fixture_test_case_data = fixture_test_case_data

        # Copy any class-level PyTest markers from the ServicePlanTestCase class to each fixture test case
        # This allows things like pytest.mark.skip[if], pytest.mark.django_db, etc. to work
        for mark in _get_unpacked_marks(parent.obj):
            mark_copy = getattr(MARK_GEN, mark.name)(*mark.args, **mark.kwargs)
            self.add_marker(mark_copy)

            if mark.name == 'skip' or (mark.name == 'skipif' and mark.args and mark.args[0]):
                PLUGIN_STATISTICS['fixture_tests_skipped'] += 1

    # noinspection SpellCheckingInspection
    def runtest(self):
        """
        PyTest calls this to actually run the test.
        """
        if self.config.pluginmanager.get_plugin('pdbinvoke') is None:
            self._run(result=self)
        else:
            self._debug()

    def _handle_skip(self):
        """
        Implements the skipping machinery (see super). It's a modified version of super and ``unittest:TestCase.run``
        that makes the following changes:
        - Handles test fixture skip directives
        - Properly handles class-level ``pytest.mark.skip[if]`` markers to make them apply to all fixture test cases
        - Properly handles the changing signature of ``_addSkip`` (super incorrectly analyzes the Python version)

        :return: ``True`` if this test is to be skipped, ``False`` if it is to be run.
        :rtype: bool
        """
        # implements the skipping machinery (see super); analog to pythons Lib/unittest/case.py:run
        cls = self._testcase.__class__

        skipped = False
        skipped_why = 'unknown'
        if getattr(cls, '__unittest_skip__', False):
            skipped = True
            skipped_why = getattr(cls, '__unittest_skip_why__', '')
        elif self.fixture_test_case_data.skip:
            skipped = True
            skipped_why = self.fixture_test_case_data.skip

        if skipped:
            # If the class or fixture or fixture test case was skipped
            try:
                # noinspection PyProtectedMember
                # This is the signature on Python 3.4+ or unittest2 on Python 3.3-
                self._testcase._addSkip(self, self._testcase, skipped_why)
            except TypeError:
                if sys.version_info >= (3, 4):
                    # If we got this error >= Python 3.4, something is wrong, so re-raise it
                    raise
                # noinspection PyProtectedMember
                self._testcase._addSkip(self, skipped_why)

            PLUGIN_STATISTICS['fixture_tests_skipped'] += 1

            return True

        return False

    # noinspection PyProtectedMember
    def _debug(self):
        """
        Runs the test in debug mode, which starts a debugger as soon as an error happens. Does not run ``setUp`` or
        ``tearDown`` since the code in ``ServicePlanTestCase`` takes care of this. See ``unittest:TestCase.debug``.
        """
        # see unittest.TestCase.debug
        if self._handle_skip():
            return

        self.fixture_test_case_data.callable(self._testcase)
        while self._testcase._cleanups:
            func, args, kwargs = self._testcase._cleanups.pop(-1)
            func(*args, **kwargs)

    # noinspection PyProtectedMember
    def _run(self, result=None):
        """
        Runs the test in normal mode, which adds failures and errors to the result. Does not run ``setUp`` or
        ``tearDown`` since the code in ``ServicePlanTestCase`` takes care of this. See ``unittest:TestCase.run``.

        :param result: The test result so far
        """
        orig_result = result
        if result is None:
            result = self._testcase.defaultTestResult()
            start_test_run = getattr(result, 'startTestRun', None)
            if start_test_run is not None:
                start_test_run()

        self._testcase._resultForDoCleanups = result
        result.startTest(self._testcase)

        if self._handle_skip():
            result.stopTest(self._testcase)
            return

        PLUGIN_STATISTICS['fixture_tests_executed'] += 1

        try:
            success = False
            # noinspection PyBroadException
            try:
                self.fixture_test_case_data.callable(self._testcase)
            except KeyboardInterrupt:
                raise
            except self._testcase.failureException:
                result.addFailure(self._testcase, sys.exc_info())
            except SkipTest as e:
                self._testcase._addSkip(result, str(e))
            except:  # noqa E722
                result.addError(self._testcase, sys.exc_info())
            else:
                success = True

            success = success and self._testcase.doCleanups()
            if success:
                result.addSuccess(self._testcase)
        finally:
            result.stopTest(self._testcase)
            if orig_result is None:
                stop_test_run = getattr(result, 'stopTestRun', None)
                if stop_test_run is not None:
                    stop_test_run()

    # noinspection SpellCheckingInspection
    def _prunetraceback(self, exception_info):
        """
        Prunes unhelpful information from the traceback so that test failure report output isn't overwwhelming and
        still contains useful information. Also appends the specialized fixture test case traceback entry to the end
        of the traceback.

        :param exception_info: The PyTest wrapper around the failure exception info object
        """
        # Before any pruning, get the frame containing _run_test_case so that we can use its locals
        lowest_test_case_frame = next(
            (
                tb for tb in reversed(exception_info.traceback)
                if tb.locals.get('_test_function_frame', False) or tb.locals.get('_run_test_case_frame', False)
            ),
            None,
        )

        super(ServicePlanTestCaseTestFunction, self)._prunetraceback(exception_info)

        if not lowest_test_case_frame:
            return

        if self.config.getoption('pysoa_disable_tb_prune') is not True:
            exception_info.traceback = exception_info.traceback.filter(
                lambda x: not x.frame.f_globals.get('__test_plan_prune_traceback')
            )

        test_case = lowest_test_case_frame.locals['test_case']

        locals_to_copy = {'job_response', 'action_results', 'action_case'}
        if lowest_test_case_frame.locals.get('_test_function_frame', False):
            locals_to_copy = {'test_fixture_results', 'test_case'}

        # noinspection PyProtectedMember
        extra_entry = ServicePlanFixtureTestTracebackEntry(
            name='{cls}::{fixture}::{test}'.format(
                cls=lowest_test_case_frame.locals['self'].__class__.__name__,
                fixture=test_case['fixture_name'],
                test=test_case['name'],
            ),
            line_number=test_case['line_number'],
            path=py.path.local(test_case['fixture_file_name']),
            local_variables={
                k: v for k, v in six.iteritems(lowest_test_case_frame.locals)
                if k in locals_to_copy
            },
            fixture_source=test_case['fixture_source'],
            test_source=test_case['source'],
            raw_entry=lowest_test_case_frame._rawentry,
        )
        exception_info.traceback.append(extra_entry)


# noinspection SpellCheckingInspection
class ServicePlanFixtureTestTracebackEntry(TracebackEntry):
    """
    A special traceback entry for displaying the relevant test fixture file contents instead of Python code when a
    fixture test case fails.
    """
    class Faker(object):
        pass

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
        super(ServicePlanFixtureTestTracebackEntry, self).__init__(raw_entry)

        self._name = name
        self.lineno = line_number - 1
        self._path = path
        self._locals = local_variables
        self._fixture_source = Source(fixture_source)
        self._test_source = test_source

        self._frame = self.Faker()
        self._frame.statement = self.statement
        self._frame.getargs = lambda *_, **__: list(six.iteritems(local_variables))
        self._frame.f_locals = local_variables
        self._frame.code = self.Faker()
        self._frame.code.path = path
        self._frame.code.raw = self.Faker()
        self._frame.code.raw.co_filename = str(path)

    @property
    def frame(self):
        return self._frame

    @property
    def relline(self):
        return self.lineno - self.getfirstlinesource()

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

    def ishidden(self):
        return False

    def name(self):
        return self._name
    name = property(name, None, None, str('name of underlaying code'))

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
