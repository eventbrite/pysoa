from __future__ import unicode_literals

import re

from pysoa.client.client import (
    Client,
    ServiceHandler,
)
from pysoa.client.settings import ClientSettings
from pysoa.common.metrics import NoOpMetricsRecorder
from pysoa.common.transport.local import LocalClientTransport
from pysoa.common.types import Error
from pysoa.server import Server
from pysoa.server.action import (
    Action,
    ActionError,
)


def _make_stub_action(action_name, body=None, errors=None):
    body = body or {}
    errors = errors or {}
    action_class_name = ''.join([part.capitalize() for part in re.split(r'[^a-zA-Z0-9]+', action_name)])
    return type(
        str(action_class_name),
        (StubAction,),
        dict(body=body, errors=errors),
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


class StubClientSettings(ClientSettings):
    defaults = {
        'transport': {
            'path': 'pysoa.test.stub_service:StubClientTransport'
        }
    }


class StubClient(Client):
    """
    A Client for testing code that calls service actions.

    Uses StubClientTransport, which incorporates a server for handling requests. Uses the real Server
    code path, so that developers needing to test their code against particular service responses can
    test against a genuine service in a unit testing environment.
    """

    settings_class = StubClientSettings

    def __init__(self, service_action_map=None, **_):
        """
        Generate settings based on a mapping of service names to actions.

        Args:
            service_action_map: dict of {service_name: <action map>}
        """
        service_action_map = service_action_map or {}
        config = {}
        for service_name, action_map in service_action_map.items():
            config[service_name] = {
                'transport': {
                    'kwargs': {
                        'action_map': action_map,
                    }
                }
            }
        super(StubClient, self).__init__(config)

    def stub_action(self, service_name, action, body=None, errors=None):
        if service_name not in self.handlers:
            self.handlers[service_name] = ServiceHandler(service_name, self.settings_class({}))
        self.handlers[service_name].transport.stub_action(action, body=body, errors=errors)


class StubClientTransport(LocalClientTransport):
    """A transport that incorporates an automatically-configured Server for handling requests."""

    def __init__(self, service_name='test', metrics=None, action_map=None):
        """
        Configure a StubServer to handle requests. Creates a new subclass of StubServer using the service name and
        action mapping provided.

        Args:
            service_name: string
            action_map: dict of {action_name: {'body': action_body, 'errors': action_errors}} where action_body is a
                dict and action_errors is a list
        """
        action_map = action_map or {}
        # Build the action_class_map property for the new Server class
        action_class_map = {
            name: _make_stub_action(name, a.get('body', {}), a.get('errors', [])) for name, a in action_map.items()
        }
        # Create the new Server subclass
        server_class_name = ''.join([part.capitalize() for part in re.split(r'[^a-zA-Z0-9]+', service_name)]) + 'Server'
        server_class = type(
            str(server_class_name),
            (StubServer,),
            dict(service_name=service_name, action_class_map=action_class_map),
        )
        super(StubClientTransport, self).__init__(service_name, metrics or NoOpMetricsRecorder(), server_class, {})

    def stub_action(self, action, body=None, errors=None):
        self.server.stub_action(action, body=body, errors=errors)


class StubServer(Server):
    """A Server that provides an interface to stub actions, i.e. define actions inline, for testing purposes."""

    def stub_action(self, action, body=None, errors=None):
        """
        Make a new StubAction class with the given body and errors, and add it to the action_class_map.

        The name of the action class is the action name converted to camel case. For example, an action
        called 'update_foo' will have an action class called UpdateFoo.
        """
        self.action_class_map[action] = _make_stub_action(action, body, errors)
