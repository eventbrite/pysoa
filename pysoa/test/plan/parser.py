from __future__ import (
    absolute_import,
    unicode_literals,
)

import codecs
import copy
import functools
import os

from pyparsing import (
    LineEnd,
    LineStart,
    MatchFirst,
    OneOrMore,
    ParseException,
    StringEnd,
    StringStart,
    col as get_parse_column,
    line as get_parse_line,
    lineno as get_parse_line_number,
)

from pysoa.test.plan.errors import (
    FixtureLoadError,
    FixtureSyntaxError,
)
from pysoa.test.plan.grammar.data_types import DataTypeConversionError
from pysoa.test.plan.grammar.directive import get_all_directives
from pysoa.test.plan.grammar.tools import (
    get_all_paths,
    path_get,
    path_put,
)


class ServiceTestPlanFixtureParser(object):
    """
    This class is responsible for parsing test plans. Create an instance using a fixture file name and fixture name,
    and then call ``parse_test_fixture`` to parse the fixture file and return all the test cases in it.
    """

    def __init__(self, fixture_file_name, fixture_name):
        """
        Construct a test fixture parser.

        :param fixture_file_name: The path to and name of the fixture file
        :type fixture_file_name: union[str, unicode]
        :param fixture_name: The name of the fixture
        :type fixture_name: union[str, unicode]
        """
        self._fixture_file_name = fixture_file_name
        self._fixture_name = fixture_name
        self._working_directory = os.path.basename(fixture_file_name)

        if not os.path.isabs(self._fixture_file_name):
            self._fixture_file_name = os.path.abspath(os.path.join(self._working_directory, self._fixture_file_name))

        self.test_cases = []
        self._global_directives = {}
        self._working_action_case = {}
        self._working_test_case = {}
        self._working_test_case_line_number = 0
        self._working_test_case_source = []
        self._fixture_source = []
        self._grammar = None
        self._line_number = 0

    def parse_test_fixture(self):
        """
        The main method responsible for the start-to-finish process of parsing test cases from a fixture file. It uses
        the other methods on this class, which generally should not be used directly.

        :return: The list of test cases
        :rtype: list[dict]
        """
        self._grammar = self._compile_grammar()

        self._ingest_directives()

        if not self.test_cases:
            raise FixtureLoadError('Failed to find any test cases in file: {}'.format(self._fixture_file_name))

        return self.test_cases

    def _ingest_directives(self):
        try:
            with codecs.open(self._fixture_file_name, mode='rb', encoding='utf-8') as file_input:
                self._grammar.parseFile(file_input)

            # explicit finalize on EOF to catch case of no blank line at end of file
            self._finalize_test_case('', 0, None)
        except ParseException as e:
            line_text = get_parse_line(e.loc, e.pstr)
            line_number = get_parse_line_number(e.loc, e.pstr)
            offset = get_parse_column(e.loc, e.pstr)
            raise FixtureSyntaxError(
                'Failed to parse line: {line}\nin file: {file}:{line_number}\n{message}'.format(
                    line=line_text,
                    file=self._fixture_file_name,
                    line_number=line_number,
                    message=e.msg,
                ),
                file_name=self._fixture_file_name,
                line_number=line_number,
                offset=offset,
                line_text=line_text,
            )
        except DataTypeConversionError as e:
            raise FixtureSyntaxError(
                'Data type conversion error\nin file: {file}:{line_number}\n{message}'.format(
                    file=self._fixture_file_name,
                    line_number=self._line_number,
                    message=e.args[0],
                ),
                file_name=self._fixture_file_name,
                line_number=self._line_number,
            )
        except IOError as e:
            raise FixtureLoadError(str(e))

    def _compile_grammar(self):
        """
        Takes the individual grammars from each registered directive and compiles them into a full test fixture grammar
        whose callback methods are the bound methods on this class instance.

        :return: The full PyParsing grammar for test fixture files.
        """
        grammars = [
            (LineEnd().suppress()).setParseAction(
                functools.partial(self._finalize_test_case)
            )
        ]

        # directives
        for directive_class in get_all_directives():
            grammars.append(
                LineStart() +
                directive_class.get_full_grammar().setParseAction(
                    functools.partial(self._ingest_directive, directive_class)
                ) +
                LineEnd()
            )

        return StringStart() + OneOrMore(MatchFirst(grammars)) + StringEnd()

    def _ingest_directive(self, directive_class, active_string, location, parse_result):
        """
        A callback that ingests a particular matched directive. Called by PyParsing when processing the grammar.

        :param directive_class: The matched directive class (not an instance)
        :type directive_class: type
        :param active_string: The contents of the fixture file
        :type active_string: union[str, unicode]
        :param location: The file location of the current parsing activity
        :param parse_result: The resulting PyParsing parsing object
        """
        self._line_number = get_parse_line_number(location, active_string)
        source = get_parse_line(location, active_string)
        self._fixture_source.append(source)

        if self._working_test_case and not self._working_test_case_line_number:
            self._working_test_case_line_number = self._line_number - 1

        test_case_target = self._working_test_case
        if parse_result.is_global:
            # This is actually a global directive, so we're working on those, not on a test case
            test_case_target = self._global_directives
        else:
            self._working_test_case_source.append(source)

        if parse_result.action:
            action_path = '{}.{}'.format(parse_result.action, parse_result.action_index or '0')
            if 'actions' not in test_case_target:
                test_case_target['actions'] = []

            if action_path not in test_case_target:
                if not parse_result.is_global:
                    # Global directives don't need a list of actions to run; only test cases do
                    test_case_target['actions'].append(action_path)

                if self._working_action_case:
                    # We're done parsing the previous action case and starting a new one
                    for dc in get_all_directives():
                        dc().post_parse_test_case_action(self._working_action_case, test_case_target)

                test_case_target[action_path] = {}

            action_case_target = test_case_target[action_path]
            self._working_action_case = action_case_target
        else:
            # This branch handles non-action directives, such as comments, test names, test descriptions, non-action
            # time-freezing, non-action mocking, etc.
            action_case_target = test_case_target

        directive_class().ingest_from_parsed_test_fixture(
            action_case_target,
            test_case_target,
            parse_result,
            self._fixture_file_name,
            self._line_number,
        )

    def _finalize_test_case(self, active_string, location, _):
        """
        Called by PyParsing at the end of each test case.

        :param active_string: The contents of the fixture file
        :type active_string: union[str, unicode]
        :param location: The file location of the current parsing activity
        """
        self._fixture_source.append('')

        if self._working_action_case:
            # We're done parsing the test case and still need to wrap up the last action in the test case
            for dc in get_all_directives():
                dc().post_parse_test_case_action(
                    self._working_action_case,
                    self._working_test_case or self._global_directives,
                )
            self._working_action_case = {}

        if not self._working_test_case:
            # just a blank line before any test cases, probably after globals or an extra blank line between tests
            return

        self._working_test_case['line_number'] = self._working_test_case_line_number
        self._working_test_case_line_number = 0

        self._working_test_case['fixture_name'] = self._fixture_name
        self._working_test_case['fixture_file_name'] = self._fixture_file_name
        self._working_test_case['source'] = self._working_test_case_source

        line_number = get_parse_line_number(location, active_string)
        if not self._working_test_case.get('name'):

            raise FixtureSyntaxError(
                '{}:{}: Test case without name'.format(self._fixture_file_name, line_number),
                file_name=self._fixture_file_name,
                line_number=line_number - 1,
            )

        if not self._working_test_case.get('description'):
            raise FixtureSyntaxError(
                '{}:{}: Test case without description'.format(self._fixture_file_name, line_number),
                file_name=self._fixture_file_name,
                line_number=line_number - 1,
            )

        if not self._working_test_case.get('actions') and not self._global_directives:
            raise FixtureSyntaxError(
                '{}:{}: Empty test case'.format(self._fixture_file_name, line_number),
                file_name=self._fixture_file_name,
                line_number=line_number - 1,
            )

        if self._global_directives:
            # merge, but make sure current overlays global where there is conflict
            test_case = {}

            for path in get_all_paths(self._global_directives):
                try:
                    path_put(test_case, path, path_get(self._global_directives, path))
                except (KeyError, IndexError):
                    raise FixtureSyntaxError(
                        'Invalid path: `{}`'.format(path),
                        file_name=self._fixture_file_name,
                        line_number=line_number,
                    )
            for path in get_all_paths(self._working_test_case):
                try:
                    path_put(test_case, path, path_get(self._working_test_case, path))
                except (KeyError, IndexError):
                    raise FixtureSyntaxError(
                        'Invalid path: `{}`'.format(path),
                        file_name=self._fixture_file_name,
                        line_number=line_number,
                    )

            for directive_class in get_all_directives():
                directive_class().post_parse_test_case(test_case)
        else:
            for directive_class in get_all_directives():
                directive_class().post_parse_test_case(self._working_test_case)

            test_case = copy.deepcopy(self._working_test_case)

        test_case['fixture_source'] = self._fixture_source
        self.test_cases.append(test_case)

        self._working_test_case.clear()
        self._working_test_case_source = []
