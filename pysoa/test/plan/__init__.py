from __future__ import (
    absolute_import,
    unicode_literals,
)

import abc
import os
import re
import sys

import attr
import six

from pysoa.test.plan import grammar
from pysoa.test.plan.errors import (
    DirectiveError,
    FixtureLoadError,
    StatusError,
)
from pysoa.test.plan.grammar.directive import get_all_directives
from pysoa.test.plan.grammar.tools import substitute_variables
from pysoa.test.plan.parser import ServiceTestPlanFixtureParser
from pysoa.test.server import ServerTestCase
from pysoa.test.stub_service import stub_action


##################################################
# IMPORTANT NOTE
#
# If you alter or add to any of the documentation below, or if you add more grammar directives, you must run
# `docs/update_test_plan_docs.sh` from the root of this project first, to ensure that the latest generated
# documentation makes its way into the `testing.rst` documentation file.
##################################################


__doc__ = """PySOA Test Plans
++++++++++++++++

Another option for testing PySOA services is to use its test plan system. Test plans extend
``pysoa.test.plan:ServicePlanTestCase`` and define a collection of plain text fixture files (with extension ``.pysoa``)
that use a specialized syntax for describing test cases that call actions on your service.

To best understand PySOA test plans and this documentation, you'll need to understand a little bit of nomenclature:

- **Test Plan**: A class that extends ``pysoa.test.plan:ServicePlanTestCase`` and declares a directory in which test
  fixtures can be discovered for that test plan. If you want, you can have a single test plan for all of the test
  fixtures in your service. You can also have multiple test plans, each with one or more fixtures. The advantage of
  using multiple test plans is that each test plan class can have unique setup activities.
- **Test Fixture**: A ``.pysoa`` file containing one or more test cases defined using the PySOA Test Plan syntax. A
  test fixture's name is the test fixture file name absent the ``.pysoa`` extension and any directories.
- **Test Case**: A individual test case within a given test fixture. Each test case must have a name (letters, numbers,
  and underscores, only) and a description (a natural language sentence describing its purpose). A test case must have
  one or more action cases.
- **Action Case**: An individual call to a service action within a test case. Each action case has an associated set of
  inputs used to make the action call and expectations used to assert the results of the action call.


Running Test Plans
******************

PySOA test plans are collected and executed with a PyTest plugin, which is not installed by default. To enable this
plugin, you need to add ``pysoa[pytest]`` to your test requirements. Example:

.. code-block:: python

    tests_require = [
        'pysoa[pytest]',
        ...
    ]

Once you do this and install your testing dependencies, you will be able to run your service's test plans. Without
this, the presence of test plans in your service will result in errors during testing.

By default, all normal tests and test plan tests will run when you invoke ``pytest`` without arguments. If you pass a
directory to ``pytest``, it will run all normal tests and test plan tests in that directory. (NOTE: For the purposes
of directory collection, test plans reside in the test case class that declares them.) You can also easily filter the
tests fixtures and test cases that are run using the ``pytest`` arguments::

    # This will match all fixture AND non-fixture test cases with the name: get_user
    pytest -k get_user
    # This will match only fixture test cases with the name: get_user
    pytest --pysoa-test-case get_user
    # This will match only fixture test cases with names matching the regular expression ^get\\_user.*
    pytest --pysoa-test-case-regex 'get\\_user.*'
    # This will match only test cases within test fixtures with the name: user_actions
    pytest --pysoa-fixture user_actions
    # This will match only test cases named get_user within test fixtures named user_actions
    pytest --pysoa-fixture user_actions --pysoa-test-case get_user

Note that ``--pysoa-test-case`` and ``--pysoa-test-case-regex`` are mutually exclusive arguments. Use ``pytest --help``
to get more information about available plugin arguments.


Creating a Test Plan with ``ServicePlanTestCase``
*************************************************

In order to create test plans, the first thing you need to do is create a test case class that extends
``pysoa.test.plan:ServicePlanTestCase``. This class extends ``ServerTestCase`` (see `Using the ServerTestCase`_),
so you need to define the same ``server_class`` and ``server_settings`` attributes. Additionally, you need to define
either ``fixture_path`` or ``custom_fixtures``. You can also optionally specify ``model_constants``, which is used to
provide stock values for variable substitution (more on that later). Here are two possible examples:

.. code-block:: python

    import os

    from pysoa.test.plan import ServicePlanTestCase

    from user_service.server import Server


    class UserServiceFixtures(ServicePlanTestCase):
        server_class = Server
        server_settings = {}
        fixture_path = os.path.dirname(__file__) + '/service_fixtures'


    class ExtraServiceFixtures(ServicePlanTestCase):
        server_class = Server
        server_settings = {}
        custom_fixtures = (
            os.path.dirname(__file__) + '/extra_fixtures/special_actions_1.pysoa',
            os.path.dirname(__file__) + '/extra_fixtures/special_actions_2.pysoa',
        )
        model_constants = {
            'test_users': [
                {'id': '1838', 'username': 'john.smith'},
                {'id': '1792', 'username': 'jane.sanders'},
            ],
        }


``ServicePlanTestCase`` provides a number of hooks that you can use to set up and tear down plans, fixtures, test
cases, and action cases. To learn more about these hooks, see the docstrings in ``ServicePlanTestCase`` for the
following methods. In each case, if you override the hook, you must call ``super`` as the first line in your hook.

- ``setUpClass``
- ``set_up_test_fixture``
- ``setUp``
- ``set_up_test_case``
- ``set_up_test_case_action``
- ``tear_down_test_case_action``
- ``tear_don_test_case``
- ``tearDown``
- ``tear_down_test_fixture``
- ``tearDownClass``


"""

