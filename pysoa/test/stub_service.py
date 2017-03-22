from pysoa.client import Client
from pysoa.common.types import Error
from pysoa.common.constants import ERROR_CODE_UNKNOWN
from pysoa.common.transport.base import ClientTransport


class NoopSerializer:
    mime_type = 'application/noop'

    def dict_to_blob(self, msg):
        return msg

    def blob_to_dict(self, msg):
        return msg


class StubClient(Client):
    """
    A Client for use in testing code that calls service actions.

    Allows the user to define "stubbed" actions that will return pre-defined values.
    Stubs can be passed either as a dictionary mapping action names to values, or added
    one by one by calling stub_action().
    """

    def __init__(self, stubbed_actions=None, *args, **kwargs):
        self.transport = StubTransport(stubbed_actions=stubbed_actions)
        self.serializer = NoopSerializer()

    def stub_action(self, action, body=None, errors=None):
        self.transport.stub_action(action, body=body, errors=errors)


class StubTransport(ClientTransport):
    """
    A transport for use in testing Clients.

    Incorporates a StubServer that imitates action responses.
    """

    def __init__(self, stubbed_actions=None):
        self.stub_server = StubServer(actions=stubbed_actions)
        self.messages = []

    def stub_action(self, action, body=None, errors=None):
        self.stub_server.stub_action(action, body=body, errors=errors)

    def send_request_message(self, request_id, meta, request):
        self.messages.append((request_id, meta, request))
        return request_id

    def receive_response_message(self):
        if self.messages:
            request_id, meta, request = self.messages.pop(0)
            response = self.stub_server.process_message(request)
            return (request_id, meta, response)
        return (None, None, None)


class StubServer():
    """
    Imitates a server, for testing clients.

    Stores a mapping of stubbed actions that can be either raw responses or callables,
    and can be called by the StubTransport to return these responses.
    """

    def __init__(self, actions=None):
        self.serializer = NoopSerializer()
        self.actions = actions or {}

    def stub_action(self, action, body=None, errors=None):
        self.actions[action] = {
            'body': body or {},
            'errors': errors or [],
        }

    def process_message(self, request):
        """Return the stubbed message or the original message if none is available."""
        request = self.serializer.blob_to_dict(request)
        response = {'actions': []}
        for action in request['actions']:
            action_name = action['action']
            if action_name not in self.actions:
                response['actions'].append(Error(
                    ERROR_CODE_UNKNOWN,
                    'Unknown action',
                    'action'
                ))
                continue
            result = self.actions.get(action_name)
            if callable(result):
                result = result(action['body'])
            result['action'] = action_name
            response['actions'].append(result)
        return self.serializer.dict_to_blob(response)
