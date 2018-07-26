"""
Directives for stubbing calls to other services
"""
from __future__ import (
    absolute_import,
    unicode_literals,
)

import sys
import traceback

from pyparsing import (
    Literal,
    Optional,
    Word,
    alphanums,
    restOfLine,
)
import six

from pysoa.common.types import Error
from pysoa.test.compatibility import mock as unittest_mock
from pysoa.test.plan.errors import FixtureSyntaxError
from pysoa.test.plan.grammar.data_types import (
    DataTypeGrammar,
    get_parsed_data_type_value,
)
from pysoa.test.plan.grammar.directive import (
    ActionDirective,
    Directive,
    VarNameGrammar,
    VarValueGrammar,
    register_directive,
)
from pysoa.test.plan.grammar.tools import path_put
from pysoa.test.stub_service import stub_action


def _ingest_action_body(test_target, parse_results, file_name, line_number):
    key = (parse_results.stub_service, parse_results.stub_action)
    stub_config = test_target.setdefault('stubbed_actions', {}).setdefault(key, {})

    if 'errors' in stub_config:
        raise FixtureSyntaxError(
            'Cannot combine stub action body and errors (must choose one) for {}.{}'.format(*key),
            file_name,
            line_number,
        )

    path_put(
        stub_config.setdefault('body', {}),
        parse_results.variable_name,
        get_parsed_data_type_value(parse_results, parse_results.value),
    )


def _ingest_error_body(test_target, parse_results, file_name, line_number):
    key = (parse_results.stub_service, parse_results.stub_action)
    stub_config = test_target.setdefault('stubbed_actions', {}).setdefault(key, {})

    if 'body' in stub_config:
        raise FixtureSyntaxError(
            'Cannot combine stub action body and errors (must choose one) for {}.{}'.format(*key),
            file_name,
            line_number,
        )

    field = parse_results.field_name
    if not field or not field.strip() or field.strip().lower() == 'none':
        field = None

    message = parse_results.error_message
    if not message or not message.strip() or message.strip().lower() == 'none':
        message = None

    stub_config.setdefault('errors', []).append({
        'code': parse_results.error_code,
        'message': message,
        'field': field,
    })


def _ingest_expect_called(test_target, parse_results, file_name, line_number):
    key = (parse_results.stub_service, parse_results.stub_action)
    stub_config = test_target.setdefault('stubbed_actions', {}).setdefault(key, {})

    if getattr(parse_results, 'not', False):
        if 'expect_request' in stub_config:
            raise FixtureSyntaxError(
                'Cannot combine "expect called" and "expect not called" on the same stub action for {}.{}'.format(*key),
                file_name,
                line_number,
            )
        stub_config['expect_not_called'] = True
    else:
        if 'expect_not_called' in stub_config:
            raise FixtureSyntaxError(
                'Cannot combine "expect called" and "expect not called" on the same stub action for {}.{}'.format(*key),
                file_name,
                line_number,
            )
        if getattr(parse_results, 'variable_name', None):
            path_put(
                stub_config.setdefault('expect_request', {}),
                parse_results.variable_name,
                get_parsed_data_type_value(parse_results, parse_results.value),
            )
        else:
            stub_config.setdefault('expect_request', {})


def _start_stubbed_actions(test_target):
    if 'stubbed_actions' in test_target:
        # We must start the stubs in a predictable order...
        for service, action in sorted(six.iterkeys(test_target['stubbed_actions'])):
            stub_config = test_target['stubbed_actions'][service, action]
            if 'errors' in stub_config:
                stub = stub_action(service, action, errors=[Error(**e) for e in stub_config['errors']])
            else:
                stub = stub_action(service, action, body=stub_config.get('body', {}))

            mock_action = stub.start()
            stub_config['started_stub'] = stub
            stub_config['mock_action'] = mock_action