__doc__ += grammar.__doc__

__doc__ += """Extending Test Plans
********************

You can extend test plan syntax to create your own directives, allowing you to add even more features to your test
plans. The base for all directive behavior is contained in the class ``pysoa.test.plan.grammar.directive:Directive``.
Your directives must extend that class directly or indirectly. Extending the base class directly gives you the ability
to manipulate test case-level and global test case-level behavior. In most cases, you'll want to extend
``pysoa.test.plan.grammar.directive:ActionDirective``, which is the base class for all action case behavior. For more
information about how to use and extend these classes, read their extensive docstrings.

Once you have created one or more new directives, you can register them with the PySOA Test Plan system using one of
the following techniques:

- Call ``pysoa.test.plan.grammar.directive:register_directive`` to register your directive with the test plan system
  manually. However, this requires your code that calls that function to be loaded before the PyTest process starts,
  which can be tricky to achieve.
- Use the Python entry point named ``pysoa.test.plan.grammar.directives`` in your ``setup.py`` file. This is a more
  reliable approach that works in all scenarios. Example:

  .. code-block:: python

      from setuptools import setup

      ...

      setup(
          name='base_service',
          description='A layer on top of PySOA that serves as the base for all of our micro services',
          ...
          entry_points={
              'pysoa.test.plan.grammar.directives': [
                  'auth_token_directive = base_service.test.directives:AuthTokenDirective',
                  'authentication_directive = base_service.test.directives:AuthProcessingDirective',
              ],
          },
          ...
      )

"""


__test_plan_prune_traceback = True  # ensure code in this file is not included in failure stack traces


@attr.s
class FixtureTestCaseData(object):
    """
    A plain-old Python object that holds fixture test case data.
    """
    name = attr.ib()
    description = attr.ib()
    fixture_name = attr.ib()
    fixture_file = attr.ib()
    line_number = attr.ib()
    skip = attr.ib()
    callable = attr.ib()


