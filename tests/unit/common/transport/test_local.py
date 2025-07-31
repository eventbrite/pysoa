from __future__ import (
    absolute_import,
    unicode_literals,
)

import unittest

from pysoa.test.compatibility import mock
from pysoa.common.transport.base import noop_metrics

from pysoa.common.transport.local import (
    LocalClientTransport,
    LocalServerTransport,
)
from pysoa.server.server import Server
from pysoa.server.settings import ServerSettings


class MockServer(Server):
    service_name = 'test_service'
    
    def setup(self):
        pass
    
    def handle_next_request(self):
        pass


class TestLocalClientTransport(unittest.TestCase):
    def test_init_with_invalid_server_class_path(self):
        with mock.patch('pysoa.common.transport.local.fields.PythonPath.resolve_python_path') as mock_resolve:
            mock_resolve.side_effect = ImportError('No module named test')
            
            with self.assertRaises(ImportError):
                LocalClientTransport(
                    service_name='test_service',
                    metrics=noop_metrics,
                    server_class='invalid.path:MockServer',
                    server_settings={}
                )

    def test_init_with_non_server_class(self):
        with self.assertRaises(TypeError):
            LocalClientTransport(
                service_name='test_service',
                metrics=noop_metrics,
                server_class=str,  # Not a Server subclass
                server_settings={}
            )

    def test_init_with_mismatched_service_name(self):
        class WrongServer(Server):
            service_name = 'wrong_service'
            
            def setup(self):
                pass
            
            def handle_next_request(self):
                pass
        
        with self.assertRaises(Exception):
            LocalClientTransport(
                service_name='test_service',
                metrics=noop_metrics,
                server_class=WrongServer,
                server_settings={}
            )

    def test_init_with_invalid_settings_path(self):
        with mock.patch('pysoa.common.transport.local.fields.PythonPath.resolve_python_path') as mock_resolve:
            mock_resolve.side_effect = ImportError('No module named test')
            
            with self.assertRaises(ImportError):
                LocalClientTransport(
                    service_name='test_service',
                    metrics=noop_metrics,
                    server_class=MockServer,
                    server_settings='invalid.path:settings'
                )

    def test_init_with_non_dict_settings_path(self):
        with mock.patch('pysoa.common.transport.local.fields.PythonPath.resolve_python_path') as mock_resolve:
            mock_resolve.return_value = 'not_a_dict'
            
            with self.assertRaises(TypeError):
                LocalClientTransport(
                    service_name='test_service',
                    metrics=noop_metrics,
                    server_class=MockServer,
                    server_settings='tests.unit.common.transport.test_local:settings'
                )

    def test_init_with_non_dict_non_string_settings(self):
        with self.assertRaises(TypeError):
            LocalClientTransport(
                service_name='test_service',
                metrics=noop_metrics,
                server_class=MockServer,
                server_settings=123  # Not a dict or string
            )

    def test_send_request_message(self):
        transport = LocalClientTransport(
            service_name='test_service',
            metrics=noop_metrics,
            server_class=MockServer,
            server_settings={}
        )
        
        # Mock the server's handle_next_request method
        transport.server.handle_next_request = mock.MagicMock()
        
        transport.send_request_message(1, {'meta': 'data'}, {'body': 'data'})
        
        transport.server.handle_next_request.assert_called_once()
        self.assertIsNone(transport._current_request)

    def test_receive_request_message_success(self):
        transport = LocalClientTransport(
            service_name='test_service',
            metrics=noop_metrics,
            server_class=MockServer,
            server_settings={}
        )
        
        # Set up a current request
        mock_request = mock.MagicMock()
        transport._current_request = mock_request
        
        result = transport.receive_request_message()
        
        self.assertEqual(result, mock_request)
        self.assertIsNone(transport._current_request)

    def test_receive_request_message_no_current_request(self):
        transport = LocalClientTransport(
            service_name='test_service',
            metrics=noop_metrics,
            server_class=MockServer,
            server_settings={}
        )
        
        with self.assertRaises(RuntimeError):
            transport.receive_request_message()

    def test_send_response_message(self):
        transport = LocalClientTransport(
            service_name='test_service',
            metrics=noop_metrics,
            server_class=MockServer,
            server_settings={}
        )
        
        transport.send_response_message(1, {'meta': 'data'}, {'body': 'data'})
        
        self.assertEqual(len(transport.response_messages), 1)
        response = transport.response_messages[0]
        self.assertEqual(response.request_id, 1)
        self.assertEqual(response.meta, {'meta': 'data'})
        self.assertEqual(response.body, {'body': 'data'})

    def test_receive_response_message_with_response(self):
        transport = LocalClientTransport(
            service_name='test_service',
            metrics=noop_metrics,
            server_class=MockServer,
            server_settings={}
        )
        
        # Add a response to the queue
        mock_response = mock.MagicMock()
        transport.response_messages.append(mock_response)
        
        result = transport.receive_response_message()
        
        self.assertEqual(result, mock_response)
        self.assertEqual(len(transport.response_messages), 0)

    def test_receive_response_message_no_response(self):
        transport = LocalClientTransport(
            service_name='test_service',
            metrics=noop_metrics,
            server_class=MockServer,
            server_settings={}
        )
        
        result = transport.receive_response_message()
        
        self.assertIsNone(result.request_id)
        self.assertIsNone(result.meta)
        self.assertIsNone(result.body)


class TestLocalServerTransport(unittest.TestCase):
    def test_receive_request_message_raises_error(self):
        transport = LocalServerTransport('test_service')
        
        with self.assertRaises(TypeError):
            transport.receive_request_message()

    def test_send_response_message_raises_error(self):
        transport = LocalServerTransport('test_service')
        
        with self.assertRaises(TypeError):
            transport.send_response_message(1, {'meta': 'data'}, {'body': 'data'}) 