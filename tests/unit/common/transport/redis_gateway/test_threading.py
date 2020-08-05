from __future__ import (
    absolute_import,
    unicode_literals,
)

import threading
import time
from typing import (
    Dict,
    List,
)
import unittest

from pymetrics.recorders.noop import noop_metrics
import six

from pysoa.common.transport.errors import MessageReceiveTimeout
from pysoa.common.transport.redis_gateway.client import RedisClientTransport
from pysoa.common.transport.redis_gateway.constants import REDIS_BACKEND_TYPE_STANDARD
from pysoa.common.transport.redis_gateway.server import RedisServerTransport
from pysoa.test.compatibility import mock


class _FakeBackend(object):
    """
    This fake Redis backend is not thread-safe. That's okay. We don't need it to be for this test, because we are
    intentionally controlling the timing of things.
    """
    def __init__(self):
        self._container = {}  # type: Dict[six.text_type, List[six.binary_type]]

    def get_connection(self, *_):
        return self

    def send_message_to_queue(self, queue_key, message, *_, **__):
        # print('\n    - send: {} / {} / {}\n'.format(queue_key, type(message), message))
        self._container.setdefault(queue_key, list()).append(message)

    def blpop(self, keys, *_, **__):
        if self._container.get(keys[0]):
            message = self._container[keys[0]].pop(0)
            # print('\n    - receive: {} / {} / {}\t'.format(keys[0], type(message), message))
            return [keys[0], message]
        return None


class _FakeEchoingServer(threading.Thread):
    """
    This is a super simple server that simply receives requests and immediately replies with responses.
    """
    def __init__(self, server_transport):
        self._transport = server_transport
        self._continue = True
        self.error = None

        super(_FakeEchoingServer, self).__init__()

    def shutdown(self):
        self._continue = False

    def run(self):
        while self._continue is True:
            try:
                # print('  - server receive')
                request_id, meta, body = self._transport.receive_request_message()
                # print('  - server send')
                self._transport.send_response_message(request_id, meta, body)
            except MessageReceiveTimeout:
                time.sleep(0.05)
            except Exception as e:
                self.error = e
                break


class _FakeClient(threading.Thread):
    def __init__(self, name, client_transport, payload, receive_delay):
        self._transport = client_transport
        self._payload = payload
        self._receive_delay = receive_delay
        self.error = None

        super(_FakeClient, self).__init__(name=name)

    def run(self):
        # print('  - client send')
        self._transport.send_request_message(0, {}, self._payload)
        time.sleep(self._receive_delay)

        try:
            # print('  - client receive')
            request_id, _, response = self._transport.receive_response_message()
            assert request_id == 0, 'Expected request ID to be 0, was {} (thread {})'.format(request_id, self.name)
            assert response == self._payload, 'Expected payload to be {}, was {} (thread {})'.format(
                self._payload,
                response,
                self.name,
            )
        except Exception as e:
            self.error = e


class TestThreadSafety(unittest.TestCase):
    @staticmethod
    def _test():
        backend = _FakeBackend()

        server_transport = RedisServerTransport(
            'threaded',
            noop_metrics,
            1,
            backend_type=REDIS_BACKEND_TYPE_STANDARD,
        )
        server_transport.core._backend_layer = backend  # type: ignore

        client_transport = RedisClientTransport(
            'threaded',
            noop_metrics,
            backend_type=REDIS_BACKEND_TYPE_STANDARD,
        )
        client_transport.core._backend_layer = backend  # type: ignore

        server = _FakeEchoingServer(server_transport)

        client1 = _FakeClient('client-1', client_transport, {'key1': 'value1'}, 1.0)
        client2 = _FakeClient('client-2', client_transport, {'key2': 'value2'}, 0.25)

        server.start()

        client1.start()
        client2.start()
        client1.join(timeout=2)
        client2.join(timeout=2)

        server.shutdown()
        server.join(timeout=2)

        return server, client1, client2

    @mock.patch(target='pysoa.common.transport.redis_gateway.client.get_hex_thread_id')
    def test_without_thread_id(self, mock_get_hex_thread_id):
        mock_get_hex_thread_id.return_value = ''

        server, client1, client2 = self._test()

        if server.error:
            raise server.error

        self.assertIsNotNone(client1.error)
        self.assertTrue(
            client1.error.args[0].startswith('Expected payload to be'),
            'Expected error message to start with "Expected payload to be," but instead got "{}"'.format(
                client1.error.args[0],
            ),
        )

        self.assertIsNotNone(client2.error)
        self.assertTrue(
            client2.error.args[0].startswith('Expected payload to be'),
            'Expected error message to start with "Expected payload to be," but instead got "{}"'.format(
                client2.error.args[0],
            ),
        )

    def test_with_thread_id(self):
        server, client1, client2 = self._test()

        if server.error:
            raise server.error

        if client1.error:
            raise client1.error

        if client2.error:
            raise client2.error
