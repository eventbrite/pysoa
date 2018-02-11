from __future__ import absolute_import, unicode_literals

import unittest

from conformity import fields

from pysoa.common.constants import ERROR_CODE_INVALID
from pysoa.server.action.introspection import IntrospectionAction
from pysoa.server.action.status import (
    BaseStatusAction,
    StatusActionFactory,
)
from pysoa.server.errors import ActionError
from pysoa.server.server import Server
from pysoa.server.types import EnrichedActionRequest


class FakeActionOne(object):
    """Test action documentation"""

    description = 'The real documentation'


class FakeActionTwo(object):
    """Test action documentation"""

    request_schema = fields.UnicodeString(description='Be weird.')

    response_schema = fields.Dictionary(
        {
            'okay': fields.Boolean(description='Whether it is okay'),
            'reason': fields.Nullable(fields.UnicodeString(description='Why it is not okay')),
        }
    )


class FakeServerOne(Server):
    """This is the documentation we should get"""

    action_class_map = {
        'status': StatusActionFactory('1.2.3'),
        'one': FakeActionOne,
    }

    settings = {}

    # noinspection PyMissingConstructor
    def __init__(self):
        pass  # Do not call super


class FakeServerTwo(Server):
    """This is NOT the documentation we should get"""

    description = 'Instead, we should get this documentation'

    action_class_map = {
        'introspect': IntrospectionAction,
        'one': FakeActionOne,
        'two': FakeActionTwo,
    }

    settings = {}

    # noinspection PyMissingConstructor
    def __init__(self):
        pass  # Do not call super


class TestIntrospectionAction(unittest.TestCase):
    def test_null_action_name(self):
        action = IntrospectionAction(FakeServerOne())

        with self.assertRaises(ActionError) as error_context:
            action(EnrichedActionRequest(action='introspect', body={'action_name': None}))

        self.assertEqual(1, len(error_context.exception.errors))
        self.assertEqual(ERROR_CODE_INVALID, error_context.exception.errors[0].code)
        self.assertEqual('action_name', error_context.exception.errors[0].field)

    def test_invalid_action_name(self):
        action = IntrospectionAction(FakeServerOne())

        with self.assertRaises(ActionError) as error_context:
            action(EnrichedActionRequest(action='introspect', body={'action_name': 'not_a_defined_action'}))

        self.assertEqual(1, len(error_context.exception.errors))
        self.assertEqual(ERROR_CODE_INVALID, error_context.exception.errors[0].code)
        self.assertEqual('action_name', error_context.exception.errors[0].field)

    def test_single_action_simple(self):
        action = IntrospectionAction(FakeServerOne())

        response = action(EnrichedActionRequest(action='introspect', body={'action_name': 'one'}))

        self.assertEqual([], response.errors)
        self.assertEqual(
            {
                'action_names': ['one'],
                'actions': {
                    'one': {
                        'documentation': 'The real documentation',
                        'request_schema': None,
                        'response_schema': None,
                    },
                },
            },
            response.body,
        )

    def test_single_action_complex(self):
        action = IntrospectionAction(FakeServerTwo())

        response = action(EnrichedActionRequest(action='introspect', body={'action_name': 'two'}))

        self.assertEqual([], response.errors)
        self.assertEqual(
            {
                'action_names': ['two'],
                'actions': {
                    'two': {
                        'documentation': 'Test action documentation',
                        'request_schema': FakeActionTwo.request_schema.introspect(),
                        'response_schema': FakeActionTwo.response_schema.introspect(),
                    },
                },
            },
            response.body,
        )

    def test_single_action_introspect_default(self):
        action = IntrospectionAction(FakeServerOne())

        response = action(EnrichedActionRequest(action='introspect', body={'action_name': 'introspect'}))

        self.assertEqual([], response.errors)
        self.assertEqual(
            {
                'action_names': ['introspect'],
                'actions': {
                    'introspect': {
                        'documentation': IntrospectionAction.description,
                        'request_schema': IntrospectionAction.request_schema.introspect(),
                        'response_schema': IntrospectionAction.response_schema.introspect(),
                    },
                },
            },
            response.body,
        )

    def test_single_action_status_default(self):
        action = IntrospectionAction(FakeServerTwo())

        response = action(EnrichedActionRequest(action='introspect', body={'action_name': 'status'}))

        self.assertEqual([], response.errors)
        self.assertEqual(
            {
                'action_names': ['status'],
                'actions': {
                    'status': {
                        'documentation': BaseStatusAction.description,
                        'request_schema': BaseStatusAction.request_schema.introspect(),
                        'response_schema': BaseStatusAction.response_schema.introspect(),
                    },
                },
            },
            response.body,
        )

    def test_whole_server_simple(self):
        action = IntrospectionAction(FakeServerOne())

        response = action(EnrichedActionRequest(action='introspect', body={}))

        self.assertEqual([], response.errors)
        self.assertEqual(
            {
                'documentation': 'This is the documentation we should get',
                'action_names': ['introspect', 'one', 'status'],
                'actions': {
                    'introspect': {
                        'documentation': IntrospectionAction.description,
                        'request_schema': IntrospectionAction.request_schema.introspect(),
                        'response_schema': IntrospectionAction.response_schema.introspect(),
                    },
                    'status': {
                        'documentation': BaseStatusAction.description,
                        'request_schema': BaseStatusAction.request_schema.introspect(),
                        'response_schema': BaseStatusAction.response_schema.introspect(),
                    },
                    'one': {
                        'documentation': 'The real documentation',
                        'request_schema': None,
                        'response_schema': None,
                    },
                },
            },
            response.body
        )

    def test_whole_server_complex(self):
        action = IntrospectionAction(FakeServerTwo())

        response = action(EnrichedActionRequest(action='introspect', body={}))

        self.assertEqual([], response.errors)
        self.assertEqual(
            {
                'documentation': 'Instead, we should get this documentation',
                'action_names': ['introspect', 'one', 'status', 'two'],
                'actions': {
                    'introspect': {
                        'documentation': IntrospectionAction.description,
                        'request_schema': IntrospectionAction.request_schema.introspect(),
                        'response_schema': IntrospectionAction.response_schema.introspect(),
                    },
                    'status': {
                        'documentation': BaseStatusAction.description,
                        'request_schema': BaseStatusAction.request_schema.introspect(),
                        'response_schema': BaseStatusAction.response_schema.introspect(),
                    },
                    'one': {
                        'documentation': 'The real documentation',
                        'request_schema': None,
                        'response_schema': None,
                    },
                    'two': {
                        'documentation': 'Test action documentation',
                        'request_schema': FakeActionTwo.request_schema.introspect(),
                        'response_schema': FakeActionTwo.response_schema.introspect(),
                    },
                },
            },
            response.body
        )
