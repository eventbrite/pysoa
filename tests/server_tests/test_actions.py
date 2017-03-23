from conformity import fields

from pysoa.common.types import (
    ActionRequest,
    ActionResponse,
)
from pysoa.server.action import Action
from pysoa.server.errors import ActionError

import pytest


class TestAction(Action):
    request_schema = fields.Dictionary({
        'string_field': fields.UnicodeString(),
    })

    def run(self, request):
        pass


class TestActionValidation(object):
    def setup_method(self, method):
        self.action = TestAction()
        self.action_request = ActionRequest(
            action='test_action',
            body={
                'string_field': u'a unicode string',
            },
            switches=None,
        )

    def test_validate_without_request_schema(self):
        self.action.request_schema = None
        self.action_request.body = {
            'string_field': 123,
        }

        try:
            self.action(self.action_request)
        except ActionError:
            pytest.fail('An unexpected ActionError was raised.')

    def test_validate_without_request_errors(self):
        try:
            self.action(self.action_request)
        except ActionError:
            pytest.fail('An unexpected ActionError was raised.')

    def test_validate_with_request_errors(self):
        self.action_request.body = {
            'string_field': 123,
        }

        with pytest.raises(ActionError) as e:
            self.action(self.action_request)

        assert len(e.value.errors) == 1
        assert e.value.errors[0].field == u'string_field'

    def test_returns_action_response(self):
        response = self.action(self.action_request)
        assert isinstance(response, ActionResponse)
        assert response.action == self.action_request.action
