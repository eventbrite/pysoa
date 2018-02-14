from __future__ import absolute_import, unicode_literals

import mock
import threading
import unittest

from pysoa.server.logging import PySOALogContextFilter


class TestPySOALogContextFilter(unittest.TestCase):
    def test_threading(self):
        thread_data = {}

        def fn(*_, **__):
            thread_data['first_get'] = PySOALogContextFilter.get_logging_request_context()

            PySOALogContextFilter.set_logging_request_context(foo='bar', **{'baz': 'qux'})

            thread_data['second_get'] = PySOALogContextFilter.get_logging_request_context()

            if thread_data.get('do_clear'):
                PySOALogContextFilter.clear_logging_request_context()

            thread_data['third_get'] = PySOALogContextFilter.get_logging_request_context()

        self.assertIsNone(PySOALogContextFilter.get_logging_request_context())

        PySOALogContextFilter.set_logging_request_context(request_id=1234, **{'correlation_id': 'abc'})

        self.assertEqual(
            {'request_id': 1234, 'correlation_id': 'abc'},
            PySOALogContextFilter.get_logging_request_context()
        )

        thread = threading.Thread(target=fn)
        thread.start()
        thread.join()

        self.assertEqual(
            {'request_id': 1234, 'correlation_id': 'abc'},
            PySOALogContextFilter.get_logging_request_context()
        )

        self.assertIsNone(thread_data['first_get'])
        self.assertEqual({'foo': 'bar', 'baz': 'qux'}, thread_data['second_get'])
        self.assertEqual({'foo': 'bar', 'baz': 'qux'}, thread_data['third_get'])

        thread_data['do_clear'] = True

        thread = threading.Thread(target=fn)
        thread.start()
        thread.join()

        self.assertEqual(
            {'request_id': 1234, 'correlation_id': 'abc'},
            PySOALogContextFilter.get_logging_request_context()
        )

        self.assertIsNone(thread_data['first_get'])
        self.assertEqual({'foo': 'bar', 'baz': 'qux'}, thread_data['second_get'])
        self.assertIsNone(thread_data['third_get'])

    def test_filter(self):
        record = mock.MagicMock()

        log_filter = PySOALogContextFilter()

        self.assertTrue(log_filter.filter(record))
        self.assertEqual('', record.correlation_id)
        self.assertEqual('', record.request_id)

        PySOALogContextFilter.set_logging_request_context(foo='bar', **{'baz': 'qux'})

        record.reset_mock()

        self.assertTrue(log_filter.filter(record))
        self.assertEqual('', record.correlation_id)
        self.assertEqual('', record.request_id)

        PySOALogContextFilter.set_logging_request_context(request_id=4321, **{'correlation_id': 'abc1234'})

        record.reset_mock()

        self.assertTrue(log_filter.filter(record))
        self.assertEqual('abc1234', record.correlation_id)
        self.assertEqual(4321, record.request_id)

        PySOALogContextFilter.clear_logging_request_context()

        record.reset_mock()

        self.assertTrue(log_filter.filter(record))
        self.assertEqual('', record.correlation_id)
        self.assertEqual('', record.request_id)
