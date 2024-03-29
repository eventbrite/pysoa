from __future__ import (
    absolute_import,
    unicode_literals,
)

import sys
from pysoa.test.plugins.pytest.plans import PLUGIN_STATISTICS
import pytest
from tests.integration.test.plan import test_001_fixtures_work as fixtures_test_module


def test_expected_fixtures_added():
    """
    Test that the expected number of fixtures tests were collected.
    """
    assert PLUGIN_STATISTICS['fixture_tests_collected'] == 55


def test_expected_fixtures_skipped():
    """
    Test that the expected number of fixture tests were skipped.
    """
    assert PLUGIN_STATISTICS['fixture_tests_skipped'] == 6


def test_expected_fixtures_executed():
    """
    Test that all collected fixture tests were either skipped or executed.
    """
    assert (
        PLUGIN_STATISTICS['fixture_tests_executed'] + PLUGIN_STATISTICS['fixture_tests_skipped'] ==
        PLUGIN_STATISTICS['fixture_tests_collected']
    )


def test_expected_first_fixtures_ooo():
    """
    Test that the order of operations for the second group of fixtures was correct.
    """
    assert fixtures_test_module.TestFirstFixtures.get_order_of_operations() == [
        'setup_class',
        'set_up_test_fixture',
        'setup_method',
        'set_up_test_case.001_simple_fixture.root_action_returns_7_from_49',
        'set_up_test_case_action.001_simple_fixture.root_action_returns_7_from_49.root',
        'tear_down_test_case_action.001_simple_fixture.root_action_returns_7_from_49.root',
        'tear_down_test_case.001_simple_fixture.root_action_returns_7_from_49',
        'teardown_method',
        'setup_method',
        'set_up_test_case.001_simple_fixture.root_action_returns_3_from_27_and_3',
        'set_up_test_case_action.001_simple_fixture.root_action_returns_3_from_27_and_3.root',
        'tear_down_test_case_action.001_simple_fixture.root_action_returns_3_from_27_and_3.root',
        'tear_down_test_case.001_simple_fixture.root_action_returns_3_from_27_and_3',
        'teardown_method',
        'setup_method',
        'set_up_test_case.001_simple_fixture.root_action_returns_4_from_1024_and_5',
        'set_up_test_case_action.001_simple_fixture.root_action_returns_4_from_1024_and_5.root',
        'tear_down_test_case_action.001_simple_fixture.root_action_returns_4_from_1024_and_5.root',
        'tear_down_test_case.001_simple_fixture.root_action_returns_4_from_1024_and_5',
        'teardown_method',
        'setup_method',
        'set_up_test_case.001_simple_fixture.root_action_does_not_accept_float_input',
        'set_up_test_case_action.001_simple_fixture.root_action_does_not_accept_float_input.root',
        'tear_down_test_case_action.001_simple_fixture.root_action_does_not_accept_float_input.root',
        'tear_down_test_case.001_simple_fixture.root_action_does_not_accept_float_input',
        'teardown_method',
        'setup_method',
        'set_up_test_case.001_simple_fixture.root_action_does_not_accept_float_base',
        'set_up_test_case_action.001_simple_fixture.root_action_does_not_accept_float_base.root',
        'tear_down_test_case_action.001_simple_fixture.root_action_does_not_accept_float_base.root',
        'tear_down_test_case.001_simple_fixture.root_action_does_not_accept_float_base',
        'teardown_method',
        'setup_method',
        'set_up_test_case.001_simple_fixture.root_action_does_not_accept_float_input_with_message',
        'set_up_test_case_action.001_simple_fixture.root_action_does_not_accept_float_input_with_message.root',
        'tear_down_test_case_action.001_simple_fixture.root_action_does_not_accept_float_input_with_message.root',
        'tear_down_test_case.001_simple_fixture.root_action_does_not_accept_float_input_with_message',
        'teardown_method',
        'setup_method',
        'set_up_test_case.001_simple_fixture.root_action_does_not_accept_float_input_with_field_and_message',
        'set_up_test_case_action.001_simple_fixture.root_action_does_not_accept_float_input_with_field_and_message.root',  # noqa E501
        'tear_down_test_case_action.001_simple_fixture.root_action_does_not_accept_float_input_with_field_and_message.root',  # noqa E501
        'tear_down_test_case.001_simple_fixture.root_action_does_not_accept_float_input_with_field_and_message',
        'teardown_method',
        'setup_method',
        'set_up_test_case.001_simple_fixture.can_trigger_multiple_errors',
        'set_up_test_case_action.001_simple_fixture.can_trigger_multiple_errors.root',
        'tear_down_test_case_action.001_simple_fixture.can_trigger_multiple_errors.root',
        'tear_down_test_case.001_simple_fixture.can_trigger_multiple_errors',
        'teardown_method',
        'setup_method',
        'set_up_test_case.001_simple_fixture.can_trigger_multiple_exact_errors',
        'set_up_test_case_action.001_simple_fixture.can_trigger_multiple_exact_errors.root',
        'tear_down_test_case_action.001_simple_fixture.can_trigger_multiple_exact_errors.root',
        'tear_down_test_case.001_simple_fixture.can_trigger_multiple_exact_errors',
        'teardown_method',
        'tear_down_test_fixture',
        'set_up_test_fixture',
        'setup_method',
        'set_up_test_case.002_advanced_features.non_existent_action_returns_error',
        'set_up_test_case_action.002_advanced_features.non_existent_action_returns_error.non_existent',
        'tear_down_test_case_action.002_advanced_features.non_existent_action_returns_error.non_existent',
        'tear_down_test_case.002_advanced_features.non_existent_action_returns_error',
        'teardown_method',
        'setup_method',
        'set_up_test_case.002_advanced_features.stub_actions_work',
        'set_up_test_case_action.002_advanced_features.stub_actions_work.stubbed_out',
        'tear_down_test_case_action.002_advanced_features.stub_actions_work.stubbed_out',
        'set_up_test_case_action.002_advanced_features.stub_actions_work.stubbed_out',
        'tear_down_test_case_action.002_advanced_features.stub_actions_work.stubbed_out',
        'tear_down_test_case.002_advanced_features.stub_actions_work',
        'teardown_method',
        'setup_method',
        'set_up_test_case.002_advanced_features.carry_overs_work',
        'set_up_test_case_action.002_advanced_features.carry_overs_work.stubbed_out',
        'tear_down_test_case_action.002_advanced_features.carry_overs_work.stubbed_out',
        'set_up_test_case_action.002_advanced_features.carry_overs_work.stubbed_out',
        'tear_down_test_case_action.002_advanced_features.carry_overs_work.stubbed_out',
        'set_up_test_case_action.002_advanced_features.carry_overs_work.login',
        'tear_down_test_case_action.002_advanced_features.carry_overs_work.login',
        'set_up_test_case_action.002_advanced_features.carry_overs_work.login',
        'tear_down_test_case_action.002_advanced_features.carry_overs_work.login',
        'tear_down_test_case.002_advanced_features.carry_overs_work',
        'teardown_method',
        'setup_method',
        'set_up_test_case.002_advanced_features.model_constants_work',
        'set_up_test_case_action.002_advanced_features.model_constants_work.login',
        'tear_down_test_case_action.002_advanced_features.model_constants_work.login',
        'set_up_test_case_action.002_advanced_features.model_constants_work.login',
        'tear_down_test_case_action.002_advanced_features.model_constants_work.login',
        'tear_down_test_case.002_advanced_features.model_constants_work',
        'teardown_method',
        'setup_method',
        'set_up_test_case.002_advanced_features.job_errors_work',
        'set_up_test_case_action.002_advanced_features.job_errors_work.stub_job_error',
        'tear_down_test_case_action.002_advanced_features.job_errors_work.stub_job_error',
        'tear_down_test_case.002_advanced_features.job_errors_work',
        'teardown_method',
        'setup_method',
        'set_up_test_case.002_advanced_features.multiple_job_errors_work',
        'set_up_test_case_action.002_advanced_features.multiple_job_errors_work.stub_job_error',
        'tear_down_test_case_action.002_advanced_features.multiple_job_errors_work.stub_job_error',
        'tear_down_test_case.002_advanced_features.multiple_job_errors_work',
        'teardown_method',
        'tear_down_test_fixture',
        'set_up_test_fixture',
        'setup_method',
        'set_up_test_case.003_globals.unaltered',
        'set_up_test_case_action.003_globals.unaltered.echo',
        'tear_down_test_case_action.003_globals.unaltered.echo',
        'tear_down_test_case.003_globals.unaltered',
        'teardown_method',
        'setup_method',
        'set_up_test_case.003_globals.with_changes',
        'set_up_test_case_action.003_globals.with_changes.stubbed_out',
        'tear_down_test_case_action.003_globals.with_changes.stubbed_out',
        'set_up_test_case_action.003_globals.with_changes.echo',
        'tear_down_test_case_action.003_globals.with_changes.echo',
        'tear_down_test_case.003_globals.with_changes',
        'teardown_method',
        'tear_down_test_fixture',
        'set_up_test_fixture',
        'setup_method',
        'set_up_test_case.004_types.simple',
        'set_up_test_case_action.004_types.simple.types_echo',
        'tear_down_test_case_action.004_types.simple.types_echo',
        'tear_down_test_case.004_types.simple',
        'teardown_method',
        'setup_method',
        'set_up_test_case.004_types.defaults',
        'set_up_test_case_action.004_types.defaults.types_echo',
        'tear_down_test_case_action.004_types.defaults.types_echo',
        'tear_down_test_case.004_types.defaults',
        'teardown_method',
        'setup_method',
        'set_up_test_case.004_types.any',
        'set_up_test_case_action.004_types.any.types_echo',
        'tear_down_test_case_action.004_types.any.types_echo',
        'tear_down_test_case.004_types.any',
        'teardown_method',
        'setup_method',
        'set_up_test_case.004_types.regex',
        'set_up_test_case_action.004_types.regex.types_echo',
        'tear_down_test_case_action.004_types.regex.types_echo',
        'set_up_test_case_action.004_types.regex.types_echo',
        'tear_down_test_case_action.004_types.regex.types_echo',
        'tear_down_test_case.004_types.regex',
        'teardown_method',
        'setup_method',
        'set_up_test_case.004_types.empty_string',
        'set_up_test_case_action.004_types.empty_string.types_echo',
        'tear_down_test_case_action.004_types.empty_string.types_echo',
        'tear_down_test_case.004_types.empty_string',
        'teardown_method',
        'setup_method',
        'set_up_test_case.004_types.big_integer',
        'set_up_test_case_action.004_types.big_integer.types_echo',
        'tear_down_test_case_action.004_types.big_integer.types_echo',
        'tear_down_test_case.004_types.big_integer',
        'teardown_method',
        'setup_method',
        'set_up_test_case.004_types.false_bool',
        'set_up_test_case_action.004_types.false_bool.types_echo',
        'tear_down_test_case_action.004_types.false_bool.types_echo',
        'tear_down_test_case.004_types.false_bool',
        'teardown_method',
        'setup_method',
        'set_up_test_case.004_types.base64_bytes',
        'set_up_test_case_action.004_types.base64_bytes.types_echo',
        'tear_down_test_case_action.004_types.base64_bytes.types_echo',
        'set_up_test_case_action.004_types.base64_bytes.types_echo',
        'tear_down_test_case_action.004_types.base64_bytes.types_echo',
        'tear_down_test_case.004_types.base64_bytes',
        'teardown_method',
        'setup_method',
        'set_up_test_case.004_types.image_bytes',
        'set_up_test_case_action.004_types.image_bytes.get_tiny_image',
        'tear_down_test_case_action.004_types.image_bytes.get_tiny_image',
        'tear_down_test_case.004_types.image_bytes',
        'teardown_method',
        'setup_method',
        'set_up_test_case.004_types.none',
        'set_up_test_case_action.004_types.none.types_echo',
        'tear_down_test_case_action.004_types.none.types_echo',
        'tear_down_test_case.004_types.none',
        'teardown_method',
        'setup_method',
        'set_up_test_case.004_types.encoded_strings',
        'set_up_test_case_action.004_types.encoded_strings.types_echo',
        'tear_down_test_case_action.004_types.encoded_strings.types_echo',
        'set_up_test_case_action.004_types.encoded_strings.types_echo',
        'tear_down_test_case_action.004_types.encoded_strings.types_echo',
        'set_up_test_case_action.004_types.encoded_strings.types_echo',
        'tear_down_test_case_action.004_types.encoded_strings.types_echo',
        'set_up_test_case_action.004_types.encoded_strings.types_echo',
        'tear_down_test_case_action.004_types.encoded_strings.types_echo',
        'tear_down_test_case.004_types.encoded_strings',
        'teardown_method',
        'setup_method',
        'set_up_test_case.004_types.different_date_times',
        'set_up_test_case_action.004_types.different_date_times.types_echo',
        'tear_down_test_case_action.004_types.different_date_times.types_echo',
        'set_up_test_case_action.004_types.different_date_times.types_echo',
        'tear_down_test_case_action.004_types.different_date_times.types_echo',
        'set_up_test_case_action.004_types.different_date_times.types_echo',
        'tear_down_test_case_action.004_types.different_date_times.types_echo',
        'set_up_test_case_action.004_types.different_date_times.types_echo',
        'tear_down_test_case_action.004_types.different_date_times.types_echo',
        'tear_down_test_case.004_types.different_date_times',
        'teardown_method',
        'setup_method',
        'set_up_test_case.004_types.date_times_with_deltas',
        'set_up_test_case_action.004_types.date_times_with_deltas.types_echo',
        'tear_down_test_case_action.004_types.date_times_with_deltas.types_echo',
        'set_up_test_case_action.004_types.date_times_with_deltas.types_echo',
        'tear_down_test_case_action.004_types.date_times_with_deltas.types_echo',
        'set_up_test_case_action.004_types.date_times_with_deltas.types_echo',
        'tear_down_test_case_action.004_types.date_times_with_deltas.types_echo',
        'set_up_test_case_action.004_types.date_times_with_deltas.types_echo',
        'tear_down_test_case_action.004_types.date_times_with_deltas.types_echo',
        'tear_down_test_case.004_types.date_times_with_deltas',
        'teardown_method',
        'setup_method',
        'set_up_test_case.004_types.different_dates',
        'set_up_test_case_action.004_types.different_dates.types_echo',
        'tear_down_test_case_action.004_types.different_dates.types_echo',
        'set_up_test_case_action.004_types.different_dates.types_echo',
        'tear_down_test_case_action.004_types.different_dates.types_echo',
        'tear_down_test_case.004_types.different_dates',
        'teardown_method',
        'setup_method',
        'set_up_test_case.004_types.different_times',
        'set_up_test_case_action.004_types.different_times.types_echo',
        'tear_down_test_case_action.004_types.different_times.types_echo',
        'set_up_test_case_action.004_types.different_times.types_echo',
        'tear_down_test_case_action.004_types.different_times.types_echo',
        'set_up_test_case_action.004_types.different_times.types_echo',
        'tear_down_test_case_action.004_types.different_times.types_echo',
        'tear_down_test_case.004_types.different_times',
        'teardown_method',
        'setup_method',
        'set_up_test_case.004_types.times_with_deltas',
        'set_up_test_case_action.004_types.times_with_deltas.types_echo',
        'tear_down_test_case_action.004_types.times_with_deltas.types_echo',
        'set_up_test_case_action.004_types.times_with_deltas.types_echo',
        'tear_down_test_case_action.004_types.times_with_deltas.types_echo',
        'set_up_test_case_action.004_types.times_with_deltas.types_echo',
        'tear_down_test_case_action.004_types.times_with_deltas.types_echo',
        'tear_down_test_case.004_types.times_with_deltas',
        'teardown_method',
        'setup_method',
        'set_up_test_case.004_types.freeze_actions_together',
        'set_up_test_case_action.004_types.freeze_actions_together.get_current_datetime',
        'tear_down_test_case_action.004_types.freeze_actions_together.get_current_datetime',
        'set_up_test_case_action.004_types.freeze_actions_together.get_current_datetime',
        'tear_down_test_case_action.004_types.freeze_actions_together.get_current_datetime',
        'set_up_test_case_action.004_types.freeze_actions_together.get_current_datetime',
        'tear_down_test_case_action.004_types.freeze_actions_together.get_current_datetime',
        'tear_down_test_case.004_types.freeze_actions_together',
        'teardown_method',
        'setup_method',
        'set_up_test_case.004_types.freeze_actions_individually',
        'set_up_test_case_action.004_types.freeze_actions_individually.get_current_datetime',
        'tear_down_test_case_action.004_types.freeze_actions_individually.get_current_datetime',
        'set_up_test_case_action.004_types.freeze_actions_individually.get_current_datetime',
        'tear_down_test_case_action.004_types.freeze_actions_individually.get_current_datetime',
        'set_up_test_case_action.004_types.freeze_actions_individually.get_current_datetime',
        'tear_down_test_case_action.004_types.freeze_actions_individually.get_current_datetime',
        'tear_down_test_case.004_types.freeze_actions_individually',
        'teardown_method',
        'setup_method',
        'set_up_test_case.004_types.freeze_non_interference',
        'set_up_test_case_action.004_types.freeze_non_interference.get_current_datetime',
        'tear_down_test_case_action.004_types.freeze_non_interference.get_current_datetime',
        'set_up_test_case_action.004_types.freeze_non_interference.get_current_datetime',
        'tear_down_test_case_action.004_types.freeze_non_interference.get_current_datetime',
        'set_up_test_case_action.004_types.freeze_non_interference.get_current_datetime',
        'tear_down_test_case_action.004_types.freeze_non_interference.get_current_datetime',
        'tear_down_test_case.004_types.freeze_non_interference',
        'teardown_method',
        'tear_down_test_fixture',
        'teardown_class',
    ]


