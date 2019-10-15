from __future__ import (
    absolute_import,
    unicode_literals,
)

from typing import Any

from pysoa.common.errors import PySOAError


__all__ = (
    'ConnectionError',
    'InvalidMessageError',
    'MessageReceiveError',
    'MessageReceiveTimeout',
    'MessageSendError',
    'MessageSendTimeout',
    'MessageTooLarge',
    'PySOATransportError',
    'TransientPySOATransportError',
)


class PySOATransportError(PySOAError):
    """
    Base exception for all transport-related PySOA errors.
    """


class MessageTooLarge(PySOATransportError):
    """
    Raised when a message is too large to be sent by the configured transport. This indicates a client- or server-side
    (wherever it was raised) programming error that must be resolved.
    """
    def __init__(self, message_size_in_bytes, *args):  # type: (int, *Any) -> None
        self.message_size_in_bytes = message_size_in_bytes
        super(MessageTooLarge, self).__init__(*args)


class InvalidMessageError(PySOATransportError):
    """
    Raised when the transport cannot send a message because there is some problem with its contents or the way it is
    structured. This is unrelated to serialization and indicates a client- or server-side (wherever it was raised)
    programming error that must be resolved.
    """


class TransientPySOATransportError(PySOATransportError):
    """
    Base exception for transport errors that are typically transient (a failure to send or receive an error) and
    cannot (usually) be resolved my changes to the client- or server-side code.
    """


class MessageReceiveTimeout(TransientPySOATransportError):
    """
    Raised when the transport reaches the timeout waiting to receive a message. On the server side, this is used for
    application control flow: When the server does not receive a message within the specified time, it performs idle
    cleanup operations and then asks the transport for a message again, in a loop, indefinitely. On the client side,
    this means the server did not respond within the specified timeout, and can be the result of several things:

    * The client timeout was set too low for the given action or actions called.
    * The server action code is poorly performant and is taking too long to respond.
    * The server is overloaded and is receiving requests faster than it can process them.
    * The server is currently down.
    """


class MessageSendTimeout(TransientPySOATransportError):
    """
    Raised when the transport encounters a timeout while attempting to send a message. The meaning of such an error
    can vary wildly depending on the configured transport. See the transport documentation for more information.
    """


class MessageReceiveError(TransientPySOATransportError):
    """
    Raised when an error occurs while the transport is attempting to receive a message. The meaning of such an error
    can vary wildly depending on the configured transport. See the transport documentation for more information.
    """


class MessageSendError(TransientPySOATransportError):
    """
    Raised when an error occurs while the transport is attempting to send a message. The meaning of such an error
    can vary wildly depending on the configured transport. See the transport documentation for more information.
    """


class ConnectionError(TransientPySOATransportError):
    """
    Raised when the transport cannot obtain the necessary connection to send or receive a message.
    """
