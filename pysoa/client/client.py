"""
The Client provides a simple interface for calling actions on Servers.

The base Client class provides the core workflow for request sending and receiving.
Requests are passed and returned as dicts, and the format of the request depends on the
implementation.

The on_request and on_response methods provide hooks for any actions that need to be
taken after a successful request or response. These may include, for example, logging
all requests and responses or raising exceptions on error responses.
"""


class Client(object):

    middleware_classes = []

    def __init__(self, service_name, transport, serializer):
        self.service_name = service_name
        self.transport = transport
        self.serializer = serializer
        self.middleware = [
            middleware_class() for middleware_class in self.middleware_classes
        ]

    def prepare_request(self, request_dict):
        """
        Pre-process the message dict. Returns metadata and the processed message dict.
        Implementations may override this method to inject necessary metadata, format
        requests and so on.

        message_dict: dict

        returns: dict
        """
        for middleware in self.middleware:
            middleware.process_request_dict(request_dict)

    def prepare_metadata(self):
        """
        Return a dict containing metadata that will be passed to
        Transport.send_request_message. Implementations should override this method to
        include any metadata required by their Transport classes.

        returns: dict
        """
        return {}

    def prepare_response(self, response_dict):
        """
        Pre-process and return the response. Implementations may override this to, for
        example, format response messages or raise exceptions on error responses.

        meta: dict
        message_dict: dict

        returns: dict
        """
        for middleware in self.middleware:
            middleware.process_response_dict(response_dict)

    def on_request(self, request_id, meta, message_dict):
        """
        Hook for any actions that occur after a request is sent on the transport.

        request_id: int
        meta: dict
        message_dict: dict
        """
        pass

    def on_response(self, request_id, meta, message_dict):
        """
        Hook for any actions that occur after a response is received on the transport.

        request_id: int
        meta: dict
        message_dict: dict
        """
        pass

    def send_request(self, message_dict):
        """
        Serialize and send a request message, and return a request ID.

        returns: int
        raises: ConnectionError, InvalidField, MessageSendError, MessageSendTimeout,
            MessageTooLarge
        """
        self.prepare_request(message_dict)
        meta = self.prepare_metadata()
        message = self.serializer.dict_to_blob(message_dict)
        request_id = self.transport.send_request_message(meta, message)
        self.on_request(request_id, meta, message_dict)
        return request_id

    def get_all_responses(self):
        """
        Receive all available responses from the trasnport as a generator.

        yields: (int, dict)
        raises: ConnectionError, MessageReceiveError, MessageReceiveTimeout, InvalidMessage,
            StopIteration
        """
        while True:
            request_id, meta, message = self.transport.receive_response_message()
            if message is None:
                break
            else:
                message_dict = self.serializer.blob_to_dict(message)
                self.prepare_response(message_dict)
                self.on_response(request_id, meta, message_dict)
                yield request_id, message_dict