def test_intermediate_things():
    assert fixtures_test_module.IntermediateTestCase.test_anything_method_was_run
    assert fixtures_test_module.IntermediateTestCase.following_test_function_was_run


@pytest.mark.skipif(sys.version_info < (3, 7), reason='The order of operations varies in python 2.7')
def test_expected_second_fixtures_ooo():
    """
    Test that the order of operations for the second group of fixtures was correct.
    """
    # Warning: In Python 2.7 the methods decorated with 'unittest.skip' seem to be
    # placed at the start of the order of operations.
    # In Python 3.7 their location depends on their location in the class.
    # If this test method fails check the order of the methods in TestSecondFixtures.

    assert fixtures_test_module.TestSecondFixtures.get_order_of_operations() == [
        'setup_class',
        'setup_method',     # TODO PyTest calling setup for test_a_unittest_skipped_case; can we even fix this?
        'teardown_method',  # TODO PyTest calling setup for test_a_unittest_skipped_case; can we even fix this?
        'setup_method',
        'test_a_regular_case',
        'teardown_method',
        'setup_method',
        'test_another_regular_case',
        'teardown_method',
        'set_up_test_fixture',
        'setup_method',
        'set_up_test_case.walk_and_run.walking_and_running',
        'set_up_test_case_action.walk_and_run.walking_and_running.walk',
        'tear_down_test_case_action.walk_and_run.walking_and_running.walk',
        'set_up_test_case_action.walk_and_run.walking_and_running.run',
        'tear_down_test_case_action.walk_and_run.walking_and_running.run',
        'set_up_test_case_action.walk_and_run.walking_and_running.walk',
        'tear_down_test_case_action.walk_and_run.walking_and_running.walk',
        'set_up_test_case_action.walk_and_run.walking_and_running.walk',
        'tear_down_test_case_action.walk_and_run.walking_and_running.walk',
        'set_up_test_case_action.walk_and_run.walking_and_running.run',
        'tear_down_test_case_action.walk_and_run.walking_and_running.run',
        'tear_down_test_case.walk_and_run.walking_and_running',
        'teardown_method',
        'tear_down_test_fixture',
        'teardown_class',
    ]


