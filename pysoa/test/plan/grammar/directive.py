"""
Modular directive system.

For a full list of installed directives and their grammars, see `pydoc pysoa.test.plan.grammar`

--

Directives define all syntax expressions the test plan system accepts as well as the validations/actions that occur
when using those directives.

Plugin writers can provide their own directives to expand the language by:

1) Subclass: `Directive`. In most cases, you will want to subclass `ActionDirective`. See below. Syntax grammars are
   expressed using `pyparsing`.

2) Link the directive in your module's entry points.  Example `setup.py`::

    from setuptools import (
        find_packages,
        setup,
    )

    setup(
        name='my_module',
        version='1.2.3.4',
        description='Some module',
        packages=find_packages(),
        entry_points={
            'pysoa.test.plan.grammar.directives': [
                'my_foo_directive = module.path.to.my.directives:MyFooDirectiveClass',
                'my_bar_directive = module.path.to.my.directives:MyBarDirectiveClass',
                etc...
            ]
        }
    )

OR

Register your directive using the `register_directive` function.
"""
from __future__ import (
    absolute_import,
    unicode_literals,
)

import abc
import sys

import pkg_resources
from pyparsing import (
    Literal,
    Optional,
    Word,
    alphanums,
    nums,
    restOfLine,
)
import six

from pysoa.common.types import (  # noqa F401
    ActionResponse,
    JobResponse,
)
from pysoa.test.plan.grammar.tools import recursive_parse_expr_repr


ENTRY_POINT_DIRECTIVES = []
REGISTERED_DIRECTIVES = []

VarNameGrammar = Word(alphanums + '-_.{}')('variable_name')
VarValueGrammar = restOfLine('value').setParseAction(lambda s, l, t: t[0].strip(' \t'))


def get_all_directives():
    if not ENTRY_POINT_DIRECTIVES:
        for entry_point in pkg_resources.iter_entry_points('pysoa.test.plan.grammar.directives'):
            try:
                directive_class = entry_point.resolve()
                ENTRY_POINT_DIRECTIVES.append(directive_class)
            except ImportError:
                sys.stderr.write('Warning: could not resolve {}\n'.format(entry_point))

    return REGISTERED_DIRECTIVES + ENTRY_POINT_DIRECTIVES


def register_directive(directive):
    REGISTERED_DIRECTIVES.append(directive)


