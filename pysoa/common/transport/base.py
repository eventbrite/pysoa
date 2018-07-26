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

import six

from pysoa.common.metrics import NoOpMetricsRecorder


def get_hex_thread_id():
    return '{:012x}'.format(threading.current_thread().ident)


@six.add_metaclass(abc.ABCMeta)
class ClientTransport(object):

    def __init__(self, service_name, metrics=NoOpMetricsRecorder()):
        """
        :param service_name: The name of the service to which this transport will send requests (and from which it will
                             receive responses)
        :type service_name: union[str, unicode]
        :param metrics: The optional metrics recorder
        :type metrics: MetricsRecorder
        """
        self.service_name = service_name
        self.metrics = metrics

    @abc.abstractmethod
    def send_request_message(self, request_id, meta, body, message_expiry_in_seconds=None):
        """
        Send a request message.

        :param request_id: The request ID
        :type request_id: int
        :param meta: Meta information about the message
        :type meta: dict
        :param body: The message body
        :type body: dict
        :param message_expiry_in_seconds: How soon the message should expire if not retrieved by a server
                                          (implementations should provide a sane default or setting for default)
        :type message_expiry_in_seconds: int

        :raise: ConnectionError, MessageSendError, MessageSendTimeout, MessageTooLarge
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def receive_response_message(self, receive_timeout_in_seconds=None):
        """
        Receive a response message from the backend and return a 3-tuple of (request_id, meta dict, message dict).

        :param receive_timeout_in_seconds: How long to block waiting for a response to become available
                                           (implementations should provide a sane default or setting for default)
        :type receive_timeout_in_seconds: int

        :return: A tuple of the request ID, meta dict, and message dict, in that order
        :rtype: tuple

        :raise: ConnectionError, MessageReceiveError, MessageReceiveTimeout
        """
        raise NotImplementedError()


@six.add_metaclass(abc.ABCMeta)
class ServerTransport(object):

    def __init__(self, service_name, metrics=NoOpMetricsRecorder()):
        """
        :param service_name: The name of the service for which this transport will receive requests and send responses
        :type service_name: union[str, unicode]
        :param metrics: The optional metrics recorder
        :type metrics: MetricsRecorder
        """
        self.service_name = service_name
        self.metrics = metrics

    @abc.abstractmethod
    def receive_request_message(self):
        """
        Receive a request message from the backend and return a 3-tuple of (request_id, meta dict, message dict). The
        metadata may include client reply-to information that should be passed back to send_response_message.

        :return: A tuple of the request ID, meta dict, and message dict, in that order
        :rtype: tuple

        :raise: ConnectionError, MessageReceiveError, MessageReceiveTimeout
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def send_response_message(self, request_id, meta, body):
        """
        Send a response message. The meta dict returned by receive_request_message should be passed verbatim as the
        second argument.

        :param request_id: The request ID
        :type request_id: int
        :param meta: Meta information about the message
        :type meta: dict
        :param body: The message body
        :type body: dict

        :raise: ConnectionError, MessageSendError, MessageSendTimeout, MessageTooLarge
        """
        raise NotImplementedError()
