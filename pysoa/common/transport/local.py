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


class ThreadlocalClientTransport(ClientTransport):

    def __init__(self, service_name, server_class_or_path, server_settings):
        super(ThreadlocalClientTransport, self).__init__(service_name)
        if isinstance(server_class_or_path, basestring):
            try:
                server_class = resolve_python_path(server_class_or_path)
            except (ImportError, AttributeError) as e:
                raise type(e)('Could not resolve server class path {}: {}'.format(server_class_or_path, e))
        else:
            server_class = server_class_or_path

        if server_class.service_name != service_name:
            raise Exception('Server {} service name "{}" does not match "{}"'.format(
                server_class,
                server_class.service_name,
                service_name,
            ))

        if isinstance(server_settings, basestring):
            try:
                settings_dict = resolve_python_path(server_settings)
            except (ImportError, AttributeError) as e:
                raise type(e)('Could not resolve settings path {}: {}'.format(server_settings, e))
        else:
            settings_dict = server_settings

        # Patch settings_dict to use ThreadlocalServerTransport
        settings_dict['transport'] = {
            'path': 'pysoa.common.transport.local:ThreadlocalServerTransport',
        }

        # Create and setup Server instance
        self.server_settings = server_class.settings_class(settings_dict)
        self.server = server_class(self.server_settings)
        self.server.setup()

    def send_request_message(self, request_id, meta, message_string):
        self.server.transport.request_messages.append(
            (
                request_id,
                meta,
                message_string,
            )
        )
        self.server.handle_next_request()

    def receive_response_message(self):
        if self.server.transport.response_messages:
            return self.server.transport.response_messages.popleft()
        return (None, None, None)


class ThreadlocalServerTransport(ServerTransport):

    def __init__(self, *args, **kwargs):
        super(ThreadlocalServerTransport, self).__init__(*args, **kwargs)
        self.request_messages = deque([])
        self.response_messages = deque([])

    def receive_request_message(self):
        if self.request_messages:
            return self.request_messages.popleft()
        raise MessageReceiveTimeout

    def send_response_message(self, request_id, meta, message_string):
        self.response_messages.append(
            (request_id, meta, message_string,)
        )