@six.add_metaclass(abc.ABCMeta)
class Directive(object):
    """Superclass for all directives, defines all hooks.

    Expected runner driven lifecycle hooks of a directive:

    I. Parsing Phase:
        1) `get_full_grammar`:

            Used to populate pyparsing parser with grammar specific to this directive. Also used to generate
            documentation about available syntax.

        2) `ingest_from_parsed_test_fixture`:

            When a parsed line matches this directive, the pyparsing parse results are passed to this method which
            should do any setup required for assertion processing later in the runner lifecycle.  This is done for a
            single line at a time.

    II. Running Tests:
        1) `set_up_test_fixture`:

            After the test fixture file has been fully parsed but before any tests are actually run, this hook allows
            for pre-run setup and modification of the structures built during ingestion.

        2) For Each Individual Test in the test fixture:

            a) `set_up_test_case`:

                Before starting a new test or calling any actions, this method allows for
                more setup and modification of the structures built during ingestion.

            b) For each action in the the test case:

                i)  `set_up_test_case_action`:

                     Before calling the action on the test service, this method allows for more setup and modification
                     of the structures built during ingestion.

                ii)  Action gets run

                iii) `assert_test_case_action_results`:

                     Perform whatever tests against the immediate action response are needed. These tests (or
                     instructions for them) should have been setup during ingestion or the previous `setup` methods.

                iv)  `tear_down_test_case_action`:

                     Allow for cleanup activity after the action has been run and before the next action runs.

            c) `assert_test_case_results`:

                After all the actions in a test have been run and asserted, this method allows for assertions on the
                results of the entire test run at once and can see the results of all action calls.

                Perform whatever tests against the series of actions responses that are needed. These tests (or
                instructions for them) should have been setup during ingestion or the previous `setup` methods.

            d) `tear_down_test_case`:

                Allow for cleanup activity after the entire test case and all of its actions have been run.

        3) `tear_down_test_fixture`

            Allow for cleanup activity after all the tests in a fixture file have been run and before the runner moves
            on to the next fixture file.

    NOTE: All directives are expected to be stateless in their instances.  If you need persistent state use the
    test_fixture/test_case/action_case structures.

    Expected state structures (these are the arguments to the various hooks):

        test_fixture:                       A list of test_case

        test_case:                          dict of instructions for one entire test:

            - description                   Description of test (populated by `ingest_from_parsed_test_fixture` of
                                            TestCaseDescriptionDirective)

            - actions                       List of action names, which actions to run, in what order (populated by
                                            `ingest_from_parsed_test_fixture` of ActionDirective subclasses)

            - {action_key}:{action_case}    Dict of detailed directive data per action in the `actions` list. This is
                                            custom data populated by `ingest_from_parsed_test_fixture` of each
                                            `ActionDirective` subclass and the contents are specific to each directive.
    """

    @classmethod
    @abc.abstractmethod
    def name(cls):
        """
        Return a [a-z_]+ name for this directive
        """
        raise NotImplementedError('{} does not implement `name`'.format(str(cls)))

    @classmethod
    def supplies_additional_grammar_types(cls):
        """
        If the grammar produces base types not already listed in the documentation, this method should be overridden
        to return a non-empty map where the keys are the base type names and the values are the grammar definitions
        for those types. For example, these are standard base types implied by all action grammars (and already
        included in the documentation): ``{'action': 'NAME', 'action_index': 'NUM'}``
        """
        return {}

    @classmethod
    @abc.abstractmethod
    def get_full_grammar(cls):
        """
        Return the full pyparsing grammar needed to parse an entire line for this directive
        """
        raise NotImplementedError('{} does not implement `get_full_grammar`'.format(str(cls)))

    @abc.abstractmethod
    def ingest_from_parsed_test_fixture(self, action_case, test_case, parse_results, file_name, line_number):
        """
        Take parse results and populate test_case with directives for later processing.

        Note that extensive logic should not happen here, just memoization for later.

        :param action_case: The directive instructions for running and asserting this specific action
        :param test_case: A dict to populate with instructions for later. Use a unique key to avoid conflict with
                          other directives.
        :param parse_results: A pyparsing `ParseResults` object
        :param file_name: The name of the file currently being parsed
        :param line_number: The line number that has just been parsed
        """
        raise NotImplementedError('{} does not implement `ingest_from_parsed_test_fixture`'.format(str(self.__class__)))

    def post_parse_test_case(self, test_case):
        """
        Do work after parsing a test case, before parsing the next test case in the fixture.

        :param test_case: The directive instructions that were parsed for this test case
        """

    def post_parse_test_case_action(self, action_case, test_case):
        """
        Do work after parsing a test case action, before parsing the next test case action.

        :param action_case: The directive instructions that were parsed for this specific action
        :param test_case: The directive instructions that were parsed for this test case
        """

    def set_up_test_fixture(self, test_fixture, **kwargs):
        """
        Do setup work after parsing the test fixture file and before running any tests

        :param test_fixture: List of test cases in this fixture
        """

    def set_up_test_case(self, test_case, test_fixture, **kwargs):
        """
        Do setup work before running a test

        :param test_case: The directive instructions to run and assert this specific test case
        :param test_fixture: List of test cases in this fixture
        """

    def set_up_test_case_action(self, action_name, action_case, test_case, test_fixture, **kwargs):
        """
        Do setup work before running an action in a test

        :param action_name: The name of the action being run (as described in the test case in the fixture)
        :param action_case: The directive instructions for running and asserting this specific action
        :param test_case: The directive instructions to run and assert this specific test case
        :param test_fixture: List of test cases in this fixture
        """

    @abc.abstractmethod
    def assert_test_case_action_results(
        self,
        action_name,
        action_case,
        test_case,
        test_fixture,
        action_response,
        job_response,
        msg=None,
        **kwargs
    ):
        """
        Run assertions against the results of running an action.

        :param action_name: The name of the action being run (as described in the test case in the fixture)
        :param action_case: The directive instructions for running and asserting this specific action
        :param test_case: The directive instructions to run and assert this specific test case
        :param test_fixture: List of test cases in this fixture
        :param action_response: The action response
        :type action_response: ActionResponse
        :param job_response: The job response
        :type job_response: JobResponse
        :param msg: Error message to include in the thrown AssertionError

        :raise: AssertionError
        """
        raise NotImplementedError('{} does not implement `assert_test_case_action_results`'.format(str(self.__class__)))

    def tear_down_test_case_action(self, action_name, action_case, test_case, test_fixture, **kwargs):
        """
        Do cleanup work after running an action in a test

        :param action_name: The name of the action being run (as described in the test case in the fixture)
        :param action_case: The directive instructions for running and asserting this specific action
        :param test_case: The directive instructions to run and assert this specific test case
        :param test_fixture: List of test cases in this fixture
        """

    def assert_test_case_results(self, test_action_results_dict, test_case, test_fixture, msg=None, **kwargs):
        """
        Run assertions against the entire set of test results.

        NOTE: Do not assume that all actions were called!  An assertion (or other failure) in an action call may
        short circuit the rest of the test!

        :param test_action_results_dict: Dict of all `action_response`s for the test, keyed by action name.
        :param test_case: The directive instructions to run and assert this specific test case
        :param test_fixture: List of test cases in this fixture
        :param msg: Error message to include in the thrown AssertionError

        :raise: AssertionError
        """

    def tear_down_test_case(self, test_case, test_fixture, **kwargs):
        """
        Do cleanup work after running a test

        :param test_case: The directive instructions to run and assert this specific test case
        :param test_fixture: List of test cases in this fixture
        """

    def assert_test_fixture_results(self, test_fixture_results, test_fixture, msg=None, **kwargs):
        """
        Run assertions against entire test fixture file results before moving on to next test file.

        NOTE: Do not assume that all test cases were run!  An error may have short circuited the entire fixture.

        :param test_fixture_results: List of test_action_results, ordered to match test_fixture
        :param test_fixture: List of test cases in this fixture
        :param msg: Error message to include in the thrown AssertionError

        :raise: AssertionError
        """

    def tear_down_test_fixture(self, test_fixture, **kwargs):
        """
        Do cleanup work after running all the tests in a test fixture file.

        :param test_fixture: List of test cases in this fixture
        """

    def __repr__(self):
        return recursive_parse_expr_repr(self.get_full_grammar())


@six.add_metaclass(abc.ABCMeta)
class ActionDirective(Directive):
    """
    Superclass for `action: ` directives
    """

    @classmethod
    def get_full_grammar(cls):
        action = ~(Literal('input') | Literal('expect')) + Word(alphanums + '_')('action')
        action_index = '.' + Word(nums)('action_index')
        global_scope = Literal('global')('is_global').setParseAction(lambda s, l, t: t[0] == 'global')

        return action + Optional(action_index) + ':' + Optional(global_scope)
