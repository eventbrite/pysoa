from __future__ import (
    absolute_import,
    unicode_literals,
)

import random
import re
from typing import (
    Any,
    Dict,
)
import unittest

from pymetrics.recorders.noop import noop_metrics
import six

from pysoa.common.transport.base import get_hex_thread_id
from pysoa.common.transport.redis_gateway.client import RedisClientTransport
from pysoa.test.compatibility import mock


@mock.patch('pysoa.common.transport.redis_gateway.client.RedisTransportClientCore')
class TestClientTransport(unittest.TestCase):
    @staticmethod
    def _get_transport(service='my_service', **kwargs):
        return RedisClientTransport(service, noop_metrics, **kwargs)

    # noinspection PyCompatibility
    def test_core_args(self, mock_core):
        transport = self._get_transport(hello='world', goodbye='earth')

        mock_core.assert_called_once_with(
            service_name='my_service',
            hello='world',
            goodbye='earth',
            metrics=transport.metrics,
        )

        assert re.compile(r'^[0-9a-fA-F]{32}$').match(transport.client_id), transport.client_id

        mock_core.reset_mock()

        transport = self._get_transport(hello='world', goodbye='earth', maximum_message_size_in_bytes=42)

        mock_core.assert_called_once_with(
            service_name='my_service',
            hello='world',
            goodbye='earth',
            metrics=transport.metrics,
            maximum_message_size_in_bytes=42,
        )

        assert re.compile(r'^[0-9a-fA-F]{32}$').match(transport.client_id), transport.client_id

    def test_send_request_message(self, mock_core):
        transport = self._get_transport()

        request_id = random.randint(1, 1000)
        meta = {'app': 'ppa'}
        message = {'test': 'payload'}

        transport.send_request_message(request_id, meta, message)

        mock_core.return_value.send_message.assert_called_once_with(
            'service.my_service',
            request_id,
            {
                'app': 'ppa',
                'reply_to': 'service.my_service.{client_id}!{thread_id}'.format(
                    client_id=transport.client_id,
                    thread_id=get_hex_thread_id(),
                ),
            },
            message,
            None,
        )

    def test_send_request_message_another_service(self, mock_core):
        transport = self._get_transport('geo')

        request_id = random.randint(1, 1000)
        message = {'another': 'message'}

        transport.send_request_message(request_id, {}, message, 25)

        mock_core.return_value.send_message.assert_called_once_with(
            'service.geo',
            request_id,
            {
                'reply_to': 'service.geo.{client_id}!{thread_id}'.format(
                    client_id=transport.client_id,
                    thread_id=get_hex_thread_id(),
                ),
            },
            message,
            25,
        )

    def test_receive_response_message(self, mock_core):
        transport = self._get_transport()
        transport._requests_outstanding = 1

        request_id = random.randint(1, 1000)
        meta = {'app': 'ppa'}
        message = {'test': 'payload'}

        mock_core.return_value.receive_message.return_value = request_id, meta, message

        response = transport.receive_response_message()

        self.assertEqual(request_id, response[0])
        self.assertEqual(meta, response[1])
        self.assertEqual(message, response[2])

        mock_core.return_value.receive_message.assert_called_once_with(
            'service.my_service.{client_id}!{thread_id}'.format(
                client_id=transport.client_id,
                thread_id=get_hex_thread_id(),
            ),
            None,
        )

    def test_receive_response_message_another_service(self, mock_core):
        transport = self._get_transport('geo')
        transport._requests_outstanding = 1

        request_id = random.randint(1, 1000)
        meta = {}  # type: Dict[six.text_type, Any]
        message = {'another': 'message'}

        mock_core.return_value.receive_message.return_value = request_id, meta, message

        response = transport.receive_response_message(15)

        self.assertEqual(request_id, response[0])
        self.assertEqual(meta, response[1])
        self.assertEqual(message, response[2])

        mock_core.return_value.receive_message.assert_called_once_with(
            'service.geo.{client_id}!{thread_id}'.format(
                client_id=transport.client_id,
                thread_id=get_hex_thread_id(),
            ),
            15,
        )

    def test_requests_outstanding(self, mock_core):
        transport = self._get_transport('geo')
        self.assertEqual(0, transport.requests_outstanding)

        transport.send_request_message(random.randint(1, 1000), {}, {})
        self.assertEqual(1, transport.requests_outstanding)

        transport.send_request_message(random.randint(1, 1000), {}, {})
        self.assertEqual(2, transport.requests_outstanding)

        request_id = random.randint(1, 1000)
        mock_core.return_value.receive_message.return_value = request_id, {}, {}

        self.assertEqual((request_id, {}, {}), transport.receive_response_message())
        self.assertEqual(1, transport.requests_outstanding)

        self.assertEqual((request_id, {}, {}), transport.receive_response_message())
        self.assertEqual(0, transport.requests_outstanding)

        self.assertEqual((None, None, None), transport.receive_response_message())
