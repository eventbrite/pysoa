from __future__ import (
    absolute_import,
    unicode_literals,
)

from typing import Mapping
from unittest import TestCase

from conformity import fields
import six

from pysoa.common.transport.base import ServerTransport
from pysoa.server.server import Server
from pysoa.server.types import ActionType
from pysoa.test import factories


class HandleNextRequestServer(Server):
    """
    Stub server to test against.
    """
    service_name = 'test_service'
    action_class_map = {}  # type: Mapping[six.text_type, ActionType]


@fields.ClassConfigurationSchema.provider(fields.Dictionary({}))
class SimplePassthroughServerTransport(ServerTransport):
    def set_request(self, request):
        self._request = request

    def receive_request_message(self):
        return (0, {}, self._request)

    def send_response_message(self, request_id, meta, body):
        self._response = body

    def get_response(self):
        return self._response


class TestProcessNextRequests(TestCase):
    def test_emtpy_request_returns_job_response_error(self):
        """
        Test that server can handle an emtpy job missing top level elements without throwing exceptions
        """
        settings = factories.ServerSettingsFactory()
        server = HandleNextRequestServer(settings=settings)
        server.transport = SimplePassthroughServerTransport(server.service_name)

        server.transport.set_request({})
        server.handle_next_request()
        response = server.transport.get_response()

        # Make sure we got an error
        self.assertTrue('errors' in response)
        errors = response['errors']
        self.assertEqual(len(errors), 3)
        self.assertEqual({'actions', 'control', 'context'}, set([e.get('field', None) for e in errors]))
