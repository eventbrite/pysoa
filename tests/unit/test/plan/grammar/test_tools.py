from __future__ import (
    absolute_import,
    unicode_literals,
)

from typing import (
    Any,
    Dict,
)
import unittest

import six

from pysoa.test.plan.errors import StatusError
from pysoa.test.plan.grammar.tools import (
    get_all_paths,
    path_get,
    path_put,
    substitute_variables,
)


class TestPathAccessors(unittest.TestCase):
    def test_001_simple_put(self):
        out = {}  # type: Dict[six.text_type, Any]
        path_put(out, 'foo', 'bar')

        self.assertEqual(out, {'foo': 'bar'})
        self.assertEqual(path_get(out, 'foo'), 'bar')

    def test_002_nested_put(self):
        out = {}  # type: Dict[six.text_type, Any]
        path_put(out, 'foo.bar', 'baz')

        self.assertEqual(out, {'foo': {'bar': 'baz'}})
        self.assertEqual(path_get(out, 'foo.bar'), 'baz')

    def test_003_bracket_name_put(self):
        out = {}  # type: Dict[six.text_type, Any]
        path_put(out, 'foo.{bar.baz}', 'moo')

        self.assertEqual(out, {'foo': {'bar.baz': 'moo'}})
        self.assertEqual(path_get(out, 'foo.{bar.baz}'), 'moo')

    def test_004_bracket_name_then_more_depth(self):
        out = {}  # type: Dict[six.text_type, Any]
        path_put(out, 'foo.{bar.baz}.gar', 'moo')

        self.assertEqual(out, {'foo': {'bar.baz': {'gar': 'moo'}}})
        self.assertEqual(path_get(out, 'foo.{bar.baz}.gar'), 'moo')

    def test_005_simple_array_put(self):
        out = {}  # type: Dict[six.text_type, Any]
        path_put(out, 'foo.bar.0', 'thing')

        self.assertEqual(out, {'foo': {'bar': ['thing']}})
        self.assertEqual(path_get(out, 'foo.bar.0'), 'thing')

    def test_005_02_bracket_name_then_list(self):
        out = {}  # type: Dict[six.text_type, Any]
        path_put(out, 'foo.bar.{thing.in.bracket}.0', 'la la la')
        self.assertEqual(out, {'foo': {'bar': {'thing.in.bracket': ['la la la']}}})
        self.assertEqual(path_get(out, 'foo.bar.{thing.in.bracket}.0'), 'la la la')

    def test_006_array_with_nested_dict(self):
        out = {}  # type: Dict[six.text_type, Any]
        path_put(out, 'foo.bar.0.baz', 'thing')

        self.assertEqual(out, {'foo': {'bar': [{'baz': 'thing'}]}})
        self.assertEqual(path_get(out, 'foo.bar.0.baz'), 'thing')

    def test_007_array_with_nested_array(self):
        out = {}  # type: Dict[six.text_type, Any]
        path_put(out, 'foo.bar.0.0.baz', 'thing')

        self.assertEqual(out, {'foo': {'bar': [[{'baz': 'thing'}]]}})
        self.assertEqual(path_get(out, 'foo.bar.0.0.baz'), 'thing')

    def test_008_array_with_missing_index(self):
        out = {}  # type: Dict[six.text_type, Any]
        path_put(out, 'foo.bar.2.baz', 'thing')

        self.assertEqual(out, {'foo': {'bar': [{}, {}, {'baz': 'thing'}]}})
        self.assertEqual(path_get(out, 'foo.bar.2.baz'), 'thing')

    def test_009_numeric_dictionary_keys(self):
        out = {}  # type: Dict[six.text_type, Any]
        path_put(out, 'foo.bar.{2}.baz', 'thing')
        self.assertEqual(out, {'foo': {'bar': {'2': {'baz': 'thing'}}}})
        self.assertEqual(path_get(out, 'foo.bar.{2}.baz'), 'thing')

    def test_010_path_get_missing_key(self):
        with self.assertRaises(KeyError):
            path_get({}, 'foo')

    def test_011_path_get_missing_nested_key(self):
        with self.assertRaises(KeyError):
            path_get({'foo': {'bar': 'baz'}}, 'foo.blah')

    def test_012_path_get_missing_array(self):
        with self.assertRaises(KeyError):
            path_get({'foo': {'bar': 'baz'}}, 'foo.0')

    def test_013_path_get_missing_array_further_index(self):
        with self.assertRaises(IndexError):
            path_get({'foo': [{}, {}]}, 'foo.2')

    def test_014_path_get_missing_nested_array(self):
        with self.assertRaises(IndexError):
            path_get({'foo': [[]]}, 'foo.0.0')

    def test_015_path_get_missing_nested_array_further_index(self):
        with self.assertRaises(IndexError):
            path_get({'foo': [[{}, {}]]}, 'foo.0.4')

    def test_016_escaped_array_index_key(self):
        out = {}  # type: Dict[six.text_type, Any]
        path_put(out, '{record_transaction.0}.inputs.foo', 'bar')
        self.assertEqual(out, {'record_transaction.0': {'inputs': {'foo': 'bar'}}})
        self.assertEqual(path_get(out, '{record_transaction.0}.inputs.foo'), 'bar')

    def test_017_escaped_array_of_dict(self):
        out = {}  # type: Dict[six.text_type, Any]
        path_put(out, 'transaction.metadata.references.0.reference_type', 'FOO')
        path_put(out, 'transaction.metadata.references.0.reference_ids.0', '1234')
        self.assertEqual(
            out,
            {'transaction': {'metadata': {'references': [{'reference_type': 'FOO', 'reference_ids': ['1234']}]}}},
        )
        self.assertEqual(path_get(out, 'transaction.metadata.references.0.reference_type'), 'FOO')
        self.assertEqual(path_get(out, 'transaction.metadata.references.0.reference_ids.0'), '1234')

    def test_018_complex_path_list(self):
        path_list = [
            'foo.bar',
            'foo.{bar.baz}',
            'foo.{yea_bar.baz}.gar',
            'foo.aba_bar.0',
            'foo.sba_bar.0.baz',
            'foo.nu_bar.0.0.baz',
            'foo.ba_bar.0.baz',
            'foo.ba_bar.1.baz',
            'foo.ba_bar.2.baz',
            'foo.re_bar.{2}.baz',
            '{record_transaction.0}.inputs.foo',
            'transaction.metadata.references.0.reference_type',
            'transaction.metadata.references.0.reference_ids.0',
        ]

        out = {}  # type: Dict[six.text_type, Any]
        for path in path_list:
            path_put(out, path, 'blah_blah')

        self.assertEqual(sorted(path_list), sorted(get_all_paths(out)))

    def test_019_nested_brackets(self):
        out = {}  # type: Dict[six.text_type, Any]
        path_put(out, 'charge.cost_components.{{item.gross}}', {'MISSING'})

        self.assertEqual(out, {'charge': {'cost_components': {'{item.gross}': {'MISSING'}}}})
        self.assertEqual(path_get(out, 'charge.cost_components.{{item.gross}}'), {'MISSING'})

    def test_020_path_listing_for_complex_dict(self):
        data = {
            'foo': {
                'aba_bar': ['test'],
                'ba_bar': [{}, {'baz': 'test'}, {}],
                'bar': 'test',
                'bar.baz': 'test',
                'nu_bar': [[{'baz': 'test'}]],
                're_bar': {'2': {'baz': 'test'}},
                'sba_bar': [{'baz': 'test'}, [], {}],
                'yea_bar.baz': {'gar': 'test'},
            },
            'record_transaction.0': {
                'inputs': {
                    'bar': [],
                    'foo': 'test',
                    're_bar': {},
                },
            },
            'transaction': {
                'metadata': {
                    'references': [
                        {'reference_ids': ['blah_blah'], 'reference_type': 'blah_blah'},
                        {},
                    ],
                },
            },
        }

        actual = get_all_paths(data, allow_blank=True)

        expected = [
            'foo.aba_bar.0',
            'foo.ba_bar.0',
            'foo.ba_bar.1.baz',
            'foo.ba_bar.2',
            'foo.bar',
            'foo.nu_bar.0.0.baz',
            'foo.re_bar.{2}.baz',
            'foo.sba_bar.0.baz',
            'foo.sba_bar.1',
            'foo.sba_bar.2',
            'foo.{bar.baz}',
            'foo.{yea_bar.baz}.gar',
            'transaction.metadata.references.0.reference_ids.0',
            'transaction.metadata.references.0.reference_type',
            'transaction.metadata.references.1',
            '{record_transaction.0}.inputs.bar',
            '{record_transaction.0}.inputs.foo',
            '{record_transaction.0}.inputs.re_bar',
        ]
        self.assertEqual(sorted(actual), sorted(expected))

    def test_021_path_listing_for_empty_structures(self):
        self.assertEqual(get_all_paths({}), [])
        self.assertEqual(get_all_paths([]), [])


