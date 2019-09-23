from __future__ import (
    absolute_import,
    unicode_literals,
)


__all__ = (
    'ConnectionError',
    'InvalidMessageError',
    'MessageReceiveError',
    'MessageReceiveTimeout',
    'MessageSendError',
    'MessageSendTimeout',
    'MessageTooLarge',
)


class MessageTooLarge(Exception):
    """
    Raised when a message is too large to be send by the configured transport.
    """
    def __init__(self, message_size_in_bytes, *args):
        self.message_size_in_bytes = message_size_in_bytes
        super(MessageTooLarge, self).__init__(*args)


class MessageReceiveTimeout(Exception):
    """
    Raised when the transport reaches the timeout waiting to receive a message.
    """


class MessageSendTimeout(Exception):
    """
    Raised when the transport encounters a timeout while attempting to send a message.
    """


class MessageReceiveError(Exception):
    """
    Raised when an error occurs while the transport is attempting to receive a message.
    """


class MessageSendError(Exception):
    """
    Raised when an error occurs while the transport is attempting to send a message.
    """


class ConnectionError(Exception):
    """
    Raised when the transport cannot obtain the necessary connection to send or receive a message.
    """


class InvalidMessageError(Exception):
    """
    Raised when the transport cannot serialize or deserialize the message because it is not valid in some way.
    """
