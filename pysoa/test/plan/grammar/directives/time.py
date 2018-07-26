"""
Directives for freezing time during test execution
"""
from __future__ import (
    absolute_import,
    unicode_literals,
)

import datetime

from pyparsing import Literal

from pysoa.test.plan.errors import FixtureSyntaxError
from pysoa.test.plan.grammar.directive import (
    ActionDirective,
    Directive,
    VarValueGrammar,
    register_directive,
)


try:
    from freezegun import freeze_time
except ImportError:
    freeze_time = None


class FreezeTimeMixin(object):
    @staticmethod
    def parse_and_store_freeze_to(target, value, file_name, line_number):
        if not freeze_time:
            raise FixtureSyntaxError(
                'Could not import freezegun to support freeze time syntax. Perhaps you need to install it?',
                file_name,
                line_number,
            )

        if value == 'now':
            freeze_to = None
        else:
            try:
                freeze_to = datetime.datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ')
            except ValueError:
                raise FixtureSyntaxError('Could not parse datetime value for time freeze', file_name, line_number)

        target['_freezegun_freeze_time'] = freeze_to

    @staticmethod
    def start_freeze(target):
        if '_freezegun_freeze_time' in target:
            target['_freezegun_context'] = freeze_time(target['_freezegun_freeze_time'])
            target['_freezegun_context'].start()

    @staticmethod
    def stop_freeze(target):
        if '_freezegun_context' in target:
            target['_freezegun_context'].stop()
            del target['_freezegun_context']


class FreezeTimeTestPlanDirective(Directive, FreezeTimeMixin):
    """
    Freeze Time using freezegun for the duration of an entire test plan.

    This will span all actions within the plan, no matter where the statement is located.
    """

    @classmethod
    def name(cls):
        return 'freeze_time_test'

    @classmethod
    def get_full_grammar(cls):
        return (
            Literal('freeze time') +
            ':' +
            VarValueGrammar
        )

    def ingest_from_parsed_test_fixture(self, action_case, test_case, parse_results, file_name, line_number):
        self.parse_and_store_freeze_to(test_case, parse_results.value, file_name, line_number)
        self.start_freeze(test_case)

    def post_parse_test_case(self, test_case):
        self.stop_freeze(test_case)

    def set_up_test_case(self, test_case, test_fixture, **kwargs):
        self.start_freeze(test_case)

    def tear_down_test_case(self, test_case, test_fixture, **kwargs):
        self.stop_freeze(test_case)

    def assert_test_case_action_results(self, *args, **kwargs):
        pass


class FreezeTimeActionDirective(ActionDirective, FreezeTimeMixin):
    """
    Freeze Time using freezegun for the duration of a single action.
    """

    @classmethod
    def name(cls):
        return 'freeze_time_action'

    @classmethod
    def get_full_grammar(cls):
        return (
            super(FreezeTimeActionDirective, cls).get_full_grammar() +
            Literal('freeze time') +
            ':' +
            VarValueGrammar
        )

    def ingest_from_parsed_test_fixture(self, action_case, test_case, parse_results, file_name, line_number):
        self.parse_and_store_freeze_to(action_case, parse_results.value, file_name, line_number)
        self.start_freeze(action_case)

    def post_parse_test_case_action(self, action_case, test_case):
        self.stop_freeze(action_case)

    def set_up_test_case_action(self, action_name, action_case, test_case, test_fixture, **kwargs):
        self.start_freeze(action_case)

    def tear_down_test_case_action(self, action_name, action_case, test_case, test_fixture, **kwargs):
        self.stop_freeze(action_case)

    def assert_test_case_action_results(self, *args, **kwargs):
        pass


register_directive(FreezeTimeTestPlanDirective)
register_directive(FreezeTimeActionDirective)