def _stop_stubbed_actions(test_target):
    if 'stubbed_actions' in test_target:
        # ...and then we must stop the stubs in the reverse order we started them (backing out).
        for service, action in sorted(six.iterkeys(test_target['stubbed_actions']), reverse=True):
            stub_config = test_target['stubbed_actions'][service, action]
            if 'started_stub' in stub_config:
                # noinspection PyBroadException
                try:
                    stub_config['started_stub'].stop()
                except Exception:
                    sys.stderr.write('WARNING: Failed to stop stub for {service}.{action} due to error:\n'.format(
                        service=service,
                        action=action,
                    ))
                    sys.stderr.write('{}\n'.format(traceback.format_exc()))


def _assert_stub_expectations(test_target):
    if 'stubbed_actions' in test_target:
        for stub_config in six.itervalues(test_target['stubbed_actions']):
            if 'mock_action' in stub_config:
                if 'expect_request' in stub_config:
                    stub_config['mock_action'].assert_has_calls([
                        unittest_mock.call(stub_config['expect_request']),
                    ])
                elif 'expect_not_called' in stub_config:
                    assert stub_config['mock_action'].call_count == 0


class StubActionBodyForTestPlanDirective(Directive):
    """
    Use this directive to stub an action call to another service that your service calls and set what that stubbed
    service action should return in the response body. This is mutually exclusive with stubbing an error to be
    returned by the stubbed service action. This follows the standard path-placing syntax used for action request
    and expectation directives. This directive applies to an entire test case. The action is stubbed before the first
    action case is run, and the stub is stopped after the last action case completes. The following use of this
    directive::

        stub action: user: get_user: body int: id: 12
        stub action: user: get_user: body: first_name: John
        stub action: user: get_user: body: last_name: Smith

    Is equivalent to this Python code:

    .. code-block:: python

        with stub_action('user', 'get_user', body={'id': 12, 'first_name': 'John', 'last_name': 'Smith'}):
            # run all actions in this test
    """

    @classmethod
    def name(cls):
        return 'stub_action_body_for_test'

    @classmethod
    def supplies_additional_grammar_types(cls):
        return {}

    @classmethod
    def get_full_grammar(cls):
        return (
            Literal('stub action') +
            ':' +
            Word(alphanums + '_')('stub_service') +
            ':' +
            Word(alphanums + '_.')('stub_action') +
            ':' +
            Literal('body') +
            Optional(DataTypeGrammar) +
            ':' +
            VarNameGrammar +
            ':' +
            VarValueGrammar
        )

    def ingest_from_parsed_test_fixture(self, action_case, test_case, parse_results, file_name, line_number):
        _ingest_action_body(test_case, parse_results, file_name, line_number)

    def assert_test_case_action_results(*_, **__):
        pass


class StubActionBodyForActionDirective(ActionDirective):
    """
    Use this directive to stub an action call to another service that your service calls and set what that stubbed
    service action should return in the response body. This is mutually exclusive with stubbing an error to be
    returned by the stubbed service action. This follows the standard path-placing syntax used for action request
    and expectation directives. This directive applies to an individual action case. The action is stubbed immediately
    before the action case is run, and the stub is stopped immediately after the action case completes. The
    following use of this directive::

        create_bookmark: stub action: user: get_user: body int: id: 12
        create_bookmark: stub action: user: get_user: body: first_name: John
        create_bookmark: stub action: user: get_user: body: last_name: Smith

    Is equivalent to this Python code:

    .. code-block:: python

        with stub_action('user', 'get_user', body={'id': 12, 'first_name': 'John', 'last_name': 'Smith'}):
            # run the first (possibly only) create_bookmark action case
    """

    @classmethod
    def name(cls):
        return 'stub_action_body_for_action'

    @classmethod
    def get_full_grammar(cls):
        return (
            super(StubActionBodyForActionDirective, cls).get_full_grammar() +
            Literal('stub action') +
            ':' +
            Word(alphanums + '_')('stub_service') +
            ':' +
            Word(alphanums + '_.')('stub_action') +
            ':' +
            Literal('body') +
            Optional(DataTypeGrammar) +
            ':' +
            VarNameGrammar +
            ':' +
            VarValueGrammar
        )

    def ingest_from_parsed_test_fixture(self, action_case, test_case, parse_results, file_name, line_number):
        _ingest_action_body(action_case, parse_results, file_name, line_number)

    def assert_test_case_action_results(*_, **__):
        pass


