from __future__ import (
    absolute_import,
    unicode_literals,
)

from conformity import fields
import pytest

from pysoa.common.schemas import (
    BasicClassSchema,
    PolymorphClassSchema,
)


class _ClassSchema(BasicClassSchema):
    contents = {
        'path': fields.UnicodeString(
            description='The path to the Redis client or server transport, in the format `module.name:ClassName`',
        ),
        'kwargs': fields.Dictionary(
            {
                'foo': fields.UnicodeString(),
                'bar': fields.Integer(),
                'baz': fields.Boolean(),
            },
            optional_keys=('baz', ),
        )
    }


class _SuperThingClient(object):
    pass


class _SuperThingServer(object):
    pass


class _ThingOne(_SuperThingClient):
    pass


class _ThingTwo(_SuperThingServer):
    pass


class _ThingThree(object):
    pass


_ThingOne.settings_schema = _ClassSchema(_ThingOne)
_ThingTwo.settings_schema = BasicClassSchema(_ThingTwo)
_ThingThree.settings_schema = {}


class TestPolymorphClassSchema(object):
    def test_non_existent_value(self):
        schema = PolymorphClassSchema({})

        nope = None

        assert 'hello:World' not in schema.contents_map
        assert schema.contents_map.get('hello:World') is None
        with pytest.raises(KeyError):
            nope = schema.contents_map['hello:World']

        assert schema.contents_map.get('goodbye:Universe') is None
        assert 'goodbye:Universe' not in schema.contents_map
        with pytest.raises(KeyError):
            nope = schema.contents_map['goodbye:Universe']

        with pytest.raises(KeyError):
            nope = schema.contents_map['pysoa.utils:DoesNotExist']
        assert 'pysoa.utils:DoesNotExist' not in schema.contents_map
        assert schema.contents_map.get('pysoa.utils:DoesNotExist') is None

        assert 'hello:World' not in schema.contents_map
        assert schema.contents_map.get('hello:World') is None
        with pytest.raises(KeyError):
            nope = schema.contents_map['hello:World']

        assert nope is None

    def test_existent_not_a_class_schema(self):
        schema = PolymorphClassSchema({})

        with pytest.raises(ValueError):
            schema.contents_map.get('tests.common.test_schemas:_ThingThree')

    def test_existent_no_subclass_enforcement(self):
        schema = PolymorphClassSchema({})

        assert schema.contents_map.get('tests.common.test_schemas:_ThingOne') is _ThingOne.settings_schema
        assert schema.contents_map.get('tests.common.test_schemas:_ThingTwo') is _ThingTwo.settings_schema

        assert schema.contents_map.get('tests.common.test_schemas:_ThingOne') is _ThingOne.settings_schema
        assert schema.contents_map.get('tests.common.test_schemas:_ThingTwo') is _ThingTwo.settings_schema

    def test_existent_with_subclass_enforcement(self):
        schema1 = PolymorphClassSchema({}, _SuperThingClient)

        assert schema1.contents_map.get('tests.common.test_schemas:_ThingOne') is _ThingOne.settings_schema
        assert schema1.contents_map.get('tests.common.test_schemas:_ThingOne') is _ThingOne.settings_schema

        with pytest.raises(ValueError):
            schema1.contents_map.get('tests.common.test_schemas:_ThingTwo')

        schema2 = PolymorphClassSchema({}, _SuperThingServer)

        assert schema2.contents_map.get('tests.common.test_schemas:_ThingTwo') is _ThingTwo.settings_schema
        assert schema2.contents_map.get('tests.common.test_schemas:_ThingTwo') is _ThingTwo.settings_schema

        with pytest.raises(ValueError):
            schema2.contents_map.get('tests.common.test_schemas:_ThingOne')

    def test_missing_default_error(self):
        schema1 = PolymorphClassSchema({})

        with pytest.raises(ValueError):
            schema1.contents_map.get('__default__')

        schema2 = PolymorphClassSchema({'__default__': True})
        assert schema2.contents_map.get('__default__') is True

    def test_errors(self):
        schema = PolymorphClassSchema(
            {
                '__default__': BasicClassSchema(),
            },
            _SuperThingClient,
        )

        assert schema.errors({'path': 'hello:World', 'kwargs': {}}) == []
        assert schema.errors({'path': 'hello:World', 'kwargs': {'yo': 'cool'}}) == []

        assert len(schema.errors(
            {'path': 'tests.common.test_schemas:_ThingOne', 'kwargs': {}}
        )) == 2

        assert len(schema.errors(
            {'path': 'tests.common.test_schemas:_ThingOne', 'kwargs': {'foo': 12, 'bar': 'geek'}}
        )) == 2

        assert len(schema.errors(
            {'path': 'tests.common.test_schemas:_ThingOne', 'kwargs': {'foo': 'geek', 'bar': 12, 'baz': 'no'}}
        )) == 1

        assert schema.errors(
            {'path': 'tests.common.test_schemas:_ThingOne', 'kwargs': {'foo': 'geek', 'bar': 12}}
        ) == []

        assert schema.errors(
            {'path': 'tests.common.test_schemas:_ThingOne', 'kwargs': {'foo': 'geek', 'bar': 12, 'baz': False}}
        ) == []
