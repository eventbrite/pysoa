from __future__ import unicode_literals

from conformity import fields


class BasicClassSchema(fields.Dictionary):
    contents = {
        'path': fields.UnicodeString(),
        'kwargs': fields.SchemalessDictionary(key_type=fields.UnicodeString()),
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