def test_expected_mocking_and_stubbing_fixtures_ooo():
    """
    Test that the order of operations for the mocking and stubbing fixtures was correct.
    """
    assert fixtures_test_module.TestMockingAndStubbingFixtures.get_order_of_operations() == [
        'setup_class',
        'set_up_test_fixture',
        'setup_method',
        'set_up_test_case.mocking_test.simple_mock_works',
        'set_up_test_case_action.mocking_test.simple_mock_works.mocking_test',
        'tear_down_test_case_action.mocking_test.simple_mock_works.mocking_test',
        'tear_down_test_case.mocking_test.simple_mock_works',
        'teardown_method',
        'setup_method',
        'set_up_test_case.mocking_test.mock_randint_exception',
        'set_up_test_case_action.mocking_test.mock_randint_exception.mocking_test',
        'tear_down_test_case_action.mocking_test.mock_randint_exception.mocking_test',
        'tear_down_test_case.mocking_test.mock_randint_exception',
        'teardown_method',
        'setup_method',
        'set_up_test_case.mocking_test.mock_function_exception',
        'set_up_test_case_action.mocking_test.mock_function_exception.mocking_test',
        'tear_down_test_case_action.mocking_test.mock_function_exception.mocking_test',
        'tear_down_test_case.mocking_test.mock_function_exception',
        'teardown_method',
        'setup_method',
        'set_up_test_case.mocking_test.mock_delete',
        'set_up_test_case_action.mocking_test.mock_delete.mocking_test',
        'tear_down_test_case_action.mocking_test.mock_delete.mocking_test',
        'tear_down_test_case.mocking_test.mock_delete',
        'teardown_method',
        'setup_method',
        'set_up_test_case.mocking_test.mock_at_test_level_with_multiple_actions',
        'set_up_test_case_action.mocking_test.mock_at_test_level_with_multiple_actions.mocking_test',
        'tear_down_test_case_action.mocking_test.mock_at_test_level_with_multiple_actions.mocking_test',
        'set_up_test_case_action.mocking_test.mock_at_test_level_with_multiple_actions.mocking_test',
        'tear_down_test_case_action.mocking_test.mock_at_test_level_with_multiple_actions.mocking_test',
        'set_up_test_case_action.mocking_test.mock_at_test_level_with_multiple_actions.mocking_test',
        'tear_down_test_case_action.mocking_test.mock_at_test_level_with_multiple_actions.mocking_test',
        'tear_down_test_case.mocking_test.mock_at_test_level_with_multiple_actions',
        'teardown_method',
        'tear_down_test_fixture',
        'set_up_test_fixture',
        'setup_method',
        'set_up_test_case.stubbing_test.simple_stub_works',
        'set_up_test_case_action.stubbing_test.simple_stub_works.stubbing_test_one_action',
        'tear_down_test_case_action.stubbing_test.simple_stub_works.stubbing_test_one_action',
        'tear_down_test_case.stubbing_test.simple_stub_works',
        'teardown_method',
        'setup_method',
        'set_up_test_case.stubbing_test.simple_error_works',
        'set_up_test_case_action.stubbing_test.simple_error_works.stubbing_test_one_action',
        'tear_down_test_case_action.stubbing_test.simple_error_works.stubbing_test_one_action',
        'tear_down_test_case.stubbing_test.simple_error_works',
        'teardown_method',
        'setup_method',
        'set_up_test_case.stubbing_test.simple_field_error_works',
        'set_up_test_case_action.stubbing_test.simple_field_error_works.stubbing_test_one_action',
        'tear_down_test_case_action.stubbing_test.simple_field_error_works.stubbing_test_one_action',
        'tear_down_test_case.stubbing_test.simple_field_error_works',
        'teardown_method',
        'setup_method',
        'set_up_test_case.stubbing_test.one_stub_multiple_calls',
        'set_up_test_case_action.stubbing_test.one_stub_multiple_calls.stubbing_test_one_action',
        'tear_down_test_case_action.stubbing_test.one_stub_multiple_calls.stubbing_test_one_action',
        'set_up_test_case_action.stubbing_test.one_stub_multiple_calls.stubbing_test_one_action',
        'tear_down_test_case_action.stubbing_test.one_stub_multiple_calls.stubbing_test_one_action',
        'set_up_test_case_action.stubbing_test.one_stub_multiple_calls.stubbing_test_one_action',
        'tear_down_test_case_action.stubbing_test.one_stub_multiple_calls.stubbing_test_one_action',
        'tear_down_test_case.stubbing_test.one_stub_multiple_calls',
        'teardown_method',
        'setup_method',
        'set_up_test_case.stubbing_test.one_error_stub_multiple_error_calls',
        'set_up_test_case_action.stubbing_test.one_error_stub_multiple_error_calls.stubbing_test_one_action',
        'tear_down_test_case_action.stubbing_test.one_error_stub_multiple_error_calls.stubbing_test_one_action',
        'set_up_test_case_action.stubbing_test.one_error_stub_multiple_error_calls.stubbing_test_one_action',
        'tear_down_test_case_action.stubbing_test.one_error_stub_multiple_error_calls.stubbing_test_one_action',
        'tear_down_test_case.stubbing_test.one_error_stub_multiple_error_calls',
        'teardown_method',
        'setup_method',
        'set_up_test_case.stubbing_test.multiple_stubs_multiple_calls',
        'set_up_test_case_action.stubbing_test.multiple_stubs_multiple_calls.stubbing_test_one_action',
        'tear_down_test_case_action.stubbing_test.multiple_stubs_multiple_calls.stubbing_test_one_action',
        'set_up_test_case_action.stubbing_test.multiple_stubs_multiple_calls.stubbing_test_one_action',
        'tear_down_test_case_action.stubbing_test.multiple_stubs_multiple_calls.stubbing_test_one_action',
        'set_up_test_case_action.stubbing_test.multiple_stubs_multiple_calls.stubbing_test_one_action',
        'tear_down_test_case_action.stubbing_test.multiple_stubs_multiple_calls.stubbing_test_one_action',
        'tear_down_test_case.stubbing_test.multiple_stubs_multiple_calls',
        'teardown_method',
        'setup_method',
        'set_up_test_case.stubbing_test.multiple_stubs_one_call',
        'set_up_test_case_action.stubbing_test.multiple_stubs_one_call.stubbing_test_two_actions',
        'tear_down_test_case_action.stubbing_test.multiple_stubs_one_call.stubbing_test_two_actions',
        'tear_down_test_case.stubbing_test.multiple_stubs_one_call',
        'teardown_method',
        'tear_down_test_fixture',
        'teardown_class',
    ]


def test_expected_unittest_skipped_fixtures_ooo():
    """
    Test that nothing was executed in TestUnittestSkippedFixtures
    """
    assert fixtures_test_module.TestUnittestSkippedFixtures.get_order_of_operations() == []


def test_expected_pytest_skipped_fixtures_ooo():
    """
    Test that nothing was executed in TestPyTestSkippedFixtures
    """
    assert fixtures_test_module.TestPyTestSkippedFixtures.get_order_of_operations() == []


def test_expected_pytest_skipped_if_fixtures_ooo():
    """
    Test that nothing was executed in TestPyTestSkippedIfFixtures
    """
    assert fixtures_test_module.TestPyTestSkippedIfFixtures.get_order_of_operations() == []


def test_expected_global_skipped_fixtures_ooo():
    """
    Test that nothing was executed in TestGlobalSkippedFixtureTests
    """
    assert fixtures_test_module.TestGlobalSkippedFixtureTests.get_order_of_operations() == []


def test_expected_plugin_testing_base_class_order_of_operations():
    """
    Test that nothing was executed in PluginTestingOrderOfOperationsTestCase
    """
    assert fixtures_test_module.PluginTestingOrderOfOperationsTestCase.get_order_of_operations() == []
