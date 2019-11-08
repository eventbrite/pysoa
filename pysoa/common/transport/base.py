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
from __future__ import (
    absolute_import,
    unicode_literals,
)

import abc
import threading
from typing import (
    Any,
    Dict,
    NamedTuple,
    Optional,
)

from pymetrics.recorders.base import MetricsRecorder
from pymetrics.recorders.noop import noop_metrics
import six


__all__ = (
    'ClientTransport',
    'get_hex_thread_id',
    'ReceivedMessage',
    'ServerTransport',
    'Transport',
)


def get_hex_thread_id():  # type: () -> six.text_type
    thread_id = threading.current_thread().ident
    return '{:012x}'.format(thread_id if thread_id is not None else 0)


ReceivedMessage = NamedTuple(
    'ReceivedMessage',
    (
        ('request_id', Optional[int]),
        ('meta', Optional[Dict[six.text_type, Any]]),
        ('body', Optional[Dict[six.text_type, Any]]),
    ),
)
"""The representation of a message received through a transport."""


@six.add_metaclass(abc.ABCMeta)
class Transport(object):
    """
    A base transport from which all client and server transports inherit, establishing base metrics and service name
    attributes.
    """

    def __init__(self, service_name, metrics=noop_metrics):
        # type: (six.text_type, MetricsRecorder) -> None
        """
        :param service_name: The name of the service to which this transport will send requests (and from which it will
                             receive responses)
        :param metrics: The optional metrics recorder
        """
        if not isinstance(service_name, six.text_type):
            raise ValueError('service_name must be a unicode string')
        if not isinstance(metrics, MetricsRecorder):
            raise ValueError('metrics must be a MetricsRecorder')

        self.service_name = service_name
        self.metrics = metrics


@six.add_metaclass(abc.ABCMeta)
class ClientTransport(Transport):
    """
    The base client transport defining the interface for transacting PySOA payloads on the client side.
    """

    @abc.abstractmethod
    def send_request_message(self, request_id, meta, body, message_expiry_in_seconds=None):
        # type: (int, Dict[six.text_type, Any], Dict[six.text_type, Any], Optional[int]) -> None
        """
        Send a request message.

        :param request_id: The request ID
        :param meta: Meta information about the message
        :param body: The message body
        :param message_expiry_in_seconds: How soon the message should expire if not retrieved by a server
                                          (implementations should provide a sane default or setting for default)

        :raise: ConnectionError, MessageSendError, MessageSendTimeout, MessageTooLarge
        """

    @abc.abstractmethod
    def receive_response_message(self, receive_timeout_in_seconds=None):
        # type: (Optional[int]) -> ReceivedMessage
        """
        Receive a response message from the backend and return a 3-tuple of (request_id, meta dict, message dict).

        :param receive_timeout_in_seconds: How long to block waiting for a response to become available
                                           (implementations should provide a sane default or setting for default)

        :return: A named tuple ReceivedMessage of the request ID, meta dict, and message dict, in that order

        :raise: ConnectionError, MessageReceiveError, MessageReceiveTimeout
        """


@six.add_metaclass(abc.ABCMeta)
class ServerTransport(Transport):
    """
    The base server transport defining the interface for transacting PySOA payloads on the server side.
    """

    @abc.abstractmethod
    def receive_request_message(self):
        # type: () -> ReceivedMessage
        """
        Receive a request message from the backend and return a 3-tuple of (request_id, meta dict, message dict). The
        metadata may include client reply-to information that should be passed back to send_response_message.

        :return: A named tuple ReceivedMessage of the request ID, meta dict, and message dict, in that order

        :raise: ConnectionError, MessageReceiveError, MessageReceiveTimeout
        """

    @abc.abstractmethod
    def send_response_message(self, request_id, meta, body):
        # type: (int, Dict[six.text_type, Any], Dict[six.text_type, Any]) -> None
        """
        Send a response message. The meta dict returned by receive_request_message should be passed verbatim as the
        second argument.

        :param request_id: The request ID
        :param meta: Meta information about the message
        :param body: The message body

        :raise: ConnectionError, MessageSendError, MessageSendTimeout, MessageTooLarge
        """
