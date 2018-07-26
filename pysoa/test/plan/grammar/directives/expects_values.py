"""
Expect action directives
"""
from __future__ import (
    absolute_import,
    unicode_literals,
)

from pyparsing import (
    CaselessLiteral,
    LineEnd,
    Literal,
    Optional,
    Suppress,
)

from pysoa.test.plan.grammar.assertions import (
    assert_not_expected,
    assert_not_present,
    assert_subset_structure,
)
from pysoa.test.plan.grammar.data_types import (
    DataTypeGrammar,
    get_parsed_data_type_value,
)
from pysoa.test.plan.grammar.directive import (
    ActionDirective,
    VarNameGrammar,
    VarValueGrammar,
    register_directive,
)
from pysoa.test.plan.grammar.tools import path_put


class ActionExpectsFieldValueDirective(ActionDirective):
    """
    Set expectations for values to be in the service call response.

    Using the ``not`` qualifier in the test will check to make sure that the field has any value other than the one
    specified.
    """

    @classmethod
    def name(cls):
        return 'expect_value'

    @classmethod
    def get_full_grammar(cls):
        return (
            super(ActionExpectsFieldValueDirective, cls).get_full_grammar() +
            Literal('expect') +
            Optional(DataTypeGrammar) +
            ':' +
            Optional(Literal('not')('not')) +
            Literal('attribute value') +
            ':' +
            VarNameGrammar +
            ':' +
            VarValueGrammar
        )

    def ingest_from_parsed_test_fixture(self, action_case, test_case, parse_results, file_name, line_number):
        variable_name = parse_results.variable_name

        path = 'expects'
        if getattr(parse_results, 'not', None):
            path = 'not_expects'

        path_put(
            action_case,
            '{}.{}'.format(path, variable_name),
            get_parsed_data_type_value(parse_results, parse_results.value),
        )

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
        if 'expects' in action_case:
            assert_subset_structure(
                action_case.get('expects', {}),
                action_response.body,
                False,
                msg,
            )

        if 'not_expects' in action_case:
            assert_not_expected(
                action_case['not_expects'],
                action_response.body,
                msg,
            )


class ActionExpectsAnyDirective(ActionExpectsFieldValueDirective):
    """
    Set expectations for values to be in the service call response where any value for the given data type will be
    accepted.
    """

    @classmethod
    def name(cls):
        return 'expect_any_value'

    @classmethod
    def get_full_grammar(cls):
        return (
            super(ActionExpectsFieldValueDirective, cls).get_full_grammar() +
            Literal('expect') +
            Literal('any')('any') +
            Optional(DataTypeGrammar) +
            ':' +
            Literal('attribute value') +
            ':' +
            VarNameGrammar +
            Optional(~Suppress(LineEnd()) + ':')
        )


class ActionExpectsNoneDirective(ActionExpectsFieldValueDirective):
    """
    Set expectations for values to be in the service call response where ``None`` value is expected.
    """

    @classmethod
    def name(cls):
        return 'expect_none'

    @classmethod
    def get_full_grammar(cls):
        return (
            super(ActionExpectsFieldValueDirective, cls).get_full_grammar() +
            Literal('expect') +
            CaselessLiteral('None')('data_type') +
            ':' +
            Literal('attribute value') +
            ':' +
            VarNameGrammar +
            Optional(~Suppress(LineEnd()) + ':')
        )


class ActionExpectsNotPresentDirective(ActionDirective):
    """
    Set expectation that the given field will not be present (even as a key) in the response.
    """

    @classmethod
    def name(cls):
        return 'expect_not_present'

    @classmethod
    def get_full_grammar(cls):
        return (
            super(ActionExpectsNotPresentDirective, cls).get_full_grammar() +
            Literal('expect not present') +
            ':' +
            Literal('attribute value') +
            ':' +
            VarNameGrammar +
            Optional(~Suppress(LineEnd()) + ':')
        )

    def ingest_from_parsed_test_fixture(self, action_case, test_case, parse_results, file_name, line_number):
        path_put(
            action_case,
            'expects_not_present.{}'.format(parse_results.variable_name),
            get_parsed_data_type_value(parse_results, parse_results.value),
        )

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
        if 'expects_not_present' in action_case:
            assert_not_present(
                action_case['expects_not_present'],
                action_response.body,
                msg,
            )


register_directive(ActionExpectsFieldValueDirective)
register_directive(ActionExpectsAnyDirective)
register_directive(ActionExpectsNoneDirective)
register_directive(ActionExpectsNotPresentDirective)
