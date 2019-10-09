from __future__ import (
    absolute_import,
    unicode_literals,
)

import unittest

from pysoa.common.errors import Error
from pysoa.test.plan.grammar import assertions
from pysoa.test.plan.grammar.data_types import AnyValue


# noinspection PyTypeChecker
class TestCustomAssertions(unittest.TestCase):
    def test_assert_not_wanted_full_match(self):
        with self.assertRaises(AssertionError):
            assertions.assert_not_expected(
                {
                    'foo': 'bar',
                    'blah': ['aa', 'bb'],
                },
                {
                    'foo': 'bar',
                    'blah': ['aa', 'bb'],
                },
            )

    def test_assert_not_wanted_complete_mismatch(self):
        assertions.assert_not_expected(
            {
                'foo': 'bar',
                'blah': ['aa', 'bb'],
            },
            {
                'zoom': 'bar',
            },
        )

    def test_assert_not_wanted_partial_match(self):
        with self.assertRaises(AssertionError):
            assertions.assert_not_expected(
                {
                    'foo': 'bar',
                    'blah': ['aa', 'bb'],
                },
                {
                    'blah': ['bb']
                },
            )

    def test_assert_not_wanted_errors_array_empty(self):
        assertions.assert_actual_list_not_subset(
            [Error(code='INVALID', message=AnyValue('str'), field=AnyValue('str', permit_none=True))],  # type: ignore
            [],
        )

    def test_assert_not_wanted_errors_mismatch_list(self):
        assertions.assert_actual_list_not_subset(
            [
                Error(code='FOO', message=AnyValue('str'), field=AnyValue('str', permit_none=True)),  # type: ignore
                Error(code='BAR', message=AnyValue('str'), field=AnyValue('str', permit_none=True)),  # type: ignore
            ],
            [
                Error(code='BAZ', message='Baz message', field=None),
            ],
        )

    def test_assert_not_wanted_errors_match_list_no_field(self):
        with self.assertRaises(AssertionError):
            assertions.assert_actual_list_not_subset(
                [
                    Error(code='FOO', message=AnyValue('str'), field=AnyValue('str', permit_none=True)),  # type: ignore
                    Error(code='BAR', message=AnyValue('str'), field=AnyValue('str', permit_none=True)),  # type: ignore
                ],
                [
                    Error(code='BAR', message='Bar message', field=None),
                ],
            )

    def test_assert_not_wanted_errors_match_list_with_field(self):
        with self.assertRaises(AssertionError):
            assertions.assert_actual_list_not_subset(
                [
                    Error(code='FOO', message=AnyValue('str'), field=AnyValue('str', permit_none=True)),  # type: ignore
                    Error(code='BAR', message=AnyValue('str'), field=AnyValue('str', permit_none=True)),  # type: ignore
                ],
                [
                    Error(code='FOO', message='Foo message', field='foo_field'),
                ],
            )

    def test_assert_not_wanted_errors_match_list_with_field_and_extras(self):
        with self.assertRaises(AssertionError):
            assertions.assert_actual_list_not_subset(
                [
                    Error(code='FOO', message=AnyValue('str'), field=AnyValue('str', permit_none=True)),  # type: ignore
                    Error(code='BAR', message=AnyValue('str'), field=AnyValue('str', permit_none=True)),  # type: ignore
                ],
                [
                    Error(code='FOO', message='Foo message', field='foo_field'),
                    Error(code='BAZ', message='Baz message', field=None),
                ],
            )

    def test_assert_not_wanted_errors_mismatch_message(self):
        assertions.assert_actual_list_not_subset(
            [
                Error(code='FOO', message=AnyValue('str'), field=AnyValue('str', permit_none=True)),  # type: ignore
                Error(code='BAR', message='Bar message', field=AnyValue('str', permit_none=True)),  # type: ignore
            ],
            [
                Error(code='BAR', message='Qux message', field=None),
            ],
        )

    def test_assert_not_wanted_errors_mismatch_field(self):
        assertions.assert_actual_list_not_subset(
            [
                Error(code='FOO', message=AnyValue('str'), field=AnyValue('str', permit_none=True)),  # type: ignore
                Error(code='BAR', message=AnyValue('str'), field='bar_field'),  # type: ignore
            ],
            [
                Error(code='BAR', message='Bar message', field=None),
            ],
        )

    def test_assert_all_wanted_errors_mismatch_empty_list(self):
        with self.assertRaises(AssertionError):
            assertions.assert_lists_match_any_order(
                [
                    Error(code='FOO', message=AnyValue('str'), field=AnyValue('str', permit_none=True)),  # type: ignore
                    Error(code='BAR', message=AnyValue('str'), field=AnyValue('str', permit_none=True)),  # type: ignore
                ],
                [],
            )

    def test_assert_all_wanted_errors_mismatch_empty_list_other_way(self):
        with self.assertRaises(AssertionError):
            assertions.assert_lists_match_any_order(
                [],
                [
                    Error(code='FOO', message=AnyValue('str'), field=AnyValue('str', permit_none=True)),  # type: ignore
                    Error(code='BAR', message=AnyValue('str'), field=AnyValue('str', permit_none=True)),  # type: ignore
                ],
            )

    def test_assert_all_wanted_errors_mismatch_missing_error(self):
        with self.assertRaises(AssertionError):
            assertions.assert_lists_match_any_order(
                [
                    Error(code='FOO', message=AnyValue('str'), field=AnyValue('str', permit_none=True)),  # type: ignore
                    Error(code='BAR', message=AnyValue('str'), field=AnyValue('str', permit_none=True)),  # type: ignore
                ],
                [
                    Error(code='BAR', message='Bar message', field=None),
                ],
            )

    def test_assert_all_wanted_errors_match_same_order(self):
        assertions.assert_lists_match_any_order(
            [
                Error(code='FOO', message=AnyValue('str'), field=AnyValue('str', permit_none=True)),  # type: ignore
                Error(code='BAR', message=AnyValue('str'), field=AnyValue('str', permit_none=True)),  # type: ignore
            ],
            [
                Error(code='FOO', message='Foo message', field='foo_field'),
                Error(code='BAR', message='Bar message', field=None),
            ],
        )

    def test_assert_all_wanted_errors_match_different_order(self):
        assertions.assert_lists_match_any_order(
            [
                Error(code='FOO', message=AnyValue('str'), field=AnyValue('str', permit_none=True)),  # type: ignore
                Error(code='BAR', message=AnyValue('str'), field=AnyValue('str', permit_none=True)),  # type: ignore
            ],
            [
                Error(code='BAR', message='Bar message', field=None),
                Error(code='FOO', message='Foo message', field='foo_field'),
            ],
        )

    def test_assert_any_wanted_error_mismatch_empty_actual_list(self):
        with self.assertRaises(AssertionError):
            assertions.assert_expected_list_subset_of_actual(
                [
                    Error(code='FOO', message=AnyValue('str'), field=AnyValue('str', permit_none=True)),  # type: ignore
                    Error(code='BAR', message=AnyValue('str'), field=AnyValue('str', permit_none=True)),  # type: ignore
                ],
                [],
            )

    def test_assert_any_wanted_error_mismatch_code(self):
        with self.assertRaises(AssertionError):
            assertions.assert_expected_list_subset_of_actual(
                [
                    Error(code='BAZ', message=AnyValue('str'), field=AnyValue('str', permit_none=True)),  # type: ignore
                ],
                [
                    Error(code='FOO', message='Foo message', field='foo_field'),
                    Error(code='BAR', message='Bar Message', field=None),
                ],
            )

    def test_assert_any_wanted_error_match(self):
        assertions.assert_expected_list_subset_of_actual(
            [
                Error(code='BAR', message=AnyValue('str'), field=AnyValue('str', permit_none=True)),  # type: ignore
            ],
            [
                Error(code='FOO', message='Foo message', field='foo_field'),
                Error(code='BAR', message='Bar message', field=None),
            ],
        )

    def test_assert_any_wanted_error_match_with_field(self):
        assertions.assert_expected_list_subset_of_actual(
            [
                Error(code='FOO', message=AnyValue('str'), field=AnyValue('str', permit_none=True)),  # type: ignore
            ],
            [
                Error(code='FOO', message='Foo message', field='foo_field'),
                Error(code='BAR', message='Bar message', field=None),
            ],
        )

    def test_assert_any_wanted_error_match_with_field_multiples(self):
        assertions.assert_expected_list_subset_of_actual(
            [
                Error(code='FOO', message=AnyValue('str'), field=AnyValue('str', permit_none=True)),  # type: ignore
                Error(code='BAR', message=AnyValue('str'), field=AnyValue('str', permit_none=True)),  # type: ignore
            ],
            [
                Error(code='FOO', message='Foo message', field='foo_field'),
                Error(code='BAR', message='Bar message', field=None),
                Error(code='BAZ', message='Baz message', field=None),
            ],
        )

    def test_assert_subset_structure_none(self):
        assertions.assert_subset_structure(
            {'foo': None},
            {'foo': None},
            subset_lists=True,
        )

    def test_assert_subset_structure_extras(self):
        assertions.assert_subset_structure(
            {'foo': 'bar'},
            {'foo': 'bar', 'baz': 'qux'},
            subset_lists=True,
        )

    def test_assert_subset_structure_mismatch(self):
        with self.assertRaises(AssertionError) as error_info:
            assertions.assert_subset_structure(
                {'foo': None},
                {'foo': 'bar'},
                subset_lists=True,
                msg='Include this in the message',
            )

        self.assertTrue(error_info.exception.args[0].startswith('Include this in the message'))
        self.assertIn('DATA ERROR', error_info.exception.args[0])
        self.assertIn('Mismatch values', error_info.exception.args[0])

    def test_assert_subset_structure_missing(self):
        with self.assertRaises(AssertionError) as error_info:
            assertions.assert_subset_structure(
                {'foo': None},
                {'baz': 'qux'},
                subset_lists=True,
            )

        self.assertNotIn('DATA ERROR', error_info.exception.args[0])
        self.assertIn('Missing values', error_info.exception.args[0])

    def test_assert_subset_structure_empty_list_not_empty(self):
        with self.assertRaises(AssertionError) as error_info:
            assertions.assert_subset_structure(
                {'foo': {'bar': []}},
                {'foo': {'bar': ['baz', 'qux']}},
                subset_lists=True,
            )

        self.assertNotIn('DATA ERROR', error_info.exception.args[0])
        self.assertIn('Mismatch values', error_info.exception.args[0])

    def test_assert_subset_structure_list_not_exact(self):
        with self.assertRaises(AssertionError) as error_info:
            assertions.assert_subset_structure(
                {'foo': {'bar': ['baz', 'qux', 'flem']}},
                {'foo': {'bar': ['baz', 'qux']}},
            )

        self.assertNotIn('DATA ERROR', error_info.exception.args[0])
        self.assertIn('Missing values', error_info.exception.args[0])

    def test_assert_subset_structure_one_item_not_subset_of_actual_list(self):
        with self.assertRaises(AssertionError) as error_info:
            assertions.assert_subset_structure(
                {'foo': {'bar': 'flem'}},
                {'foo': {'bar': ['baz', 'qux']}},
                subset_lists=True,
            )

        self.assertNotIn('DATA ERROR', error_info.exception.args[0])
        self.assertIn('Missing values', error_info.exception.args[0])

    def test_assert_subset_structure_one_item_subset_of_actual_list(self):
        assertions.assert_subset_structure(
            {'foo': {'bar': 'baz'}},
            {'foo': {'bar': ['baz', 'qux']}},
            subset_lists=True,
        )

    def test_assert_not_present_but_present(self):
        with self.assertRaises(AssertionError):
            assertions.assert_not_present(
                {'foo': AnyValue('str')},
                {'foo': 'Hello', 'bar': 42},
            )

    def test_assert_not_present_but_present_sub_structure(self):
        with self.assertRaises(AssertionError):
            assertions.assert_not_present(
                {'user': {'foo': AnyValue('str')}},
                {'user': {'foo': 'Hello', 'bar': 42}},
            )

    def test_assert_not_present_not_present(self):
        assertions.assert_not_present(
            {'foo': AnyValue('str')},
            {'bar': 42},
        )

    def test_assert_not_present_not_present_sub_structure(self):
        assertions.assert_not_present(
            {'user': {'foo': AnyValue('str')}},
            {'user': {'bar': 42}},
        )

    def test_assert_exact_structure_mismatch(self):
        with self.assertRaises(AssertionError) as error_info:
            assertions.assert_exact_structure(
                {'user': {'id': 12, 'name': AnyValue('str')}, 'parent': {'id': AnyValue('int'), 'name': 'Roger'}},
                {'user': {'id': 12, 'name': 'Seth'}, 'parent': {'id': 79, 'name': 'Betty'}},
            )

        self.assertIn('Mismatch values', error_info.exception.args[0])

    def test_assert_exact_structure_missing(self):
        with self.assertRaises(AssertionError) as error_info:
            assertions.assert_exact_structure(
                {'user': {'id': 12, 'name': AnyValue('str')}, 'parent': {'id': AnyValue('int'), 'name': 'Roger'}},
                {'user': {'id': 12, 'name': 'Seth'}, 'parent': {'name': 'Roger'}},
            )

        self.assertIn('Missing values', error_info.exception.args[0])

    def test_assert_exact_structure_extra(self):
        with self.assertRaises(AssertionError) as error_info:
            assertions.assert_exact_structure(
                {'user': {'id': 12, 'name': AnyValue('str')}, 'parent': {'id': AnyValue('int'), 'name': 'Roger'}},
                {'user': {'id': 12, 'name': 'Seth'}, 'parent': {'id': 79, 'name': 'Roger', 'age': 65}},
            )

        self.assertIn('Extra values', error_info.exception.args[0])

    def test_assert_exact_structure_non_empty(self):
        with self.assertRaises(AssertionError) as error_info:
            assertions.assert_exact_structure(
                {'user': {'id': 12, 'name': AnyValue('str')}, 'parent': {}},
                {'user': {'id': 12, 'name': 'Seth'}, 'parent': {'id': 79}},
            )

        self.assertIn('Extra values', error_info.exception.args[0])

    def test_assert_exact_structure_match(self):
        assertions.assert_exact_structure(
            {'user': {'id': 12, 'name': AnyValue('str')}, 'parent': {'id': AnyValue('int'), 'name': 'Roger'}},
            {'user': {'id': 12, 'name': 'Seth'}, 'parent': {'id': 79, 'name': 'Roger'}},
        )

    def test_assert_exact_structure_list_mismatch(self):
        with self.assertRaises(AssertionError):
            assertions.assert_exact_structure(
                {'user': {'id': 12, 'name': AnyValue('str')}, 'parents': [79, 86]},
                {'user': {'id': 12, 'name': 'Seth'}, 'parents': [79, 86, 51]},
            )
