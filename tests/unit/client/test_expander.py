from __future__ import (
    absolute_import,
    unicode_literals,
)

from unittest import TestCase

from pysoa.client.expander import (
    ExpansionConverter,
    ExpansionNode,
    TypeNode,
)


class TestTypeNode(TestCase):
    def setUp(self):
        self.type_node = TypeNode(node_type='foo')

    def test_add_expansion(self):
        expansion_node = ExpansionNode(
            node_type='bar',
            name='bar',
            source_field='bar_id',
            destination_field='bar',
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
            node_type='bar',
            name='bar',
            source_field='bar_id',
            destination_field='bar',
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
            node_type='bar',
            name='bar',
            source_field='bar_id',
            destination_field='bar',
            service='bar',
            action='get_bar',
            request_field='id',
            response_field='bar',
        )
        self.type_node.add_expansion(expansion_node)

        another_expansion_node = ExpansionNode(
            node_type='bar',
            name='bar',
            source_field='bar_id',
            destination_field='bar',
            service='bar',
            action='get_bar',
            request_field='id',
            response_field='bar',
        )
        child_expansion_node = ExpansionNode(
            node_type='baz',
            name='baz',
            source_field='baz_id',
            destination_field='baz',
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
            node_type='bar',
            name='bar',
            source_field='bar_id',
            destination_field='bar',
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

    def test_find_objects_recursively(self):
        matching_objects = self.type_node.find_objects({
            'something': {
                '_type': 'bar',
                'id': 'hello',
                'related': [
                    {'_type': 'foo', 'id': 'goodbye'},
                    {'_type': 'foo', 'id': 'world'},
                ],
                'sub': {'_type': 'wiggle', 'wiggle_id': '1234'},
            },
        })
        self.assertEqual(2, len(matching_objects))
        self.assertEqual({'_type': 'foo', 'id': 'goodbye'}, matching_objects[0])
        self.assertEqual({'_type': 'foo', 'id': 'world'}, matching_objects[1])

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

    def test_to_dict(self):
        bar_expansion_node = ExpansionNode(
            node_type='bar',
            name='bar',
            source_field='bar_id',
            destination_field='bar',
            service='bar',
            action='get_bar',
            request_field='id',
            response_field='bar',
        )
        baz_expansion_node = ExpansionNode(
            node_type='baz',
            name='baz',
            source_field='baz_id',
            destination_field='baz',
            service='baz',
            action='get_baz',
            request_field='id',
            response_field='baz',
        )
        qux_expansion_node = ExpansionNode(
            node_type='qux',
            name='qux',
            source_field='qux_id',
            destination_field='qux',
            service='qux',
            action='get_qux',
            request_field='id',
            response_field='qux',
        )
        bar_expansion_node.add_expansion(baz_expansion_node)
        bar_expansion_node.add_expansion(qux_expansion_node)
        self.type_node.add_expansion(bar_expansion_node)

        type_node_dict = self.type_node.to_dict()

        self.assertTrue('foo' in type_node_dict)
        self.assertEqual(set(type_node_dict['foo']), {'bar.qux', 'bar.baz'})


class TestExpansionNode(TestCase):
    def setUp(self):
        self.expansion_node = ExpansionNode(
            node_type='foo',
            name='foo',
            source_field='foo_id',
            destination_field='foo',
            service='foo',
            action='get_foo',
            request_field='id',
            response_field='foo',
        )

    def test_to_strings_with_expansions(self):
        bar_expansion_node = ExpansionNode(
            node_type='bar',
            name='bar',
            source_field='bar_id',
            destination_field='bar',
            service='bar',
            action='get_bar',
            request_field='id',
            response_field='bar',
        )
        baz_expansion_node = ExpansionNode(
            node_type='baz',
            name='baz',
            source_field='baz_id',
            destination_field='baz',
            service='baz',
            action='get_baz',
            request_field='id',
            response_field='baz',
        )
        self.expansion_node.add_expansion(bar_expansion_node)
        self.expansion_node.add_expansion(baz_expansion_node)

        self.assertEqual(
            set(self.expansion_node.to_strings()),
            {'foo.baz', 'foo.bar'},
        )

    def test_to_strings_without_expansions(self):
        self.assertEqual(
            self.expansion_node.to_strings(),
            ['foo'],
        )


class TestExpansionConverter(TestCase):
    def setUp(self):
        self.converter = ExpansionConverter(
            type_routes={
                'foo_route': {
                    'service': 'foo',
                    'action': 'get_foo',
                    'request_field': 'id',
                    'response_field': 'foo',
                },
                'bar_route': {
                    'service': 'bar',
                    'action': 'get_bar',
                    'request_field': 'id',
                    'response_field': 'bar',
                },
                'baz_route': {
                    'service': 'baz',
                    'action': 'get_baz',
                    'request_field': 'id',
                    'response_field': 'baz',
                },
                'qux_route': {
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
                        'route': 'bar_route',
                        'source_field': 'bar_id',
                        'destination_field': 'bar',
                    },
                },
                'bar': {
                    'baz': {
                        'type': 'baz',
                        'route': 'baz_route',
                        'source_field': 'baz_id',
                        'destination_field': 'baz',
                    },
                    'qux': {
                        'type': 'qux',
                        'route': 'qux_route',
                        'source_field': 'qux_id',
                        'destination_field': 'qux',
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
        self.assertEqual(bar_expansion_node.destination_field, 'bar')
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
        self.assertEqual(baz_expansion_node.destination_field, 'baz')
        self.assertEqual(baz_expansion_node.service, 'baz')
        self.assertEqual(baz_expansion_node.action, 'get_baz')
        self.assertEqual(baz_expansion_node.request_field, 'id')
        self.assertEqual(baz_expansion_node.response_field, 'baz')
        self.assertEqual(len(baz_expansion_node.expansions), 0)
        self.assertIsInstance(qux_expansion_node, ExpansionNode)
        self.assertEqual(qux_expansion_node.type, 'qux')
        self.assertEqual(qux_expansion_node.name, 'qux')
        self.assertEqual(qux_expansion_node.source_field, 'qux_id')
        self.assertEqual(qux_expansion_node.destination_field, 'qux')
        self.assertEqual(qux_expansion_node.service, 'qux')
        self.assertEqual(qux_expansion_node.action, 'get_qux')
        self.assertEqual(qux_expansion_node.request_field, 'id')
        self.assertEqual(qux_expansion_node.response_field, 'qux')
        self.assertEqual(len(qux_expansion_node.expansions), 0)

    def test_trees_to_dict(self):
        foo_tree_node = TypeNode(node_type='foo')
        bar_expansion_node = ExpansionNode(
            node_type='bar',
            name='bar',
            source_field='bar_id',
            destination_field='bar',
            service='bar',
            action='get_bar',
            request_field='id',
            response_field='bar',
        )
        foo_tree_node.add_expansion(bar_expansion_node)

        baz_tree_node = TypeNode(node_type='baz')
        qux_expansion_node = ExpansionNode(
            node_type='qux',
            name='qux',
            source_field='qux_id',
            destination_field='qux',
            service='qux',
            action='get_qux',
            request_field='id',
            response_field='qux',
        )
        baz_tree_node.add_expansion(qux_expansion_node)

        self.assertEqual(
            self.converter.trees_to_dict([foo_tree_node, baz_tree_node]),
            {
                'foo': ['bar'],
                'baz': ['qux'],
            },
        )
