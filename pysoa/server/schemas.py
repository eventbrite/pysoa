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
        'switches': List(Integer()),
        'continue_on_error': Boolean(),
        'correlation_id': UnicodeString(),
    },
    allow_extra_keys=True,
)

JobRequestSchema = Dictionary(
    {
        'control': ControlHeaderSchema,
        'context': SchemalessDictionary(key_type=UnicodeString()),
        'actions': List(ActionRequestSchema),
    },
    optional_keys=['context'],
)
