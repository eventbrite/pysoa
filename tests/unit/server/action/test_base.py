from __future__ import (
    absolute_import,
    unicode_literals,
)

from typing import (
    Any,
    Dict,
    Optional,
)
import unittest

from conformity import fields
import six

from pysoa.common.types import ActionResponse
from pysoa.server.action import Action
from pysoa.server.errors import (
    ActionError,
    ResponseValidationError,
)
from pysoa.server.types import EnrichedActionRequest


class TestAction(Action):
    __test__ = False  # So that PyTest doesn't try to collect this and spit out a warning

    request_schema = fields.Dictionary({
        'string_field': fields.UnicodeString(),
    })  # type: Optional[fields.Dictionary]

    response_schema = fields.Dictionary({
        'boolean_field': fields.Boolean(),
    })  # type: Optional[fields.Dictionary]

    _return = None  # type: Optional[Dict[six.text_type, Any]]

    def run(self, request):
        return self._return


class TestActionValidation(unittest.TestCase):
    def setUp(self):
        self.action = TestAction()
        self.action._return = {'boolean_field': True}
        self.action_request = EnrichedActionRequest(
            action='test_action',
            body={
                'string_field': 'a unicode string',
            },
        )

    def test_validate_without_request_schema(self):
        self.action.request_schema = None
        self.action_request.body = {
            'string_field': 123,
        }

        self.action(self.action_request)

    def test_validate_with_request_errors(self):
        self.action_request.body = {
            'string_field': 123,
        }

        with self.assertRaises(ActionError) as error_context:
            self.action(self.action_request)

        self.assertEqual(1, len(error_context.exception.errors))
        self.assertEqual('string_field', error_context.exception.errors[0].field)

    def test_returns_action_response_true(self):
        response = self.action(self.action_request)
        self.assertIsInstance(response, ActionResponse)
        self.assertEqual(self.action_request.action, response.action)
        self.assertEqual({'boolean_field': True}, response.body)

    def test_returns_action_response_false(self):
        self.action._return = {'boolean_field': False}

        response = self.action(self.action_request)
        self.assertIsInstance(response, ActionResponse)
        self.assertEqual(self.action_request.action, response.action)
        self.assertEqual({'boolean_field': False}, response.body)

    def test_response_validation(self):
        self.action._return = {}

        with self.assertRaises(ResponseValidationError):
            self.action(self.action_request)

    def test_no_response(self):
        self.action._return = None
        self.action.response_schema = None

        response = self.action(self.action_request)
        self.assertIsInstance(response, ActionResponse)
        self.assertEqual(self.action_request.action, response.action)
        self.assertEqual({}, response.body)