class StubActionErrorForTestPlanDirective(Directive):
    """
    Use this directive to stub an action call to another service that your service calls and set an error that the
    stubbed service action should return. This is mutually exclusive with stubbing a response body to be returned by
    the stubbed service action. This follows the standard (full) error code/field/message syntax of the error
    expectations directives, and the error field may be "none" to indicate that this error should have no field name.
    This directive applies to an entire test case. The action is stubbed before the first action case is run, and the
    stub is stopped after the last action case completes. The following use of this directive::

        stub action: user: get_user: error: code=NOT_FOUND, field=none, message=The user was not found
        stub action: user: create_user: error: code=INVALID, field=first_name, message=The first name is invalid

    Is equivalent to this Python code:

    .. code-block:: python

        with stub_action('user', 'get_user', errors=[Error(code='NOT_FOUND', message='The user was not found']), \\
                stub_action(
                    'user',
                    'create_user',
                    errors=[Error(code='INVALID', field='first_name', message='The first name is invalid')],
                ):
            # run all actions in this test
    """

    @classmethod
    def name(cls):
        return 'stub_action_error_for_test'

    @classmethod
    def get_full_grammar(cls):
        return (
            Literal('stub action') +
            ':' +
            Word(alphanums + '_')('stub_service') +
            ':' +
            Word(alphanums + '_.')('stub_action') +
            ':' +
            Literal('error') +
            ':' +
            Literal('code') +
            '=' +
            Word(alphanums + '-_')('error_code') +
            ',' +
            Literal('field') +
            '=' +
            Word(alphanums + '-_.{}[]')('field_name') +
            ',' +
            Literal('message') +
            '=' +
            restOfLine('error_message').setParseAction(lambda s, l, t: t[0].strip(' \t'))
        )

    def ingest_from_parsed_test_fixture(self, action_case, test_case, parse_results, file_name, line_number):
        _ingest_error_body(test_case, parse_results, file_name, line_number)

    def assert_test_case_action_results(*_, **__):
        pass


class StubActionErrorForActionDirective(ActionDirective):
    """
    Use this directive to stub an action call to another service that your service calls and set an error that the
    stubbed service action should return. This is mutually exclusive with stubbing a response body to be returned by
    the stubbed service action. This follows the standard (full) error code/field/message syntax of the error
    expectations directives, and the error field may be "none" to indicate that this error should have no field name.
    This directive applies to an individual action case. The action is stubbed immediately before the action case is
    run, and the stub is stopped immediately after the action case completes. The following use of this directive::

        stub action: user: get_user: error: code=NOT_FOUND, field=none, message=The user was not found
        stub action: user: create_user: error: code=INVALID, field=first_name, message=The first name is invalid

    Is equivalent to this Python code:

    .. code-block:: python

        with stub_action('user', 'get_user', errors=[Error(code='NOT_FOUND', message='The user was not found']), \\
                stub_action(
                    'user',
                    'create_user',
                    errors=[Error(code='INVALID', field='first_name', message='The first name is invalid')],
                ):
            # run all actions in this test
    """

    @classmethod
    def name(cls):
        return 'stub_action_error_for_action'

    @classmethod
    def get_full_grammar(cls):
        return (
            super(StubActionErrorForActionDirective, cls).get_full_grammar() +
            Literal('stub action') +
            ':' +
            Word(alphanums + '_')('stub_service') +
            ':' +
            Word(alphanums + '_.')('stub_action') +
            ':' +
            Literal('error') +
            ':' +
            Literal('code') +
            '=' +
            Word(alphanums + '-_')('error_code') +
            ',' +
            Literal('field') +
            '=' +
            Word(alphanums + '-_.{}[]')('field_name') +
            ',' +
            Literal('message') +
            '=' +
            restOfLine('error_message').setParseAction(lambda s, l, t: t[0].strip(' \t'))
        )

    def ingest_from_parsed_test_fixture(self, action_case, test_case, parse_results, file_name, line_number):
        _ingest_error_body(action_case, parse_results, file_name, line_number)

    def assert_test_case_action_results(*_, **__):
        pass