@six.add_metaclass(abc.ABCMeta)
class ServicePlanTestCase(ServerTestCase):
    """
    Serves as the base class for all test plans. Your test plans must extend this class, and may override any of its
    methods, though, in most cases, you should not need to do this. Most commonly, you may override one of the setup or
    teardown methods in order to bootstrap and clean up dependencies that your tests have.

    Your test case class is not limited to running fixture tests. It may also include normal test case methods whose
    names start with ``test_``, and they will be run normally like any other ``unittest` test methods.
    """

    fixture_path = None
    fixture_regex = re.compile(r'^[^.].*?\.(:?pysoa)$')
    custom_fixtures = ()
    model_constants = {}

    _all_directives = None

    @classmethod
    def setUpClass(cls):
        """
        This method is invoked one time before the test plan (all the fixtures defined in ``fixture_path``) or any of
        the normal tests in your test case are run.
        """
        cls._all_directives = get_all_directives()

        super(ServicePlanTestCase, cls).setUpClass()

    @classmethod
    def tearDownClass(cls):
        """
        This method is invoked one time after the test plan (all the fixtures defined in ``fixture_path``) and any of
        the normal tests in your test case are run. If you override this, your call to `super` must be the very first
        line of code in the method.
        """
        if getattr(cls, '_test_fixture_setup_called', None):
            last_e = None
            for fixture_name, tear_down_not_called in six.iteritems(cls._test_fixture_setup_called):
                # If a -k or --pysoa-test-case filter was used to deselect most tests, the last test in a fixture may
                # not run, in which case the fixture won't be properly torn down. The only way to solve this is to,
                # on class tear-down, check for any not-torn-down fixtures and tear them down. However, this is not
                # the ideal time to tear down a fixture, so we only use this for abnormal tear-downs, not for all
                # fixture tear-downs.
                if tear_down_not_called:
                    self, test_fixture = tear_down_not_called
                    try:
                        self._run_directive_hook('tear_down_test_fixture', test_fixture)
                        self.tear_down_test_fixture(test_fixture)
                    except Exception as e:
                        last_e = e
            if last_e:
                raise last_e

        super(ServicePlanTestCase, cls).tearDownClass()

    def set_up_test_fixture(self, test_fixture, **kwargs):
        """
        This method is invoked once for each fixture file, before any test cases in that fixture file are run.

        :param test_fixture: List of test cases in this fixture
        :type test_fixture: list
        """

    def tear_down_test_fixture(self, test_fixture, **kwargs):
        """
        This method is invoked once for each fixture file, after all test cases in the fixture file have run.

        :param test_fixture: List of test cases in this fixture
        :type test_fixture: list
        """

    def setUp(self):
        """
        This method is invoked once for each test case in a fixture file, before the test is run. It is also run once
        before each ``test_`` method in your test case, if you have any.
        """
        super(ServicePlanTestCase, self).setUp()

    def tearDown(self):
        """
        This method is invoked once for each test case in a fixture file, after the test is run. It is also run once
        after each ``test_`` method in your test case, if you have any.
        """
        super(ServicePlanTestCase, self).tearDown()

    def set_up_test_case(self, test_case, test_fixture, **kwargs):
        """
        This method is invoked immediately after `setUp` and before the test case is run.

        :param test_case: The directive instructions to run and assert this specific test case
        :type test_case: dict
        :param test_fixture: List of test cases in this fixture
        :type test_fixture: list
        """

    def tear_down_test_case(self, test_case, test_fixture, **kwargs):
        """
        This method is invoked immediately before `tearDown` and after the test case is run.

        :param test_case: The directive instructions to run and assert this specific test case
        :type test_case: dict
        :param test_fixture: List of test cases in this fixture
        :type test_fixture: list
        """

    def set_up_test_case_action(self, action_name, action_case, test_case, test_fixture, **kwargs):
        """
        This method is invoked once fear each service action run within a test case, before the action is called.

        :param action_name: The name of the action being run (as described in the test case in the fixture)
        :type action_name: union[str, unicode]
        :param action_case: The directive instructions for running and asserting this specific action
        :type action_case: dict
        :param test_case: The directive instructions to run and assert this specific test case
        :type test_case: dict
        :param test_fixture: List of test cases in this fixture
        :type test_fixture: list
        """

    def tear_down_test_case_action(self, action_name, action_case, test_case, test_fixture, **kwargs):
        """
        This method is invoked once fear each service action run within a test case, before the action is called.

        :param action_name: The name of the action being run (as described in the test case in the fixture)
        :type action_name: union[str, unicode]
        :param action_case: The directive instructions for running and asserting this specific action
        :type action_case: dict
        :param test_case: The directive instructions to run and assert this specific test case
        :type test_case: dict
        :param test_fixture: List of test cases in this fixture
        :type test_fixture: list
        """

    @classmethod
    def get_fixture_test_information(cls):
        """
        Generates fixture test case information used for executing fixture test cases. Acts as a generator that yields
        ``FixtureTestCaseData`` instances, which include the test name, description, fixture name, fixture file name,
        fixture line number on which the test case begins, whether the fixture is skipped and the reason for its being
        skipped, and a callable that can be used to invoke the test.

        Tests are returned in the alphabetical order of the fixture file names and then the order the tests appear
        in the fixture files.

        :return: a generator of fixture test case information.
        :rtype: generator[FixtureTestCaseData]
        """

        for fixture_file_name in cls.get_fixture_file_names():
            fixture_name, _ = os.path.splitext(os.path.basename(fixture_file_name))

            test_fixture_results = []
            last_test_function = None

            fixture_parser = ServiceTestPlanFixtureParser(fixture_file_name, fixture_name)
            test_fixture = fixture_parser.parse_test_fixture()

            for test_case in test_fixture:
                test_function = cls._create_test_function(
                    description=test_case['description'],
                    fixture_name=fixture_name,
                    test_case=test_case,
                    test_fixture=test_fixture,
                    test_fixture_results=test_fixture_results,
                )

                skip = test_case.get('skip', None)

                if not skip:
                    last_test_function = test_function

                yield FixtureTestCaseData(
                    name=test_case['name'],
                    description=test_case['description'],
                    fixture_name=fixture_name,
                    fixture_file=fixture_file_name,
                    line_number=test_case['line_number'],
                    skip=skip,
                    callable=test_function,
                )

            if last_test_function:
                last_test_function._last_fixture_test = True

    @classmethod
    def get_fixture_file_names(cls):
        """
        Generate the list of fixture files to run. If ``cls.custom_fixtures`` has a value, its contents will be
        returned directly. Otherwise, all fixtures in ``cls.fixture_path`` will be loaded based on
        ``cls.fixture_regex``.

        Results will be returned as a list or tuple, e.g. ``['full_path_to_fixture_1', 'full_path_to_fixture_2']``.

        :return: An alphabetically-sorted list of all fixture file names
        :rtype: union(list, tuple)
        """

        if cls.custom_fixtures:
            return cls.custom_fixtures

        if not cls.fixture_path:
            return []

        if not os.path.isdir(cls.fixture_path):
            raise FixtureLoadError(
                'Tried loading fixtures from "{}", however this path does not exist. Please specify the correct path '
                'by setting `cls.fixture_path`.'.format(cls.fixture_path)
            )

        fixture_files = []
        for directory_path, _, files in os.walk(cls.fixture_path):
            for fixture_file in files:
                if cls.fixture_regex.search(fixture_file):
                    fixture_files.append(directory_path + '/' + fixture_file)

        if not fixture_files:
            raise FixtureLoadError(
                'Could not find any fixture files in `cls.fixture_path` "{path}" that matched `cls.fixture_regex` '
                '"{regex}". To customize this regex, please override `cls.fixture_regex`.'.format(
                    path=cls.fixture_path,
                    regex=cls.fixture_regex.pattern,
                )
            )

        return sorted(fixture_files)

    @staticmethod
    def _create_test_function(description, fixture_name, test_case, test_fixture, test_fixture_results):
        """
        This method creates a test case function, which the PyTest plugin binds to the test case class to make it a
        method of the class, and which PyTest later invokes to run the test case.

        :param description: The test description, to which the created test function's ``__doc__`` will be set
        :type description: union[str, unicode]
        :param fixture_name: The fixture name
        :type fixture_name: union[str, unicode]
        :param test_case: The directive instructions to run and assert this specific test case
        :type test_case: dict
        :param test_fixture: List of test cases in this fixture
        :type test_fixture: list
        :param test_fixture_results: List of all action-call results in the entire fixture
        :type test_fixture_results: list
        :return: The test function, whose first argument must be an instance of test class inheriting from
                 ``ServicePlanTestCase``, and which accepts other args and kwargs that are currently ignored but
                 reserved for future use.
        :rtype: function
        """
        def test_function(self, *args, **kwargs):
            """
            This guy does the actual work of running a test case, and is invoked by PyTest when the time comes.

            :param self: The test case instance
            :type self: ServicePlanTestCase
            """

            # noinspection PyUnusedLocal
            # This instructs the traceback manipulator that this frame belongs to test_function, which is simpler than
            # having it analyze the code path details to determine the frame location.
            _test_function_frame = True  # noqa F841

            if not hasattr(self.__class__, '_test_fixture_setup_called'):
                self.__class__._test_fixture_setup_called = {}
            if not hasattr(self.__class__, '_test_fixture_setup_succeeded'):
                self.__class__._test_fixture_setup_succeeded = {}

            if not self._test_fixture_setup_called.get(fixture_name, False):
                # If this is the first test in the fixture, we need to set up the fixture
                self._test_fixture_setup_called[fixture_name] = self, test_fixture
                self.set_up_test_fixture(test_fixture)
                self._run_directive_hook('set_up_test_fixture', test_fixture)
                # After the fixture has set up without error, we note this so that all fixture tests can run
                self._test_fixture_setup_succeeded[fixture_name] = True

            if not self._test_fixture_setup_succeeded.get(fixture_name, False):
                # If the fixture was not successfully set up, then fixture setup must have failed on the first test, so
                # all remaining tests in this fixture are also invalid.
                raise StatusError('Test fixture {} not set up'.format(fixture_name))

            outer_exception = False
            try:  # LABEL: 1
                # First, we call the standard TestCase setUp, which we have taken over
                self.setUp()

                # Next, we call the fixture test case setup on the class and on all directives
                self.set_up_test_case(test_case, test_fixture)
                self._run_directive_hook('set_up_test_case', test_case, test_fixture)

                try:  # LABEL: 2
                    # Now we can actually run the test!
                    self._run_test_case(test_case, test_fixture, test_fixture_results, *args, **kwargs)
                except BaseException as e:
                    # We're only catching (everything) so that we can record which error happened in TRY 1
                    outer_exception = e
                    raise
                finally:
                    # noinspection PyBroadException
                    try:  # LABEL: 3
                        # Now we need to call the fixture test case teardown on the class and on all directives
                        self._run_directive_hook('tear_down_test_case', test_case, test_fixture)
                        self.tear_down_test_case(test_case, test_fixture)
                    except KeyboardInterrupt:
                        if outer_exception:
                            # If an error happened in TRY 2, raise it instead of the interrupt so we don't mask it
                            raise outer_exception
                        raise
                    except BaseException:
                        if not outer_exception:
                            raise  # If an error did not happen in TRY 2, just raise the tear-down error
                        self.addError(self, sys.exc_info())  # Otherwise, record the tear-down error so we don't mask
            except BaseException as e:
                outer_exception = e
                raise
            finally:
                try:  # LABEL: 4
                    # Almost done, we call the standard TestCase tearDown, which we have taken over
                    self.tearDown()
                except KeyboardInterrupt:
                    if outer_exception:
                        # If an error happened in TRY 1 - 3, raise it instead of the interrupt so we don't mask it
                        raise outer_exception
                    raise
                except BaseException as e:
                    if not outer_exception:
                        outer_exception = e
                        raise  # If an error did not happen in TRY 1 - 3, just raise the tear-down error
                    self.addError(self, sys.exc_info())  # Otherwise, record the tear-down error so we don't mask
                finally:
                    if test_function._last_fixture_test:
                        # If this is the last fixture test case, we need to assert and clean up the fixture
                        try:  # LABEL: 5
                            self._run_directive_hook('assert_test_fixture_results', test_fixture_results, test_fixture)
                        except KeyboardInterrupt:
                            if outer_exception:
                                # If an error happened in TRY 1 - 4, raise it instead of the interrupt so we don't mask
                                raise outer_exception
                            raise
                        except self.failureException as e:
                            # If the tear-down asserts raised an assertion error
                            if not outer_exception:
                                outer_exception = e
                                raise  # If an error did not happen in TRY 1 - 4, just raise the assertion error
                            self.addFailure(self, sys.exc_info())  # Otherwise, record the assertion error so no mask
                        except BaseException as e:
                            if not outer_exception:
                                outer_exception = e
                                raise  # If an error did not happen in TRY 1 - 4, just raise the on-assert error
                            self.addError(self, sys.exc_info())  # Otherwise, record the tear-down error so no mask
                        finally:
                            # noinspection PyBroadException
                            try:  # LABEL: 6
                                self._test_fixture_setup_succeeded[fixture_name] = False
                                self._test_fixture_setup_called[fixture_name] = False
                                self._run_directive_hook('tear_down_test_fixture', test_fixture)
                                self.tear_down_test_fixture(test_fixture)
                            except KeyboardInterrupt:
                                if outer_exception:
                                    # If an error happened in TRY 1 - 5, raise it instead of the interrupt so no mask
                                    raise outer_exception
                                raise
                            except BaseException:
                                if not outer_exception:
                                    raise  # If an error did not happen in TRY 1 - 5, just raise the tear-down error
                                self.addError(self, sys.exc_info())  # Otherwise, record the tear-down error so no mask

        test_function.__doc__ = description
        test_function._last_fixture_test = False

        return test_function

    @classmethod
    def _run_directive_hook(cls, hook, *args, **kwargs):
        """
        Runs the named hook method on all registered directives using the given positional and keyword arguments.

        :param hook: The name of the hook
        :type hook: union[str, unicode]
        """
        for directive_class in cls._all_directives:
            directive = directive_class()
            if not hasattr(directive, hook):
                raise DirectiveError('Directive class {} has no method {}.'.format(directive_class.__name__, hook))

            getattr(directive, hook)(*args, **kwargs)

    def _run_test_case(self, test_case, test_fixture, test_fixture_results, *_, **__):
        """
        This does the actual work of running the test case.

        :param test_case: The directive instructions to run and assert this specific test case
        :type test_case: dict
        :param test_fixture: List of test cases in this fixture
        :type test_fixture: list
        :param test_fixture_results: List of all action-call results in the entire fixture
        :type test_fixture_results: list
        """

        # noinspection PyUnusedLocal
        # This instructs the traceback manipulator that this frame belongs to _run_test_case, which is simpler than
        # having it analyze the code path details to determine the frame location.
        _run_test_case_frame = True  # noqa F841

        action_results = {}
        action_response_bodies = {}
        test_fixture_results.append(action_results)

        for action_path in test_case['actions']:
            action_name, action_index = action_path.split('.')
            action_case = test_case[action_path]

            if 'inputs' in action_case:
                substitute_variables(action_case['inputs'], action_response_bodies, self.model_constants)
            if 'job_control_inputs' in action_case:
                substitute_variables(action_case['job_control_inputs'], action_response_bodies, self.model_constants)
            if 'job_context_inputs' in action_case:
                substitute_variables(action_case['job_context_inputs'], action_response_bodies, self.model_constants)

            self.set_up_test_case_action(action_name, action_case, test_case, test_fixture)
            self._run_directive_hook('set_up_test_case_action', action_name, action_case, test_case, test_fixture)

            stub_context = self._WrapperContextManager()  # it's a no-op with no arguments
            if (
                action_name not in self.server_class.action_class_map and  # if the server doesn't have this action
                action_name not in ('status', 'introspect') and  # if the action isn't one of the built-in actions
                hasattr(self, '_process_stub_action_{}'.format(action_name))  # if the test job has a mock action
            ):
                # Hook for custom, test-only actions that are not real commands on the service.  Custom actions must
                # must work the same as side-effect functions on stub_action (must accept a request body dict and
                # return a response body dict, `ActionResponse`, or `JobResponse` or raise an `ActionError` or
                # `JobError`).
                stub_context = self._WrapperContextManager(
                    stub_action(self.server_class.service_name, action_name),
                    getattr(self, '_process_stub_action_{}'.format(action_name)),
                )

            with stub_context:
                job_response = self.client.call_actions(
                    service_name=self.server_class.service_name,
                    actions=[{'action': action_name, 'body': action_case.get('inputs', {})}],
                    raise_job_errors=False,
                    raise_action_errors=False,
                    context=action_case.get('job_context_inputs', {}),
                    control_extra=action_case.get('job_control_inputs', {}),
                )

            action_results[action_path] = job_response.actions[0] if job_response.actions else None
            action_response_bodies[action_path] = job_response.actions[0].body if job_response.actions else None

            substitute_variables(action_response_bodies, action_response_bodies, self.model_constants)
            substitute_variables(action_case, action_response_bodies, self.model_constants)

            try:
                self._run_directive_hook(
                    'assert_test_case_action_results',
                    action_name,
                    action_case,
                    test_case,
                    test_fixture,
                    action_results[action_path],
                    job_response,
                    action_path,
                )
            finally:
                try:
                    self._run_directive_hook(
                        'tear_down_test_case_action',
                        action_name,
                        action_case,
                        test_case,
                        test_fixture,
                    )
                finally:
                    self.tear_down_test_case_action(action_name, action_case, test_case, test_fixture)

        self._run_directive_hook('assert_test_case_results', action_results, test_case, test_fixture)

    class _WrapperContextManager(object):
        def __init__(self, stub_action_context=None, mock_action_side_effect=None):
            self._stub_action_context = stub_action_context
            self._mock_action_side_effect = mock_action_side_effect

        def __enter__(self):
            if self._stub_action_context:
                mock_action = self._stub_action_context.__enter__()
                mock_action.side_effect = self._mock_action_side_effect
                return mock_action

        def __exit__(self, *args):
            if self._stub_action_context:
                self._stub_action_context.__exit__(*args)
