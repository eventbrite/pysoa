"""
Expect error directives
"""
from __future__ import (
    absolute_import,
    unicode_literals,
)

from pyparsing import (
    Literal,
    Optional,
    Word,
    alphanums,
    restOfLine,
)
import six

from pysoa.common.types import Error
from pysoa.test.plan.grammar.assertions import (
    assert_actual_list_not_subset,
    assert_expected_list_subset_of_actual,
    assert_lists_match_any_order,
)
from pysoa.test.plan.grammar.data_types import AnyValue
from pysoa.test.plan.grammar.directive import (
    ActionDirective,
    register_directive,
)
from pysoa.test.plan.grammar.tools import (
    path_get,
    path_put,
)


__test_plan_prune_traceback = True  # ensure code in this file is not included in failure stack traces


class ActionExpectsNoErrorsDirective(ActionDirective):
    """
    Expect that no errors are reported back in the service call response. Any error in either the job response or the
    action response will cause this expectation to fail.
    """

    @classmethod
    def name(cls):
        return 'expect_no_errors'

    @classmethod
    def get_full_grammar(cls):
        return (
            super(ActionExpectsNoErrorsDirective, cls).get_full_grammar() +
            Literal('expect') +
            ':' +
            Literal('no errors')
        )

    def ingest_from_parsed_test_fixture(self, action_case, test_case, parse_results, file_name, line_number):
        action_case['expects_no_errors'] = True

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
        if not action_case.get('expects_no_errors', False):
            return

        if job_response.errors:
            raise AssertionError('{}: Expected no job errors, but got: {}'.format(msg or '', job_response.errors))

        if action_response.errors:
            raise AssertionError('{}: Expected no action errors, but got: {}'.format(msg or '', action_response.errors))


class ActionExpectsErrorsDirective(ActionDirective):
    """
    Set expectations that specific errors will (or will not) be in the service response. Any error that that matches
    this code, whether or not it has a field or message, will fulfill this expectation.

    If ``not`` is used, the absence of the error will be asserted (it negates the expectation exactly). As long as no
    error has this code, this expectation will pass.

    If ``exact`` is used, then all of the errors you define must match all of the errors in your response, and your
    response cannot have any non-matching extra errors. ``exact`` and non-``exact`` are mutually-exclusive
    expectations: an action case that has a mixture of ``exact`` and non-``exact`` error expectations will fail. For
    each error case, you must use one or the other.

    If ``job`` is used, then the job response will be examined for the error instead of the action response.
    """

    @classmethod
    def name(cls):
        return 'expect_error'

    @classmethod
    def get_full_grammar(cls):
        return (
            super(ActionExpectsErrorsDirective, cls).get_full_grammar() +
            Literal('expect') +
            ':' +
            Optional('not').setResultsName('not') +
            Optional('exact')('exact') +
            Optional('job')('job') +
            Literal('error') +
            ':' +
            Literal('code') +
            '=' +
            Word(alphanums + '-_')('error_code')
        )

    def ingest_from_parsed_test_fixture(self, action_case, test_case, parse_results, file_name, line_number):
        path = 'expects_{not_q}{job_q}{exact_q}error'.format(
            not_q='not_' if getattr(parse_results, 'not', None) else '',
            job_q='job_' if parse_results.job else '',
            exact_q='exact_' if parse_results.exact else '',
        )

        try:
            errors = path_get(action_case, path)
        except (KeyError, IndexError):
            errors = []
            path_put(action_case, path, errors)

        errors.append(Error(
            code=parse_results.error_code,
            message=getattr(parse_results, 'error_message', None) or AnyValue('str'),
            field=getattr(parse_results, 'field_name', None) or AnyValue('str', permit_none=True),
            traceback=AnyValue('str', permit_none=True),
            variables=AnyValue('list', permit_none=True),
        ))

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
        for instruction, expected in six.iteritems(action_case):
            if instruction.startswith('expects_') and instruction.endswith('_error'):
                target = action_response
                if '_job_' in instruction:
                    target = job_response

                errors = target.errors if target else []

                try:
                    if '_not_' in instruction:
                        assert_actual_list_not_subset(expected, errors, 'NOT EXPECTED ERRORS: {}'.format(msg or ''))
                    elif '_exact_' in instruction:
                        assert_lists_match_any_order(expected, errors, 'EXPECTED EXACT ERRORS: {}'.format(msg or ''))
                    else:
                        assert_expected_list_subset_of_actual(expected, errors, 'EXPECTED ERRORS: {}'.format(msg or ''))
                except AssertionError as e:
                    for error in errors:
                        if error.code == 'SERVER_ERROR':
                            raise type(e)(
                                '{message}\n\nSERVER_ERROR: {detail}'.format(
                                    message=e.args[0],
                                    detail=error.message,
                                ),
                            )
                    raise