class AssertStubActionCalledForTestPlanDirective(Directive):
    """
    Use this directive to stub an action call to another service that your service calls and set an expectation that
    the stubbed action will be called (or not) by the test. If you use this directive without a corresponding
    `stub action ... body` or `stub action ... error` directive, the stubbed action will return an empty dict as the
    response body. You cannot combine `expect called` and `expect not called` for the same stubbed action; the two are
    mutually exclusive. If you do not specify a variable name and value, the expectation will be that the action is
    called with an empty request dict. This directive applies to an entire test case. The action is stubbed before the
    first action case is run, and the stub is stopped after the last action case completes.
    """

    @classmethod
    def name(cls):
        return 'stub_action_called_for_test'

    @classmethod
    def get_full_grammar(cls):
        return (
            Literal('stub action') +
            ':' +
            Word(alphanums + '_')('stub_service') +
            ':' +
            Word(alphanums + '_.')('stub_action') +
            ':' +
            Literal('expect') +
            Optional('not').setResultsName('not') +
            Literal('called') +
            (
                Literal(':') |
                (Optional(DataTypeGrammar) + ':' + VarNameGrammar + ':' + VarValueGrammar)
            )
        )

    def ingest_from_parsed_test_fixture(self, action_case, test_case, parse_results, file_name, line_number):
        _ingest_expect_called(test_case, parse_results, file_name, line_number)

    def set_up_test_case(self, test_case, test_fixture, **kwargs):
        _start_stubbed_actions(test_case)

    def tear_down_test_case(self, test_case, test_fixture, **kwargs):
        _stop_stubbed_actions(test_case)

    def assert_test_case_results(self, test_action_results_dict, test_case, test_fixture, msg=None, **kwargs):
        _assert_stub_expectations(test_case)

    def assert_test_case_action_results(*_, **__):
        pass


class AssertStubActionCalledForActionDirective(ActionDirective):
    """
    Use this directive to stub an action call to another service that your service calls and set an expectation that
    the stubbed action will be called (or not) by the test. If you use this directive without a corresponding
    `stub action ... body` or `stub action ... error` directive, the stubbed action will return an empty dict as the
    response body. You cannot combine `expect called` and `expect not called` for the same stubbed action; the two are
    mutually exclusive. If you do not specify a variable name and value, the expectation will be that the action is
    called with an empty request dict. This directive applies to an individual action case. The action is stubbed
    immediately before the action case is run, and the stub is stopped immediately after the action case completes.
    """

    @classmethod
    def name(cls):
        return 'stub_action_called_for_action'

    @classmethod
    def get_full_grammar(cls):
        return (
            super(AssertStubActionCalledForActionDirective, cls).get_full_grammar() +
            Literal('stub action') +
            ':' +
            Word(alphanums + '_')('stub_service') +
            ':' +
            Word(alphanums + '_.')('stub_action') +
            ':' +
            Literal('expect') +
            Optional('not').setResultsName('not') +
            Literal('called') +
            (
                Literal(':') |
                (Optional(DataTypeGrammar) + ':' + VarNameGrammar + ':' + VarValueGrammar)
            )
        )

    def ingest_from_parsed_test_fixture(self, action_case, test_case, parse_results, file_name, line_number):
        _ingest_expect_called(action_case, parse_results, file_name, line_number)

    def set_up_test_case_action(self, action_name, action_case, test_case, test_fixture, **kwargs):
        _start_stubbed_actions(action_case)

    def tear_down_test_case_action(self, action_name, action_case, test_case, test_fixture, **kwargs):
        _stop_stubbed_actions(action_case)

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
        _assert_stub_expectations(action_case)


register_directive(StubActionBodyForTestPlanDirective)
register_directive(StubActionBodyForActionDirective)
register_directive(StubActionErrorForTestPlanDirective)
register_directive(StubActionErrorForActionDirective)
register_directive(AssertStubActionCalledForTestPlanDirective)
register_directive(AssertStubActionCalledForActionDirective)
