"""
Transports are the interface between the Client or Server and the transport backend.

Two base classes are provided, with methods split between Client and Server side. In
many cases, Transport implementations will inherit from both ClientTransport and
ServerTransport and implement both sets of methods, in order to consolidate shared
backend code into a single class.

All Transport methods either accept or return a metadata argument. This should be a
dict that includes any information that is necessary for processing the message, but
is not business logic. For example, if your implementation has multiple serializer
types, the metadata may include a mimetype to tell the endpoint receiving the message
which type of serializer to use.
"""


class MessageTooLarge(Exception):
    pass


class MessageReceiveTimeout(Exception):
    pass


class MessageSendTimeout(Exception):
    pass


class MessageReceiveError(Exception):
    pass


class MessageSendError(Exception):
    pass


class ConnectionError(Exception):
    pass


class ClientTransport(object):

    def send_request_message(self, meta, message_string):
        """
        Send a serialized request message and return a request ID.

        meta: dict
        message_string: bytes (string)

        returns: int
        raises: ConnectionError, MessageSendError, MessageSendTimeout,
            MessageTooLarge
        """
        raise NotImplementedError

    def receive_response_message(self):
        """
        Receive a response message from the backend and return a 3-tuple of
        (request_id, meta, message).

        returns: int, dict, string
        raises: ConnectionError, MessageReceiveError, MessageReceiveTimeout
        """
        raise NotImplementedError


class ServerTransport(object):

    def receive_request_message(self):
        """
        Receive a request message from the backend and return a tuple of
        (meta, message). The metadata may include client reply-to information
        that should be passed back to send_response_message.

        returns: dict, string
        raises: ConnectionError, MessageReceiveError, MessageReceiveTimeout
        """
        raise NotImplementedError

    def send_response_message(self, meta, message_string):
        """
        Send a response message. The meta dict returned by
        receive_request_message should be passed verbatim as the second
        argument.

        meta: dict
        message_string: bytes (string)

        raises: ConnectionError, MessageSendError, MessageSendTimeout,
            MessageTooLarge
        """
        raise NotImplementedError
