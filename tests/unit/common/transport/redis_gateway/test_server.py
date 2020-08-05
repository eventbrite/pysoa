from __future__ import (
    absolute_import,
    unicode_literals,
)

import random
import unittest

from pymetrics.recorders.noop import noop_metrics

from pysoa.common.transport.errors import InvalidMessageError
from pysoa.common.transport.redis_gateway.server import RedisServerTransport
from pysoa.test.compatibility import mock


@mock.patch('pysoa.common.transport.redis_gateway.server.RedisTransportServerCore')
class TestServerTransport(unittest.TestCase):
    @staticmethod
    def _get_transport(service='my_service', **kwargs):
        return RedisServerTransport(service, noop_metrics, 1, **kwargs)

    def test_core_args(self, mock_core):
        transport = self._get_transport(hello='world', goodbye='earth')

        mock_core.assert_called_once_with(
            service_name='my_service',
            hello='world',
            goodbye='earth',
            metrics=transport.metrics,
        )

        mock_core.reset_mock()

        transport = self._get_transport(hello='world', goodbye='earth', maximum_message_size_in_bytes=79)

        mock_core.assert_called_once_with(
            service_name='my_service',
            hello='world',
            goodbye='earth',
            metrics=transport.metrics,
            maximum_message_size_in_bytes=79,
        )

    def test_receive_request_message(self, mock_core):
        transport = self._get_transport()

        request_id = random.randint(1, 1000)
        meta = {'app': 'ppa'}
        message = {'test': 'payload'}

        mock_core.return_value.receive_message.return_value = request_id, meta, message

        self.assertEqual((request_id, meta, message), transport.receive_request_message())

        mock_core.return_value.receive_message.assert_called_once_with('service.my_service')

    def test_receive_request_message_another_service(self, mock_core):
        transport = self._get_transport('geo')

        request_id = random.randint(1, 1000)
        message = {'another': 'message'}

        mock_core.return_value.receive_message.return_value = request_id, {}, message

        self.assertEqual((request_id, {}, message), transport.receive_request_message())

        mock_core.return_value.receive_message.assert_called_once_with('service.geo')

    def test_send_response_message_no_reply_to(self, mock_core):
        transport = self._get_transport()

        request_id = random.randint(1, 1000)
        meta = {'app': 'ppa'}
        message = {'test': 'payload'}

        with self.assertRaises(InvalidMessageError):
            transport.send_response_message(request_id, meta, message)

        self.assertFalse(mock_core.return_value.send_message.called)

    def test_send_response_message(self, mock_core):
        transport = self._get_transport()

        request_id = random.randint(1, 1000)
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

        request_id = random.randint(1, 1000)
        meta = {'reply_to': 'service.tag.123498afe09b9128cd92348a8c7bde31!'}
        message = {'another': 'message'}

        transport.send_response_message(request_id, meta, message)

        mock_core.return_value.send_message.assert_called_once_with(
            'service.tag.123498afe09b9128cd92348a8c7bde31!',
            request_id,
            meta,
            message,
        )
