from __future__ import unicode_literals
from collections import deque

from pysoa.common.transport.exceptions import (
    MessageReceiveTimeout,
)
from pysoa.common.settings import resolve_python_path
from .base import (
    ClientTransport,
    ServerTransport,
)


class LocalClientTransport(ClientTransport):

    def __init__(self, service_name, server_class_or_path, server_settings):
        super(LocalClientTransport, self).__init__(service_name)

        # If the server is specified as a path, resolve it to a class
        if isinstance(server_class_or_path, basestring):
            try:
                server_class = resolve_python_path(server_class_or_path)
            except (ImportError, AttributeError) as e:
                raise type(e)('Could not resolve server class path {}: {}'.format(server_class_or_path, e))
        else:
            server_class = server_class_or_path

        # Make sure the client and the server match names
        if server_class.service_name != service_name:
            raise Exception('Server {} service name "{}" does not match "{}"'.format(
                server_class,
                server_class.service_name,
                service_name,
            ))

        # See if the server settings is actually a string to the path for settings
        if isinstance(server_settings, basestring):
            try:
                settings_dict = resolve_python_path(server_settings)
            except (ImportError, AttributeError) as e:
                raise type(e)('Could not resolve settings path {}: {}'.format(server_settings, e))
        else:
            settings_dict = server_settings

        # Patch settings_dict to use ThreadlocalServerTransport
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

    def send_request_message(self, request_id, meta, message_string):
        """
        Receives a request from the client and handles and dispatches in
        in-thread.
        """
        self._current_request = (request_id, meta, message_string)
        try:
            self.server.handle_next_request()
        finally:
            self._current_request = None

    def receive_request_message(self):
        """
        Gives the server the current request (we are actually inside the stack
        of send_request_message so we know this is OK)
        """
        if self._current_request:
            try:
                return self._current_request
            finally:
                self._current_request = None
        else:
            raise RuntimeError("Local server tried to receive message more than once")

    def send_response_message(self, request_id, meta, message_string):
        """
        Add the response to the deque
        """
        self.response_messages.append(
            (request_id, meta, message_string,)
        )

    def receive_response_message(self):
        """
        Give them a message from the deque
        """
        if self.response_messages:
            return self.response_messages.popleft()
        return (None, None, None)


class LocalServerTransport(ServerTransport):
    """
    Empty class that we use as an import stub for local transport before
    we swap in the Client transport instance to do double duty.
    """
