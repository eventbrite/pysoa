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


__all__ = (
    'ActionRequestSchema',
    'ContextHeaderSchema',
    'ControlHeaderSchema',
    'JobRequestSchema',
)


ActionRequestSchema = Dictionary(
    {
        'action': UnicodeString(description='The name of the service action to execute.'),
        'body': SchemalessDictionary(key_type=UnicodeString(), description='The request parameters for this action.'),
    },
    optional_keys=('body', ),
)
"""The Conformity schema with which action requests are validated."""

ControlHeaderSchema = Dictionary(
    {
        'continue_on_error': Boolean(
            description='Whether to continue executing more actions in a multi-action job request if an action '
                        'results in an error.',
        ),
        'suppress_response': Boolean(
            description='Whether to complete processing a request without sending a response back to the client '
                        '(defaults to false).'
        ),
    },
    allow_extra_keys=True,
    optional_keys=('suppress_response', ),
)

ContextHeaderSchema = Dictionary(
    {
        'caller': UnicodeString(
            description='Optional, caller-supplied meta-information about the caller, such as an application name, '
                        'file name, class or method name, file name and line number, etc. May be useful for logging '
                        'or metrics.',
        ),
        'calling_service': UnicodeString(
            description='A header that PySOA automatically adds to all outgoing requests from one service to another '
                        'when those requests are made with `request.client.call_**(...)` or '
                        '`request.client.send_request(...)`. For example, if Foo Service calls Bar Service, the '
                        'request context that Bar Service receives will include `"calling_service": "foo"`. May be '
                        'useful for logging or metrics.'
        ),
        'correlation_id': UnicodeString(
            description='Correlation IDs can be used at your own discretion, but are generally shared across multiple '
                        'service requests, even across multiple services, to correlate requests that are logically '
                        'linked together (example: such as all PySOA requests that occur within the scope of a single '
                        'HTTP request in a client application). The PySOA client automatically adds a UUID correlation '
                        'ID to all outgoing requests if the client is not already configured with an inherited '
                        'correlation ID, and the client available in `request.client` automatically inherits the '
                        'correlation ID from the request.',
        ),
        'switches': List(Integer(), description='See: :ref:`api-versioning-using-switches`.'),
    },
    allow_extra_keys=True,
    optional_keys=('caller', 'calling_service'),
)

JobRequestSchema = Dictionary(
    {
        'control': ControlHeaderSchema,
        'context': ContextHeaderSchema,
        'actions': List(
            ActionRequestSchema,
            min_length=1,
            description='The list of all actions to execute in this request',
        ),
    },
)
"""The Conformity schema with which job requests are validated."""
