from __future__ import absolute_import, unicode_literals

import unittest
import uuid

import mock

from pysoa.common.metrics import NoOpMetricsRecorder
from pysoa.common.transport.exceptions import InvalidMessageError
from pysoa.common.transport.redis_gateway.server import RedisServerTransport


@mock.patch('pysoa.common.transport.redis_gateway.server.RedisTransportCore')
class TestServerTransport(unittest.TestCase):
    @staticmethod
    def _get_transport(service='my_service', **kwargs):
        return RedisServerTransport(service, NoOpMetricsRecorder(), **kwargs)

    def test_core_args(self, mock_core):
        transport = self._get_transport(hello='world', goodbye='earth')

        mock_core.assert_called_once_with(
            hello='world',
            goodbye='earth',
            metrics=transport.metrics,
            metrics_prefix='server',
        )

    def test_receive_request_message(self, mock_core):
        transport = self._get_transport()

        request_id = uuid.uuid4().hex
        meta = {'app': 'ppa'}
        message = {'test': 'payload'}

        mock_core.return_value.receive_message.return_value = request_id, meta, message

        self.assertEqual((request_id, meta, message), transport.receive_request_message())

        mock_core.return_value.receive_message.assert_called_once_with('service.my_service')

    def test_receive_request_message_another_service(self, mock_core):
        transport = self._get_transport('geo')

        request_id = uuid.uuid4().hex
        message = {'another': 'message'}

        mock_core.return_value.receive_message.return_value = request_id, {}, message

        self.assertEqual((request_id, {}, message), transport.receive_request_message())

        mock_core.return_value.receive_message.assert_called_once_with('service.geo')

    def test_send_response_message_no_reply_to(self, mock_core):
        transport = self._get_transport()

        request_id = uuid.uuid4().hex
        meta = {'app': 'ppa'}
        message = {'test': 'payload'}

        with self.assertRaises(InvalidMessageError):
            transport.send_response_message(request_id, meta, message)

        self.assertFalse(mock_core.return_value.send_message.called)

    def test_send_response_message(self, mock_core):
        transport = self._get_transport()

        request_id = uuid.uuid4().hex
        meta = {'app': 'ppa', 'reply_to': 'my_reply_to_queue'}
        message = {'test': 'payload'}

        transport.send_response_message(request_id, meta, message)

        mock_core.return_value.send_message.assert_called_once_with(
            'my_reply_to_queue',
            request_id,
            meta,
            message,
        )

    def test_send_response_message_another_service(self, mock_core):
        transport = self._get_transport()

        request_id = uuid.uuid4().hex
        meta = {'reply_to': 'service.tag.123498afe09b9128cd92348a8c7bde31!'}
        message = {'another': 'message'}

        transport.send_response_message(request_id, meta, message)

        mock_core.return_value.send_message.assert_called_once_with(
            'service.tag.123498afe09b9128cd92348a8c7bde31!',
            request_id,
            meta,
            message,
        )
