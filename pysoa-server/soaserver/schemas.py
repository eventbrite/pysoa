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
        'body': SchemalessDictionary(),
    },
    optional_keys=['body'],
)

ControlHeaderSchema = Dictionary(
    {
        'switches': List(Integer()),
        'continue_on_error': Boolean(),
        'correllation_id': UnicodeString(),
    }
)

JobRequestSchema = Dictionary(
    {
        'control': ControlHeaderSchema,
        'actions': List(ActionRequestSchema),
    }
)
