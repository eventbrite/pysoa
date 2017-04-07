from __future__ import unicode_literals

import re

from pysoa.client import Client
from pysoa.common.types import Error
from pysoa.common.transport.local import ThreadlocalClientTransport
from pysoa.server import Server
from pysoa.server.settings import ServerSettings
from pysoa.server.action import (
    Action,
    ActionError,
)


class StubAction(Action):
    """An Action that simply returns a preset value or error."""

    body = {}
    errors = []

    def run(self, request):
        if self.errors:
            raise ActionError(
                errors=[
                    Error(
                        code=e['code'],
                        message=e['message'],
                        field=e['field'],
                    ) if not isinstance(e, Error) else e for e in self.errors
                ]
            )
        else:
            return self.body


class NoopSerializer:
    mime_type = 'application/noop'

    def dict_to_blob(self, msg):
        return msg

    def blob_to_dict(self, msg):
        return msg


class StubClient(Client):
    """
    A Client for testing code that calls service actions.

    Uses StubClientTransport, which incorporates a server for handling requests. Uses the real Server
    code path, so that developers needing to test their code against particular service responses can
    test against a genuine service in a unit testing environment.
    """

    def __init__(self, service_name='test', action_class_map=None, **kwargs):
        transport = StubClientTransport(service_name=service_name, action_class_map=action_class_map)
        serializer = NoopSerializer()
        super(StubClient, self).__init__(service_name, transport, serializer)

    def stub_action(self, action, body=None, errors=None):
        self.transport.stub_action(action, body=body, errors=errors)


class StubClientTransport(ThreadlocalClientTransport):
    """A transport that incorporates an automatically-configured server for handling requests."""

    def __init__(self, service_name='test', action_class_map=None):
        server_settings = ServerSettings({
            'transport': {
                'path': 'pysoa.common.transport.local:ThreadlocalServerTransport',
            },
            'serializer': {
                'path': 'pysoa.test.stub_service:NoopSerializer',
            },
        })
        self.server = StubServer(server_settings, service_name=service_name, action_class_map=action_class_map)

    def stub_action(self, action, body=None, errors=None):
        self.server.stub_action(action, body=body, errors=errors)


class StubServer(Server):
    """
    A Server that can be configured entirely on initialization, so that stub services do not require new Server
    subclasses.
    """

    def __new__(cls, settings, service_name='test', action_class_map=None):
        instance = super(StubServer, cls).__new__(cls)
        instance.service_name = service_name
        instance.action_class_map = action_class_map or {}
        return instance

    def __init__(self, settings, **kwargs):
        super(StubServer, self).__init__(settings)

    def stub_action(self, action, body=None, errors=None):
        """
        Make a new StubAction class with the given body and errors, and add it to the action_class_map.

        The name of the action class is the action name converted to camel case. For example, an action
        called 'update_foo' will have an action class called UpdateFoo.
        """
        action_class_name = ''.join([part.capitalize() for part in re.split(r'[^a-zA-Z0-9]+', action)])
        new_action_class = type(str(action_class_name), (StubAction,), dict(body=body, errors=errors))
        self.action_class_map[action] = new_action_class
