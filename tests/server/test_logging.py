from __future__ import absolute_import, unicode_literals

import mock
import six
import threading
import unittest

from pysoa.server.logging import (
    PySOALogContextFilter,
    RecursivelyCensoredDictWrapper,
)


class TestPySOALogContextFilter(unittest.TestCase):
    def tearDown(self):
        # Make sure that if anything goes wrong with these tests, that it doesn't affect any other tests
        PySOALogContextFilter.clear_logging_request_context()
        PySOALogContextFilter.clear_logging_request_context()
        PySOALogContextFilter.clear_logging_request_context()
        PySOALogContextFilter.clear_logging_request_context()
        PySOALogContextFilter.clear_logging_request_context()
        PySOALogContextFilter.clear_logging_request_context()
        PySOALogContextFilter.clear_logging_request_context()

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

        PySOALogContextFilter.set_logging_request_context(filter='mine', **{'logger': 'yours'})
        self.assertEqual({'filter': 'mine', 'logger': 'yours'}, PySOALogContextFilter.get_logging_request_context())

        record.reset_mock()

        self.assertTrue(log_filter.filter(record))
        self.assertEqual('', record.correlation_id)
        self.assertEqual('', record.request_id)

        PySOALogContextFilter.set_logging_request_context(request_id=4321, **{'correlation_id': 'abc1234'})
        self.assertEqual(
            {'request_id': 4321, 'correlation_id': 'abc1234'},
            PySOALogContextFilter.get_logging_request_context()
        )

        record.reset_mock()

        self.assertTrue(log_filter.filter(record))
        self.assertEqual('abc1234', record.correlation_id)
        self.assertEqual(4321, record.request_id)

        PySOALogContextFilter.clear_logging_request_context()
        self.assertEqual({'filter': 'mine', 'logger': 'yours'}, PySOALogContextFilter.get_logging_request_context())

        record.reset_mock()

        self.assertTrue(log_filter.filter(record))
        self.assertEqual('', record.correlation_id)
        self.assertEqual('', record.request_id)

        PySOALogContextFilter.clear_logging_request_context()
        self.assertIsNone(PySOALogContextFilter.get_logging_request_context())

        record.reset_mock()

        self.assertTrue(log_filter.filter(record))
        self.assertEqual('', record.correlation_id)
        self.assertEqual('', record.request_id)


class TestRecursivelyCensoredDictWrapper(unittest.TestCase):
    def test_non_dict(self):
        with self.assertRaises(ValueError):
            # noinspection PyTypeChecker
            RecursivelyCensoredDictWrapper(['this', 'is', 'a', 'list'])

    def test_simple_dict(self):
        original = {
            'hello': 'world',
            'password': 'censor!',
            'credit_card': '1234567890123456',
            'passphrase': True,
            'cvv': 938,
        }

        wrapped = RecursivelyCensoredDictWrapper(original)

        expected = {
            'hello': 'world',
            'password': '**********',
            'credit_card': '**********',
            'passphrase': True,
            'cvv': '**********',
        }

        self.assertEqual(expected, eval(repr(wrapped)))
        self.assertEqual(repr(wrapped), str(wrapped))
        if six.PY2:
            self.assertEqual(six.text_type(repr(wrapped)), six.text_type(wrapped))
        else:
            self.assertEqual(six.binary_type(repr(wrapped), 'utf-8'), six.binary_type(wrapped))

        # Make sure the original dict wasn't modified
        self.assertEqual(
            {
                'hello': 'world',
                'password': 'censor!',
                'credit_card': '1234567890123456',
                'passphrase': True,
                'cvv': 938,
            },
            original,
        )

    def test_complex_dict(self):
        original = {
            'a_list': [
                'a',
                True,
                109.8277,
                {'username': 'nick', 'passphrase': 'this should be censored'},
                {'username': 'allison', 'passphrase': ''},
            ],
            'a_set': {
                'b',
                False,
                18273,
            },
            'a_tuple': (
                'c',
                True,
                42,
                {'cc_number': '9876543210987654', 'cvv': '987', 'expiration': '12-20', 'pin': '4096'},
            ),
            'passwords': ['Make It Censored', None, '', 'Hello, World!'],
            'credit_card_numbers': ('1234', '5678', '9012'),
            'cvv2': {'a', None, '', 'b'},
            'pin': frozenset({'c', 'd', ''}),
            'foo': 'bar',
            'passphrases': {
                'not_sensitive': 'not censored',
                'bankAccount': 'this should also be censored',
            }
        }

        wrapped = RecursivelyCensoredDictWrapper(original)

        expected = {
            'a_list': [
                'a',
                True,
                109.8277,
                {'username': 'nick', 'passphrase': '**********'},
                {'username': 'allison', 'passphrase': ''},
            ],
            'a_set': {
                'b',
                False,
                18273,
            },
            'a_tuple': (
                'c',
                True,
                42,
                {'cc_number': '**********', 'cvv': '**********', 'expiration': '12-20', 'pin': '**********'},
            ),
            'passwords': ['**********', None, '', '**********'],
            'credit_card_numbers': ('**********', '**********', '**********'),
            'cvv2': {'**********', None, '', '**********'},
            'pin': frozenset({'**********', '**********', ''}),
            'foo': 'bar',
            'passphrases': {
                'not_sensitive': 'not censored',
                'bankAccount': '**********',
            }
        }

        self.assertEqual(expected, eval(repr(wrapped)))
        self.assertEqual(repr(wrapped), str(wrapped))
        if six.PY2:
            self.assertEqual(six.text_type(repr(wrapped)), six.text_type(wrapped))
        else:
            self.assertEqual(six.binary_type(repr(wrapped), 'utf-8'), six.binary_type(wrapped))

        self.assertEqual(
            {
                'a_list': [
                    'a',
                    True,
                    109.8277,
                    {'username': 'nick', 'passphrase': 'this should be censored'},
                    {'username': 'allison', 'passphrase': ''},
                ],
                'a_set': {
                    'b',
                    False,
                    18273,
                },
                'a_tuple': (
                    'c',
                    True,
                    42,
                    {'cc_number': '9876543210987654', 'cvv': '987', 'expiration': '12-20', 'pin': '4096'},
                ),
                'passwords': ['Make It Censored', None, '', 'Hello, World!'],
                'credit_card_numbers': ('1234', '5678', '9012'),
                'cvv2': {'a', None, '', 'b'},
                'pin': frozenset({'c', 'd', ''}),
                'foo': 'bar',
                'passphrases': {
                    'not_sensitive': 'not censored',
                    'bankAccount': 'this should also be censored',
                }
            },
            original,
        )
