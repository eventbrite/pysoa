from __future__ import (
    absolute_import,
    unicode_literals,
)

from collections import deque

from conformity import fields
import six

from pysoa.common.settings import (
    BasicClassSchema,
    resolve_python_path,
)
from pysoa.common.transport.base import (
    ClientTransport,
    ServerTransport,
)


class LocalClientTransport(ClientTransport):
    """A transport that incorporates a server for running a service and client in a single thread."""

    def __init__(self, service_name, metrics, server_class, server_settings):
        """
        :param service_name: The service name
        :type service_name: union[str, unicode]
        :param metrics: The metrics recorder
        :type metrics: MetricsRecorder
        :param server_class: The server class for which this transport will serve as a client
        :type server_class: class
        :param server_settings: The server settings that will be passed to the server class on instantiation
        :type server_settings: dict
        """
        super(LocalClientTransport, self).__init__(service_name, metrics)

        # If the server is specified as a path, resolve it to a class
        if isinstance(server_class, six.string_types):
            try:
                server_class = resolve_python_path(server_class)
            except (ImportError, AttributeError) as e:
                raise type(e)('Could not resolve server class path {}: {}'.format(server_class, e))

        # Make sure the client and the server match names
        if server_class.service_name != service_name:
            raise Exception('Server {} service name "{}" does not match "{}"'.format(
                server_class,
                server_class.service_name,
                service_name,
            ))

        # See if the server settings is actually a string to the path for settings
        if isinstance(server_settings, six.string_types):
            try:
                settings_dict = resolve_python_path(server_settings)
            except (ImportError, AttributeError) as e:
                raise type(e)('Could not resolve settings path {}: {}'.format(server_settings, e))
        else:
            settings_dict = server_settings

        # Patch settings_dict to use LocalServerTransport
        settings_dict['transport'] = {
            'path': 'pysoa.common.transport.local:LocalServerTransport',
        }

        # Set an empty queued request; we'll use this later
        self._current_request = None

        # Set up a deque for responses for just this client
        self.response_messages = deque()

        # Create and setup Server instance
        self.server_settings = server_class.settings_class(settings_dict)
        self.server = server_class(self.server_settings)
        self.server.transport = self
        self.server.setup()

    def send_request_message(self, request_id, meta, body, _=None):
        """
        Receives a request from the client and handles and dispatches in in-thread. `message_expiry_in_seconds` is not
        supported. Messages do not expire, as the server handles the request immediately in the same thread before
        this method returns. This method blocks until the server has completed handling the request.
        """
        self._current_request = (request_id, meta, body)
        try:
            self.server.handle_next_request()
        finally:
            self._current_request = None

    def receive_request_message(self):
        """
        Gives the server the current request (we are actually inside the stack of send_request_message so we know this
        is OK).
        """
        if self._current_request:
            try:
                return self._current_request
            finally:
                self._current_request = None
        else:
            raise RuntimeError('Local server tried to receive message more than once')

    def send_response_message(self, request_id, meta, body):
        """
        Add the response to the deque.
        """
        self.response_messages.append((request_id, meta, body))

    def receive_response_message(self, _=None):
        """
        Receives a message from the deque. `receive_timeout_in_seconds` is not supported. Receive does not time out,
        because by the time the thread calls this method, a response is already available in the deque, or something
        happened and a response will never be available. This method does not wait and returns immediately.
        """
        if self.response_messages:
            return self.response_messages.popleft()
        return None, None, None


class LocalServerTransport(ServerTransport):
    """
    Empty class that we use as an import stub for local transport before we swap in the Client transport instance to do
    double duty.
    """

    def receive_request_message(self):
        """
        Does nothing, because this will never be called (the same-named method on the `LocalClientTransport` is called,
        instead).
        """
        raise TypeError('The LocalServerTransport cannot be used directly; it is a stub.')

    def send_response_message(self, request_id, meta, body):
        """
        Does nothing, because this will never be called (the same-named method on the `LocalClientTransport` is called,
        instead).
        """
        raise TypeError('The LocalServerTransport cannot be used directly; it is a stub.')


class LocalClientTransportSchema(BasicClassSchema):
    contents = {
        'path': fields.UnicodeString(
            description='The path to the local client transport, in the format `module.name:ClassName`',
        ),
        'kwargs': fields.Dictionary({
            # server class can be an import path or a class object
            'server_class': fields.Any(
                fields.UnicodeString(
                    description='The path to the `Server` class, in the format `module.name:ClassName`',
                ),
                fields.ObjectInstance(
                    six.class_types,
                    description='A reference to the `Server`-extending class/type',
                ),
                description='The path to the `Server` class to use locally (as a library), or a reference to the '
                            '`Server`-extending class/type itself',
            ),
            # No deeper validation because the Server will perform its own validation
            'server_settings': fields.SchemalessDictionary(
                key_type=fields.UnicodeString(),
                description='The settings to use when instantiating the `server_class`'
            ),
        }),
    }

    optional_keys = ()

    description = 'The settings for the local client transport'


class LocalServerTransportSchema(BasicClassSchema):
    contents = {
        'path': fields.UnicodeString(
            description='The path to the local server transport, in the format `module.name:ClassName`',
        ),
        'kwargs': fields.Dictionary({}),
    }

    description = 'The settings for the local client transport'


LocalClientTransport.settings_schema = LocalClientTransportSchema(LocalClientTransport)
LocalServerTransport.settings_schema = LocalServerTransportSchema(LocalServerTransport)
