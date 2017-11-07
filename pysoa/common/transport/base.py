"""
Transports are the interface between the Client or Server and the transport backend.

Two base classes are provided, with methods split between Client and Server side. In
many cases, Transport implementations will inherit from both ClientTransport and
ServerTransport and implement both sets of methods, in order to consolidate shared
backend code into a single class.

All Transport methods either accept or return a metadata argument. This should be a
dict that includes any information that is necessary for processing the message, but
is not business logic. For example, if your implementation has multiple serializer
types, the metadata may include a mime type to tell the endpoint receiving the message
which type of serializer to use.
"""
from pysoa.common.metrics import NoOpMetricsRecorder


class ClientTransport(object):

    def __init__(self, service_name, metrics=NoOpMetricsRecorder()):
        self.service_name = service_name
        self.metrics = metrics

    def send_request_message(self, request_id, meta, message_string):
        """
        Send a serialized request message.

        Args:
            request_id: int
            meta: dict
            message_string: bytes (string)
        Returns:
            None
        Raises:
            ConnectionError, MessageSendError, MessageSendTimeout, MessageTooLarge
        """
        raise NotImplementedError

    def receive_response_message(self):
        """
        Receive a response message from the backend and return a 3-tuple of
        (request_id, meta, message).

        Returns:
            (int, string)
        Raises:
            ConnectionError, MessageReceiveError, MessageReceiveTimeout
        """
        raise NotImplementedError


class ServerTransport(object):

    def __init__(self, service_name, metrics=NoOpMetricsRecorder()):
        self.service_name = service_name
        self.metrics = metrics

    def receive_request_message(self):
        """
        Receive a request message from the backend and return a 3-tuple of
        (request_id, meta, message). The metadata may include client reply-to information
        that should be passed back to send_response_message.

        Returns:
            (int, dict, string)
        Raises:
            ConnectionError, MessageReceiveError, MessageReceiveTimeout
        """
        raise NotImplementedError

    def send_response_message(self, request_id, meta, message_string):
        """
        Send a response message. The meta dict returned by
        receive_request_message should be passed verbatim as the second
        argument.

        Args:
            request_id: int
            meta: dict
            message_string: bytes (string)
        Returns:
            None
        Raises:
            ConnectionError, MessageSendError, MessageSendTimeout, MessageTooLarge
        """
        raise NotImplementedError
