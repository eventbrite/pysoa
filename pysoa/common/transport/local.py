from __future__ import unicode_literals
import importlib

from .base import (
    ClientTransport,
    ServerTransport,
)


class ThreadlocalClientTransport(ClientTransport):
    def __init__(self, service_name, server_class, server_settings):
        super(ThreadlocalClientTransport, self).__init__(service_name)

        # Load Server and settings dictionary
        module_name, class_name = server_class.split(':', 1)
        try:
            server_module = importlib.import_module(module_name)
        except ImportError:
            raise ValueError('Cannot import server module {}'.format(module_name))
        try:
            server_class = getattr(server_module, class_name)
        except AttributeError:
            raise ValueError('Cannot find server class "{}" in module {}'.format(
                class_name,
                module_name,
            ))
        try:
            settings_module = importlib.import_module(server_settings)
        except ImportError:
            raise ValueError('Cannot import settings module {}'.format(server_settings))
        try:
            settings_dict = getattr(settings_module, 'settings')
        except AttributeError:
            raise ValueError('Cannot find settings variable in settings module {}'.format(
                server_settings,
            ))

        # Patch settings_dict to use ThreadlocalServerTransport
        settings_dict['transport'] = {
            'path': 'pysoa.common.transport.local:ThreadlocalServerTransport',
        }

        # Create and setup Server instance
        self.server_settings = server_class.settings_class(settings_dict)
        self.server = server_class(self.server_settings)
        self.server.setup()

    def send_request_message(self, request_id, meta, message_string):
        self.server.transport.request_message = (
            request_id,
            meta,
            message_string,
        )
        self.server.handle_next_request()

    def receive_response_message(self):
        if self.server.transport.response_message:
            response_message = self.server.transport.response_message
            self.server.transport.response_message = None
            return response_message

        return (None, None, None)


class ThreadlocalServerTransport(ServerTransport):
    def receive_request_message(self):
        request_message = self.request_message
        self.request_message = None
        return request_message

    def send_response_message(self, request_id, meta, message_string):
        self.response_message = (
            request_id,
            meta,
            message_string,
        )
