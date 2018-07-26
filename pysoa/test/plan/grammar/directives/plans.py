"""
Top level plan oriented directives
"""
from __future__ import (
    absolute_import,
    unicode_literals,
)

from pyparsing import (
    Literal,
    Optional,
    Suppress,
    Word,
    alphanums,
    restOfLine,
)

from pysoa.test.plan.errors import FixtureSyntaxError
from pysoa.test.plan.grammar.directive import (
    Directive,
    register_directive,
)
from pysoa.test.plan.grammar.tools import path_put


class TestCaseNameDirective(Directive):
    """
    The (required) name of the test, which must be a valid method name in Python syntax.
    """

    @classmethod
    def name(cls):
        return 'test_name'

    @classmethod
    def get_full_grammar(cls):
        return (
            Literal('test name') +
            ':' +
            Word(alphanums + '_')('name')
        )

    def ingest_from_parsed_test_fixture(self, action_case, test_case, parse_results, file_name, line_number):
        if 'name' in test_case:
            raise FixtureSyntaxError('Duplicate test name directive for test case', file_name, line_number)

        path_put(test_case, 'name', parse_results.name)

    def assert_test_case_action_results(*args, **kwargs):
        pass


class TestCaseDescriptionDirective(Directive):
    """
    The (required) description for the test, which can be a regular, plain-language sentence.
    """

    @classmethod
    def name(cls):
        return 'test_description'

    @classmethod
    def get_full_grammar(cls):
        return (
            Literal('test description') +
            ':' +
            restOfLine()('description')
        )

    def ingest_from_parsed_test_fixture(self, action_case, test_case, parse_results, file_name, line_number):
        if 'description' in test_case:
            raise FixtureSyntaxError('Duplicate test description directive for test case', file_name, line_number)

        path_put(
            test_case,
            'description',
            '{}\n{}'.format(parse_results.description.strip(' \t\n'), file_name),
        )

    def assert_test_case_action_results(*args, **kwargs):
        pass


class TestCaseCommentDirective(Directive):
    """
    All lines that start with ``#`` are comments.
    """

    @classmethod
    def name(cls):
        return 'fixture_comment'

    @classmethod
    def get_full_grammar(cls):
        return Suppress(Literal('#') + restOfLine())

    def ingest_from_parsed_test_fixture(self, action_case, test_case, parse_results, file_name, line_number):
        pass

    def assert_test_case_action_results(*args, **kwargs):
        pass

    def __repr__(self):
        return "'#' comment"


class TestCaseSkipDirective(Directive):
    """
    Use this directive to skip a test or, with ``global``, to skip all tests in the entire fixture
    """

    @classmethod
    def name(cls):
        return 'test_skip'

    @classmethod
    def get_full_grammar(cls):
        return (
            Literal('test skip') +
            Optional(Literal('global')('is_global').setParseAction(lambda s, l, t: t[0] == 'global')) +
            ':' +
            restOfLine()('reason')
        )

    def ingest_from_parsed_test_fixture(self, action_case, test_case, parse_results, file_name, line_number):
        path_put(test_case, 'skip', parse_results.reason.strip(' \t'))

    def assert_test_case_action_results(*args, **kwargs):
        pass


register_directive(TestCaseCommentDirective)
register_directive(TestCaseNameDirective)
register_directive(TestCaseDescriptionDirective)
register_directive(TestCaseSkipDirective)
