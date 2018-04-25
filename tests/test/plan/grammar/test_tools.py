from __future__ import absolute_import, unicode_literals

import unittest

from pysoa.test.plan.errors import StatusError
from pysoa.test.plan.grammar.tools import (
    get_all_paths,
    path_get,
    path_put,
    substitute_variables,
)


class TestPathAccessors(unittest.TestCase):
    def test_001_simple_put(self):
        out = {}
        path_put(out, 'foo', 'bar')

        self.assertEquals(out, {'foo': 'bar'})
        self.assertEquals(path_get(out, 'foo'), 'bar')

    def test_002_nested_put(self):
        out = {}
        path_put(out, 'foo.bar', 'baz')

        self.assertEquals(out, {'foo': {'bar': 'baz'}})
        self.assertEquals(path_get(out, 'foo.bar'), 'baz')

    def test_003_bracket_name_put(self):
        out = {}
        path_put(out, 'foo.{bar.baz}', 'moo')

        self.assertEquals(out, {'foo': {'bar.baz': 'moo'}})
        self.assertEquals(path_get(out, 'foo.{bar.baz}'), 'moo')

    def test_004_bracket_name_then_more_depth(self):
        out = {}
        path_put(out, 'foo.{bar.baz}.gar', 'moo')

        self.assertEquals(out, {'foo': {'bar.baz': {'gar': 'moo'}}})
        self.assertEquals(path_get(out, 'foo.{bar.baz}.gar'), 'moo')

    def test_005_simple_array_put(self):
        out = {}
        path_put(out, 'foo.bar.0', 'thing')

        self.assertEquals(out, {'foo': {'bar': ['thing']}})
        self.assertEquals(path_get(out, 'foo.bar.0'), 'thing')

    def test_005_02_bracket_name_then_list(self):
        out = {}
        path_put(out, 'foo.bar.{thing.in.bracket}.0', 'la la la')
        self.assertEquals(out, {'foo': {'bar': {'thing.in.bracket': ['la la la']}}})
        self.assertEquals(path_get(out, 'foo.bar.{thing.in.bracket}.0'), 'la la la')

    def test_006_array_with_nested_dict(self):
        out = {}
        path_put(out, 'foo.bar.0.baz', 'thing')

        self.assertEquals(out, {'foo': {'bar': [{'baz': 'thing'}]}})
        self.assertEquals(path_get(out, 'foo.bar.0.baz'), 'thing')

    def test_007_array_with_nested_array(self):
        out = {}
        path_put(out, 'foo.bar.0.0.baz', 'thing')

        self.assertEquals(out, {'foo': {'bar': [[{'baz': 'thing'}]]}})
        self.assertEquals(path_get(out, 'foo.bar.0.0.baz'), 'thing')

    def test_008_array_with_missing_index(self):
        out = {}
        path_put(out, 'foo.bar.2.baz', 'thing')

        self.assertEquals(out, {'foo': {'bar': [{}, {}, {'baz': 'thing'}]}})
        self.assertEquals(path_get(out, 'foo.bar.2.baz'), 'thing')

    def test_009_numeric_dictionary_keys(self):
        out = {}
        path_put(out, 'foo.bar.{2}.baz', 'thing')
        self.assertEquals(out, {'foo': {'bar': {'2': {'baz': 'thing'}}}})
        self.assertEquals(path_get(out, 'foo.bar.{2}.baz'), 'thing')

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
        out = {}
        path_put(out, '{record_transaction.0}.inputs.foo', 'bar')
        self.assertEquals(out, {'record_transaction.0': {'inputs': {'foo': 'bar'}}})
        self.assertEquals(path_get(out, '{record_transaction.0}.inputs.foo'), 'bar')

    def test_017_escaped_array_of_dict(self):
        out = {}
        path_put(out, 'transaction.metadata.references.0.reference_type', 'FOO')
        path_put(out, 'transaction.metadata.references.0.reference_ids.0', '1234')
        self.assertEquals(
            out,
            {'transaction': {'metadata': {'references': [{'reference_type': 'FOO', 'reference_ids': ['1234']}]}}},
        )
        self.assertEquals(path_get(out, 'transaction.metadata.references.0.reference_type'), 'FOO')
        self.assertEquals(path_get(out, 'transaction.metadata.references.0.reference_ids.0'), '1234')

    def test_018_get_all_paths(self):
        path_list = [
            'foo.bar',
            'foo.{bar.baz}',
            'foo.{yea_bar.baz}.gar',
            'foo.aba_bar.0',
            'foo.sba_bar.0.baz',
            'foo.nu_bar.0.0.baz',
            'foo.ba_bar.2.baz',
            'foo.re_bar.{2}.baz',
            '{record_transaction.0}.inputs.foo',
            'transaction.metadata.references.0.reference_type',
            'transaction.metadata.references.0.reference_ids.0',
        ]

        out = {}
        for path in path_list:
            path_put(out, path, 'blah_blah')

        self.assertEquals(sorted(path_list), sorted(get_all_paths(out)))

    def test_020_nested_brackets(self):
        out = {}
        path_put(out, 'charge.cost_components.{{item.gross}}', {'MISSING'})

        self.assertEquals(out, {'charge': {'cost_components': {'{item.gross}': {'MISSING'}}}})
        self.assertEquals(path_get(out, 'charge.cost_components.{{item.gross}}'), {'MISSING'})


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

        substitute_variables(data, *self.sources)

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

        substitute_variables(data, *self.sources)

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
