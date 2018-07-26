"""
Action input directives
"""
from __future__ import (
    absolute_import,
    unicode_literals,
)

from pyparsing import (
    Literal,
    Optional,
    oneOf,
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


class ActionInputDirective(ActionDirective):
    """
    Set inputs that will be sent for an action in the service request.

    Using ``job control`` will put the value in the job control header instead of the action request.

    Using ``job context`` will put the value in the job context header instead of the action request.
    """

    @classmethod
    def name(cls):
        return 'input'

    @classmethod
    def get_full_grammar(cls):
        return (
            super(ActionInputDirective, cls).get_full_grammar() +
            Optional(Literal('job') + oneOf(('control', 'context'))('job_slot')) +
            Literal('input') +
            Optional(DataTypeGrammar) +
            ':' +
            VarNameGrammar +
            ':' +
            VarValueGrammar
        )

    def ingest_from_parsed_test_fixture(self, action_case, test_case, parse_results, file_name, line_number):
        parsed_data_type_value = get_parsed_data_type_value(parse_results, parse_results.value)

        path = 'inputs'
        if parse_results.job_slot == 'control':
            path = 'job_control_' + path

        if parse_results.job_slot == 'context':
            path = 'job_context_' + path

        path_put(
            action_case,
            '{}.{}'.format(path, parse_results.variable_name),
            parsed_data_type_value,
        )

    def assert_test_case_action_results(*args, **kwargs):
        pass


register_directive(ActionInputDirective)
