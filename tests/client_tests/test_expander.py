from unittest import TestCase

from pysoa.client.expander import (
    ExpansionConverter,
    ExpansionNode,
    TypeNode,
)


class TypeNodeTests(TestCase):
    def setUp(self):
        self.type_node = TypeNode(type='foo')

    def test_add_expansion(self):
        expansion_node = ExpansionNode(
            type='bar',
            name='bar',
            source_field='bar_id',
            dest_field='bar',
            service='bar',
            action='get_bar',
            request_field='id',
            response_field='bar',
        )
        self.type_node.add_expansion(expansion_node)

        self.assertEqual(len(self.type_node.expansions), 1)
        self.assertEqual(
            self.type_node.expansions[0],
            expansion_node,
        )

    def test_cannot_add_same_expansion_twice(self):
        expansion_node = ExpansionNode(
            type='bar',
            name='bar',
            source_field='bar_id',
            dest_field='bar',
            service='bar',
            action='get_bar',
            request_field='id',
            response_field='bar',
        )
        self.type_node.add_expansion(expansion_node)
        self.type_node.add_expansion(expansion_node)

        self.assertEqual(len(self.type_node.expansions), 1)
        self.assertEqual(
            self.type_node.expansions[0],
            expansion_node,
        )

    def test_add_expansion_merges_children(self):
        expansion_node = ExpansionNode(
            type='bar',
            name='bar',
            source_field='bar_id',
            dest_field='bar',
            service='bar',
            action='get_bar',
            request_field='id',
            response_field='bar',
        )
        self.type_node.add_expansion(expansion_node)

        another_expansion_node = ExpansionNode(
            type='bar',
            name='bar',
            source_field='bar_id',
            dest_field='bar',
            service='bar',
            action='get_bar',
            request_field='id',
            response_field='bar',
        )
        child_expansion_node = ExpansionNode(
            type='baz',
            name='baz',
            source_field='baz_id',
            dest_field='baz',
            service='baz',
            action='get_baz',
            request_field='id',
            response_field='baz',
        )
        another_expansion_node.add_expansion(child_expansion_node)
        self.type_node.add_expansion(another_expansion_node)

        self.assertEqual(len(self.type_node.expansions), 1)
        self.assertNotEqual(
            self.type_node.expansions[0],
            another_expansion_node,
        )
        self.assertEqual(
            len(self.type_node.expansions[0].expansions),
            1,
        )
        self.assertEqual(
            self.type_node.expansions[0].expansions[0],
            child_expansion_node,
        )

    def test_get_expansion(self):
        expansion_node = ExpansionNode(
            type='bar',
            name='bar',
            source_field='bar_id',
            dest_field='bar',
            service='bar',
            action='get_bar',
            request_field='id',
            response_field='bar',
        )
        self.type_node.add_expansion(expansion_node)
        self.assertEqual(
            self.type_node.get_expansion(expansion_node.name),
            expansion_node,
        )

    def test_get_expansion_does_not_exist(self):
        self.assertEqual(
            self.type_node.get_expansion('not_a_valid_expansion_name'),
            None,
        )

    def test_find_objects_dict_with_type(self):
        test_foo = {
            '_type': 'foo',
        }
        matching_objects = self.type_node.find_objects(test_foo)
        self.assertEqual(len(matching_objects), 1)
        self.assertEqual(matching_objects[0], test_foo)

    def test_find_objects_dict_with_type_ignores_matching_subobjects(self):
        test_foo = {
            '_type': 'foo',
            'related_foos': [{
                '_type': 'foo',
            }],
        }
        matching_objects = self.type_node.find_objects(test_foo)
        self.assertEqual(len(matching_objects), 1)
        self.assertEqual(matching_objects[0], test_foo)

    def test_find_objects_dict_without_type(self):
        test_foo = {
            '_type': 'foo',
        }
        test_response = {
            'foo': test_foo,
        }
        matching_objects = self.type_node.find_objects(test_response)
        self.assertEqual(len(matching_objects), 1)
        self.assertEqual(matching_objects[0], test_foo)

    def test_find_objects_list(self):
        test_foo = {
            '_type': 'foo',
        }
        matching_objects = self.type_node.find_objects([test_foo])
        self.assertEqual(len(matching_objects), 1)
        self.assertEqual(matching_objects[0], test_foo)