class TestSubstituteValues(unittest.TestCase):
    sources = [
        {
            'users': [{'id': 5, 'username': 'beamer'}, {'id': 12, 'username': 'pumpkin'}],
            'runners': ['John', 'Rebecca'],
            'integers': {'one': 1, 'seventeen': 17}
        },
        {
            'get_doctor.0': {'doctor': {'id': 1827, 'name': 'Jamie Rolling', 'specialty': 'endocrinologist'}},
        },
    ]

    def test_substitute_variables_no_variables(self):
        data = {
            'foo': 'bar',
            'baz': ['qux', 'flem'],
            'flub': {'flux': 'flare', 'flex': 'flue'},
        }

        substitute_variables(data, *self.sources)  # type: ignore

        self.assertEqual(
            {
                'foo': 'bar',
                'baz': ['qux', 'flem'],
                'flub': {'flux': 'flare', 'flex': 'flue'},
            },
            data,
        )

    def test_substitute_variables_no_sources(self):
        data = {
            'foo': '[[users.0.username]]',
            'baz': ['qux', 'flem'],
            'flub': {'flux': 'flare', 'flex': 'flue'},
        }

        with self.assertRaises(StatusError):
            substitute_variables(data)

    def test_substitute_variables_with_variables(self):
        data = {
            'foo': '[[users.0.username]]',
            'baz': ['qux', '[[runners.1]]', None, 12, '[[integers.seventeen]]'],
            'flub': {
                'flux': 'flare [[GET_DOCTOR.0.doctor.specialty]] [[{get_doctor.0}.doctor.name]] '
                        '[[not.a.sub] [also.not.a.sub]] [[users.1.username]] with [[runners.0]]',
            },
        }

        substitute_variables(data, *self.sources)  # type: ignore

        self.assertEqual(
            {
                'foo': 'beamer',
                'baz': ['qux', 'Rebecca', None, 12, 17],
                'flub': {
                    'flux': 'flare endocrinologist Jamie Rolling [[not.a.sub] [also.not.a.sub]] pumpkin with John',
                },
            },
            data,
        )
