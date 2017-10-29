from __future__ import absolute_import, unicode_literals

import unittest
import uuid

import mock

from pysoa.common.transport.redis_gateway.client import RedisClientTransport


@mock.patch('pysoa.common.transport.redis_gateway.client.RedisTransportCore')
class TestClientTransport(unittest.TestCase):
    @staticmethod
    def _get_transport(service='my_service', **kwargs):
        return RedisClientTransport(service, **kwargs)

    def test_core_args(self, mock_core):
        transport = self._get_transport(hello='world', goodbye='earth')

        mock_core.assert_called_once_with(hello='world', goodbye='earth')

        self.assertRegexpMatches(transport.client_id, r'^[0-9a-fA-F]{32}$')

    def test_send_request_message(self, mock_core):
        transport = self._get_transport()

        request_id = uuid.uuid4().hex
        meta = {'app': 'ppa'}
        message = {'test': 'payload'}

        transport.send_request_message(request_id, meta, message)

        mock_core.return_value.send_message.assert_called_once_with(
            'service.my_service',
            request_id,
            {'app': 'ppa', 'reply_to': 'service.my_service.{client_id}!'.format(client_id=transport.client_id)},
            message
        )

    def test_send_request_message_another_service(self, mock_core):
        transport = self._get_transport('geo')

        request_id = uuid.uuid4().hex
        message = {'another': 'message'}

        transport.send_request_message(request_id, {}, message)

        mock_core.return_value.send_message.assert_called_once_with(
            'service.geo',
            request_id,
            {'reply_to': 'service.geo.{client_id}!'.format(client_id=transport.client_id)},
            message
        )

    def test_receive_response_message(self, mock_core):
        transport = self._get_transport()
        transport._requests_outstanding = 1

        request_id = uuid.uuid4().hex
        meta = {'app': 'ppa'}
        message = {'test': 'payload'}

        mock_core.return_value.receive_message.return_value = request_id, meta, message

        response = transport.receive_response_message()

        self.assertEqual(request_id, response[0])
        self.assertEqual(meta, response[1])
        self.assertEqual(message, response[2])

        mock_core.return_value.receive_message.assert_called_once_with(
            'service.my_service.{client_id}!'.format(client_id=transport.client_id),
        )

    def test_receive_response_message_another_service(self, mock_core):
        transport = self._get_transport('geo')
        transport._requests_outstanding = 1

        request_id = uuid.uuid4().hex
        meta = {}
        message = {'another': 'message'}

        mock_core.return_value.receive_message.return_value = request_id, meta, message

        response = transport.receive_response_message()

        self.assertEqual(request_id, response[0])
        self.assertEqual(meta, response[1])
        self.assertEqual(message, response[2])

        mock_core.return_value.receive_message.assert_called_once_with(
            'service.geo.{client_id}!'.format(client_id=transport.client_id),
        )

    def test_requests_outstanding(self, mock_core):
        transport = self._get_transport('geo')
        self.assertEqual(0, transport.requests_outstanding)

        transport.send_request_message(uuid.uuid4().hex, {}, {})
        self.assertEqual(1, transport.requests_outstanding)

        transport.send_request_message(uuid.uuid4().hex, {}, {})
        self.assertEqual(2, transport.requests_outstanding)

        request_id = uuid.uuid4().hex
        mock_core.return_value.receive_message.return_value = request_id, {}, {}

        self.assertEqual((request_id, {}, {}), transport.receive_response_message())
        self.assertEqual(1, transport.requests_outstanding)

        self.assertEqual((request_id, {}, {}), transport.receive_response_message())
        self.assertEqual(0, transport.requests_outstanding)

        self.assertEqual((None, None, None), transport.receive_response_message())
