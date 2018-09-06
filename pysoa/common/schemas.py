from __future__ import (
    absolute_import,
    unicode_literals,
)

from conformity import fields

from pysoa.utils import resolve_python_path


class BasicClassSchema(fields.Dictionary):
    contents = {
        'path': fields.UnicodeString(
            description='The path to the class to be imported and used, in the format `module.name:ClassName`',
        ),
        'kwargs': fields.SchemalessDictionary(
            key_type=fields.UnicodeString(),
            description='Any keyword arguments that should be passed to the class when constructing a new instance',
        ),
    }
    optional_keys = ['kwargs']
    object_type = None

    def __init__(self, object_type=None, **kwargs):
        super(BasicClassSchema, self).__init__(**kwargs)

        if object_type:
            assert isinstance(object_type, type)
            self.object_type = object_type

    def __repr__(self):
        return '{class_name}({object_type})'.format(
            class_name=self.__class__.__name__,
            object_type='object_type={module_name}:{class_name}'.format(
                module_name=self.object_type.__module__,
                class_name=self.object_type.__name__,
            ) if self.object_type else '',
        )


class PolymorphClassSchema(fields.Polymorph):
    """
    This is a more advanced variant of Conformity's `Polymorph` class, whose `switch_field` is always `path` (so that
    it supports `BasicClassSchema`), and whose contents map is dynamic and extensible. When provided a `path` value
    not found in the contents map, the path will be imported and the imported class will be inspected for a
    `settings_schema` attribute. `settings_schema` must be an instance of `BasicClassSchema`, and its value will be
    cached as the contents map value corresponding to that value of `path`. This allows other projects to extend
    polymorph settings and still provide settings validation without having to re-write the entire settings
    hierarchy to support new features.

    Some important notes:

    * You may specify already-known values in the `contents_map` parameter, but this is not required.
    * If you want to support `path` values that cannot be found (imported), you must supply a `'__default__'` key in
      the `contents_map` parameter.
    * You may specify the `enforce_object_type_subclass_of` parameter to enforce that any dynamically-discovered
      schemas' `object_type` attribute (see `BasicClassSchema`) is a subclass of the specified value. For example, the
      `PolymorphicServerSettings`'s `transport` field (a `PolymorphClassSchema`) enforces that the schemas'
      `object_type` attribute is a subclass of `ServerTransport` (to ensure that the `path` points to a server transport
      and not a client transport or some other arbitrary object), and likewise `PolymorphicClientSettings` enforces an
      `object_type` of `ClientTransport` (or its children) for `transport`.
    """
    def __init__(self, contents_map, enforce_object_type_subclass_of=None, description=None, **kwargs):
        super(PolymorphClassSchema, self).__init__(
            switch_field='path',
            contents_map=contents_map,
            description=description,
            **kwargs
        )

        self.contents_map = self.DynamicContentsMap(enforce_object_type_subclass_of, self.contents_map)

    class DynamicContentsMap(dict):
        def __init__(self, enforce_object_type_subclass_of, *args, **kwargs):
            super(PolymorphClassSchema.DynamicContentsMap, self).__init__(*args, **kwargs)

            self._enforce_object_type_subclass_of = enforce_object_type_subclass_of
            self._unresolved_paths = set()

        def get(self, key, default=None):
            if key in self:
                return super(PolymorphClassSchema.DynamicContentsMap, self).__getitem__(key)
            return default

        def __getitem__(self, key):
            self._add_path_to_map_if_available_and_necessary(key)

            return super(PolymorphClassSchema.DynamicContentsMap, self).__getitem__(key)

        def __contains__(self, key):
            if super(PolymorphClassSchema.DynamicContentsMap, self).__contains__(key):
                return True

            self._add_path_to_map_if_available_and_necessary(key)
            return super(PolymorphClassSchema.DynamicContentsMap, self).__contains__(key)

        def _add_path_to_map_if_available_and_necessary(self, path):
            if (
                super(PolymorphClassSchema.DynamicContentsMap, self).__contains__(path) or
                path in self._unresolved_paths
            ):
                return

            if path == '__default__':
                raise ValueError(
                    'You did not specify a key named "__default__" in the polymorph class schema, but you used a '
                    'path for which no module or class could be imported.'
                )

            try:
                item = resolve_python_path(path)
            except (AttributeError, ImportError, ValueError):
                self._unresolved_paths.add(path)
                return

            try:
                schema = item.settings_schema
                if not isinstance(schema, BasicClassSchema):
                    raise ValueError('Schema `{}` for path "{}" must be a `BasicClassSchema`'.format(schema, path))
                if (
                    self._enforce_object_type_subclass_of and
                    not issubclass(schema.object_type, self._enforce_object_type_subclass_of)
                ):
                    raise ValueError(
                        'Schema attribute `settings_schema.object_type` of `{}` for path "{}" must be a '
                        'subclass of `{}`'.format(
                            schema.object_type.__name__,
                            path,
                            self._enforce_object_type_subclass_of.__name__,
                        )
                    )
                self[path] = schema
            except AttributeError:
                self._unresolved_paths.add(path)