class ActionExpectsFieldErrorsDirective(ActionExpectsErrorsDirective):
    """
    Set expectations that specific errors will (or will not) be in the service response. Any error that that matches
    this code *and* field, whether or not it has a message value, will fulfill this expectation.

    If ``not`` is used, the absence of the error will be asserted (it negates the expectation exactly). As long as no
    error has this code *and* field (even if some errors have this code and other errors have this field), this
    expectation will pass.

    If ``exact`` is used, then all of the errors you define must match all of the errors in your response, and your
    response cannot have any non-matching extra errors. ``exact`` and non-``exact`` are mutually-exclusive
    expectations: an action case that has a mixture of ``exact`` and non-``exact`` error expectations will fail. For
    each error case, you must use one or the other.

    If ``job`` is used, then the job response will be examined for the error instead of the action response.
    """

    @classmethod
    def name(cls):
        return 'expect_error_field'

    @classmethod
    def get_full_grammar(cls):
        return (
            super(ActionExpectsFieldErrorsDirective, cls).get_full_grammar() +
            ',' +
            Literal('field') +
            '=' +
            Word(alphanums + '-_.{}[]')('field_name')
        )


class ActionExpectsMessageErrorsDirective(ActionExpectsErrorsDirective):
    """
    Set expectations that specific errors will (or will not) be in the service response. Any error that that matches
    this code *and* message, whether or not it has a field value, will fulfill this expectation.

    If ``not`` is used, the absence of the error will be asserted (it negates the expectation exactly). As long as no
    error has this code *and* message (even if some errors have this code and other errors have this message), this
    expectation will pass.

    If ``exact`` is used, then all of the errors you define must match all of the errors in your response, and your
    response cannot have any non-matching extra errors. ``exact`` and non-``exact`` are mutually-exclusive
    expectations: an action case that has a mixture of ``exact`` and non-``exact`` error expectations will fail. For
    each error case, you must use one or the other.

    If ``job`` is used, then the job response will be examined for the error instead of the action response.
    """

    @classmethod
    def name(cls):
        return 'expect_error_message'

    @classmethod
    def get_full_grammar(cls):
        return (
            super(ActionExpectsMessageErrorsDirective, cls).get_full_grammar() +
            ',' +
            Literal('message') +
            '=' +
            restOfLine('error_message').setParseAction(lambda s, l, t: t[0].strip(' \t'))
        )


class ActionExpectsFieldMessageErrorsDirective(ActionExpectsFieldErrorsDirective):
    """
    Set expectations that specific errors will (or will not) be in the service response. Any error that that matches
    this code, field, *and* message will fulfill this expectation.

    If ``not`` is used, the absence of the error will be asserted (it negates the expectation exactly). As long as no
    error has this code, field, *and* message, this expectation will pass.

    If ``exact`` is used, then all of the errors you define must match all of the errors in your response, and your
    response cannot have any non-matching extra errors. ``exact`` and non-``exact`` are mutually-exclusive
    expectations: an action case that has a mixture of ``exact`` and non-``exact`` error expectations will fail. For
    each error case, you must use one or the other.

    If ``job`` is used, then the job response will be examined for the error instead of the action response.
    """

    @classmethod
    def name(cls):
        return 'expect_error_field_message'

    @classmethod
    def get_full_grammar(cls):
        return (
            super(ActionExpectsFieldMessageErrorsDirective, cls).get_full_grammar() +
            ',' +
            Literal('message') +
            '=' +
            restOfLine('error_message').setParseAction(lambda s, l, t: t[0].strip(' \t'))
        )


# This order is very important; do not disturb
register_directive(ActionExpectsFieldMessageErrorsDirective)
register_directive(ActionExpectsMessageErrorsDirective)
register_directive(ActionExpectsFieldErrorsDirective)
register_directive(ActionExpectsErrorsDirective)
register_directive(ActionExpectsNoErrorsDirective)
