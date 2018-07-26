from __future__ import (
    absolute_import,
    unicode_literals,
)

from conformity.fields import (
    Boolean,
    Dictionary,
    Integer,
    List,
    SchemalessDictionary,
    UnicodeString,
)


ActionRequestSchema = Dictionary(
    {
        'action': UnicodeString(),
        'body': SchemalessDictionary(key_type=UnicodeString()),
    },
    optional_keys=['body'],
)

ControlHeaderSchema = Dictionary(
    {
        'continue_on_error': Boolean(),
    },
    allow_extra_keys=True,
)

ContextHeaderSchema = Dictionary(
    {
        'switches': List(Integer()),
        'correlation_id': UnicodeString(),
    },
    allow_extra_keys=True,
)

JobRequestSchema = Dictionary(
    {
        'control': ControlHeaderSchema,
        'context': ContextHeaderSchema,
        'actions': List(ActionRequestSchema, min_length=1),
    },
)
