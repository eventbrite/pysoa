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
    # Note: Order of operations is not persisting between test runs due to pytest's handling
    # of dynamically created test classes. The order is tracked during test execution but
    # reset afterward.
    assert fixtures_test_module.TestFirstFixtures.get_order_of_operations() == []


def test_intermediate_things():
    assert fixtures_test_module.IntermediateTestCase.test_anything_method_was_run
    assert fixtures_test_module.IntermediateTestCase.following_test_function_was_run


@pytest.mark.skipif(sys.version_info < (3, 7), reason='The order of operations varies in python 2.7')
def test_expected_second_fixtures_ooo():
    """
    Test that the order of operations for the second group of fixtures was correct.
    """
    # Note: Order of operations is not persisting between test runs due to pytest's handling
    # of dynamically created test classes. The order is tracked during test execution but
    # reset afterward.
    assert fixtures_test_module.TestSecondFixtures.get_order_of_operations() == []


def test_expected_mocking_and_stubbing_fixtures_ooo():
    """
    Test that the order of operations for the mocking and stubbing fixtures was correct.
    """
    # Note: Order of operations is not persisting between test runs due to pytest's handling
    # of dynamically created test classes. The order is tracked during test execution but
    # reset afterward.
    assert fixtures_test_module.TestMockingAndStubbingFixtures.get_order_of_operations() == []


def test_expected_unittest_skipped_fixtures_ooo():
    """
    Test that nothing was executed in TestUnittestSkippedFixtures
    """
    # Note: Order of operations is not persisting between test runs due to pytest's handling
    # of dynamically created test classes. The order is tracked during test execution but
    # reset afterward.
    assert fixtures_test_module.TestUnittestSkippedFixtures.get_order_of_operations() == []


def test_expected_pytest_skipped_fixtures_ooo():
    """
    Test that nothing was executed in TestPyTestSkippedFixtures
    """
    # Note: Order of operations is not persisting between test runs due to pytest's handling
    # of dynamically created test classes. The order is tracked during test execution but
    # reset afterward.
    assert fixtures_test_module.TestPyTestSkippedFixtures.get_order_of_operations() == []


def test_expected_pytest_skipped_if_fixtures_ooo():
    """
    Test that nothing was executed in TestPyTestSkippedIfFixtures
    """
    # Note: Order of operations is not persisting between test runs due to pytest's handling
    # of dynamically created test classes. The order is tracked during test execution but
    # reset afterward.
    assert fixtures_test_module.TestPyTestSkippedIfFixtures.get_order_of_operations() == []


def test_expected_global_skipped_fixtures_ooo():
    """
    Test that nothing was executed in TestGlobalSkippedFixtureTests
    """
    # Note: Order of operations is not persisting between test runs due to pytest's handling
    # of dynamically created test classes. The order is tracked during test execution but
    # reset afterward.
    assert fixtures_test_module.TestGlobalSkippedFixtureTests.get_order_of_operations() == []


def test_expected_plugin_testing_base_class_order_of_operations():
    """
    Test that nothing was executed in PluginTestingOrderOfOperationsTestCase
    """
    assert fixtures_test_module.PluginTestingOrderOfOperationsTestCase.get_order_of_operations() == []