class ExpansionConverterTests(TestCase):
    def setUp(self):
        self.converter = ExpansionConverter(
            type_routes={
                'foo': {
                    'service': 'foo',
                    'action': 'get_foo',
                    'request_field': 'id',
                    'response_field': 'foo',
                },
                'bar': {
                    'service': 'bar',
                    'action': 'get_bar',
                    'request_field': 'id',
                    'response_field': 'bar',
                },
                'baz': {
                    'service': 'baz',
                    'action': 'get_baz',
                    'request_field': 'id',
                    'response_field': 'baz',
                },
                'qux': {
                    'service': 'qux',
                    'action': 'get_qux',
                    'request_field': 'id',
                    'response_field': 'qux',
                },
            },
            type_expansions={
                'foo': {
                    'bar': {
                        'type': 'bar',
                        'source_field': 'bar_id',
                        'dest_field': 'bar',
                    },
                },
                'bar': {
                    'baz': {
                        'type': 'baz',
                        'source_field': 'baz_id',
                        'dest_field': 'baz',
                    },
                    'qux': {
                        'type': 'qux',
                        'source_field': 'qux_id',
                        'dest_field': 'qux',
                    },
                },
            },
        )

    def test_dict_to_trees(self):
        trees = self.converter.dict_to_trees({
            'foo': [
                'bar',
                'bar.baz',
                'bar.qux',
            ],
        })

        self.assertEqual(len(trees), 1)
        type_node = trees[0]
        self.assertIsInstance(type_node, TypeNode)
        self.assertEqual(type_node.type, 'foo')
        self.assertEqual(len(type_node.expansions), 1)

        bar_expansion_node = type_node.expansions[0]
        self.assertIsInstance(bar_expansion_node, ExpansionNode)
        self.assertEqual(bar_expansion_node.type, 'bar')
        self.assertEqual(bar_expansion_node.name, 'bar')
        self.assertEqual(bar_expansion_node.source_field, 'bar_id')
        self.assertEqual(bar_expansion_node.dest_field, 'bar')
        self.assertEqual(bar_expansion_node.service, 'bar')
        self.assertEqual(bar_expansion_node.action, 'get_bar')
        self.assertEqual(bar_expansion_node.request_field, 'id')
        self.assertEqual(bar_expansion_node.response_field, 'bar')
        self.assertEqual(len(bar_expansion_node.expansions), 2)

        baz_expansion_node, qux_expansion_node = sorted(bar_expansion_node.expansions, key=lambda x: x.type)
        self.assertIsInstance(baz_expansion_node, ExpansionNode)
        self.assertEqual(baz_expansion_node.type, 'baz')
        self.assertEqual(baz_expansion_node.name, 'baz')
        self.assertEqual(baz_expansion_node.source_field, 'baz_id')
        self.assertEqual(baz_expansion_node.dest_field, 'baz')
        self.assertEqual(baz_expansion_node.service, 'baz')
        self.assertEqual(baz_expansion_node.action, 'get_baz')
        self.assertEqual(baz_expansion_node.request_field, 'id')
        self.assertEqual(baz_expansion_node.response_field, 'baz')
        self.assertEqual(len(baz_expansion_node.expansions), 0)
        self.assertIsInstance(qux_expansion_node, ExpansionNode)
        self.assertEqual(qux_expansion_node.type, 'qux')
        self.assertEqual(qux_expansion_node.name, 'qux')
        self.assertEqual(qux_expansion_node.source_field, 'qux_id')
        self.assertEqual(qux_expansion_node.dest_field, 'qux')
        self.assertEqual(qux_expansion_node.service, 'qux')
        self.assertEqual(qux_expansion_node.action, 'get_qux')
        self.assertEqual(qux_expansion_node.request_field, 'id')
        self.assertEqual(qux_expansion_node.response_field, 'qux')
        self.assertEqual(len(qux_expansion_node.expansions), 0)
