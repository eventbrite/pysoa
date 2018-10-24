from __future__ import (
    absolute_import,
    unicode_literals,
)

import datetime
import time
import timeit
import unittest

import attr
import freezegun

from pysoa.common.serializer.json_serializer import JSONSerializer
from pysoa.common.serializer.msgpack_serializer import MsgpackSerializer
from pysoa.common.transport.exceptions import (
    InvalidMessageError,
    MessageReceiveError,
    MessageReceiveTimeout,
    MessageSendError,
    MessageTooLarge,
)
from pysoa.common.transport.redis_gateway.backend.base import CannotGetConnectionError
from pysoa.common.transport.redis_gateway.constants import (
    REDIS_BACKEND_TYPE_SENTINEL,
    REDIS_BACKEND_TYPE_STANDARD,
)
from pysoa.common.transport.redis_gateway.core import RedisTransportCore
from pysoa.test.compatibility import mock

# To ensure all the patching over there happens over here
from tests.common.transport.redis_gateway.backend.test_standard import mockredis


@attr.s
class MockSerializer(object):
    kwarg1 = attr.ib(default=None)
    kwarg2 = attr.ib(default=None)


@mock.patch('redis.Redis', new=mockredis.mock_redis_client)
class TestRedisTransportCore(unittest.TestCase):
    def setUp(self):
        RedisTransportCore._backend_layer_cache = {}

    def test_invalid_backend_type(self):
        with self.assertRaises(ValueError):
            RedisTransportCore(backend_type='hello')

    @mock.patch('pysoa.common.transport.redis_gateway.core.SentinelRedisClient')
    @mock.patch('pysoa.common.transport.redis_gateway.core.StandardRedisClient')
    def test_standard_client_created_with_defaults(self, mock_standard, mock_sentinel):
        core = RedisTransportCore(backend_type=REDIS_BACKEND_TYPE_STANDARD)
        core.backend_layer.anything()

        self.assertEqual(60, core.message_expiry_in_seconds)
        self.assertEqual(10000, core.queue_capacity)
        self.assertEqual(10, core.queue_full_retries)
        self.assertEqual(5, core.receive_timeout_in_seconds)
        self.assertIsInstance(core.default_serializer, MsgpackSerializer)

        mock_standard.assert_called_once_with()
        mock_standard.return_value.anything.assert_called_once_with()
        self.assertFalse(mock_sentinel.called)

    @mock.patch('pysoa.common.transport.redis_gateway.core.SentinelRedisClient')
    @mock.patch('pysoa.common.transport.redis_gateway.core.StandardRedisClient')
    def test_standard_client_created(self, mock_standard, mock_sentinel):
        core = RedisTransportCore(
            service_name='example',
            backend_type=REDIS_BACKEND_TYPE_STANDARD,
            backend_layer_kwargs={
                'hosts': [('localhost', 6379), 'far_away_host'],
                'redis_db': 2,
                'redis_port': 1098,
            },
            message_expiry_in_seconds=30,
            queue_capacity=100,
            queue_full_retries=7,
            receive_timeout_in_seconds=10,
            default_serializer_config={'object': MockSerializer, 'kwargs': {'kwarg1': 'hello'}},
        )
        core.backend_layer.anything()

        self.assertEqual('example', core.service_name)
        self.assertEqual(30, core.message_expiry_in_seconds)
        self.assertEqual(100, core.queue_capacity)
        self.assertEqual(7, core.queue_full_retries)
        self.assertEqual(10, core.receive_timeout_in_seconds)
        self.assertIsInstance(core.default_serializer, MockSerializer)
        self.assertEqual('hello', core.default_serializer.kwarg1)

        mock_standard.assert_called_once_with(
            hosts=[('localhost', 6379), ('far_away_host', 1098)],
            connection_kwargs={'db': 2},
        )
        mock_standard.return_value.anything.assert_called_once_with()
        self.assertFalse(mock_sentinel.called)

    @mock.patch('pysoa.common.transport.redis_gateway.core.SentinelRedisClient')
    @mock.patch('pysoa.common.transport.redis_gateway.core.StandardRedisClient')
    def test_sentinel_client_created(self, mock_standard, mock_sentinel):
        core = RedisTransportCore(
            backend_type=REDIS_BACKEND_TYPE_SENTINEL,
            backend_layer_kwargs={
                'connection_kwargs': {'hello': 'world'},
                'hosts': [('another_host', 6379)],
                'redis_db': 5,
                'redis_port': 1098,
                'sentinel_refresh_interval': 13,
                'sentinel_services': ['svc1', 'svc2', 'svc3'],
                'sentinel_failover_retries': 5,
            },
            message_expiry_in_seconds=45,
            queue_capacity=7500,
            queue_full_retries=4,
            receive_timeout_in_seconds=6,
            default_serializer_config={'object': MockSerializer, 'kwargs': {'kwarg2': 'goodbye'}},
        )
        core.backend_layer.anything()

        self.assertEqual(45, core.message_expiry_in_seconds)
        self.assertEqual(7500, core.queue_capacity)
        self.assertEqual(4, core.queue_full_retries)
        self.assertEqual(6, core.receive_timeout_in_seconds)
        self.assertIsInstance(core.default_serializer, MockSerializer)
        self.assertEqual('goodbye', core.default_serializer.kwarg2)

        mock_sentinel.assert_called_once_with(
            hosts=[('another_host', 6379)],
            connection_kwargs={'db': 5, 'hello': 'world'},
            sentinel_refresh_interval=13,
            sentinel_services=['svc1', 'svc2', 'svc3'],
            sentinel_failover_retries=5,
        )
        mock_sentinel.return_value.anything.assert_called_once_with()
        self.assertFalse(mock_standard.called)

    @mock.patch('pysoa.common.transport.redis_gateway.core.SentinelRedisClient')
    @mock.patch('pysoa.common.transport.redis_gateway.core.StandardRedisClient')
    def test_cannot_get_connection_error_on_send(self, mock_standard, mock_sentinel):
        core = RedisTransportCore(backend_type=REDIS_BACKEND_TYPE_STANDARD)

        mock_standard.return_value.get_connection.side_effect = CannotGetConnectionError('This is my error')

        with self.assertRaises(MessageSendError) as error_context:
            core.send_message('my_queue', 71, {}, {})

        self.assertEqual('Cannot get connection: This is my error', error_context.exception.args[0])

        self.assertFalse(mock_sentinel.called)
        mock_standard.return_value.get_connection.assert_called_once_with('pysoa:my_queue')

    @mock.patch('pysoa.common.transport.redis_gateway.core.SentinelRedisClient')
    @mock.patch('pysoa.common.transport.redis_gateway.core.StandardRedisClient')
    def test_cannot_get_connection_error_on_receive(self, mock_standard, mock_sentinel):
        core = RedisTransportCore(backend_type=REDIS_BACKEND_TYPE_STANDARD)

        mock_standard.return_value.get_connection.side_effect = CannotGetConnectionError('This is another error')

        with self.assertRaises(MessageReceiveError) as error_context:
            core.receive_message('your_queue')

        self.assertEqual('Cannot get connection: This is another error', error_context.exception.args[0])

        self.assertFalse(mock_sentinel.called)
        mock_standard.return_value.get_connection.assert_called_once_with('pysoa:your_queue')

    @staticmethod
    def _get_core(**kwargs):
        return RedisTransportCore(backend_type=REDIS_BACKEND_TYPE_STANDARD, **kwargs)

    def test_invalid_request_id(self):
        core = self._get_core()

        with self.assertRaises(InvalidMessageError):
            # noinspection PyTypeChecker
            core.send_message('test_invalid_request_id', None, {}, {'test': 'payload'})

    def test_message_too_large(self):
        core = self._get_core()

        message = {'test': ['payload%i' % i for i in range(1000, 9530)]}  # This creates a message > 102,400 bytes

        with self.assertRaises(MessageTooLarge):
            core.send_message('test_message_too_large', 0, {}, message)

    def test_message_too_large_configurable(self):
        core = self._get_core(maximum_message_size_in_bytes=150)

        message = {'test': ['payload%i' % i for i in range(100, 110)]}  # This creates a message > 150 bytes

        with self.assertRaises(MessageTooLarge):
            core.send_message('test_message_too_large', 1, {}, message)

    def test_oversized_message_is_logged(self):
        core = self._get_core(log_messages_larger_than_bytes=150)

        message = {'test': ['payload%i' % i for i in range(100, 110)]}  # This creates a message > 150 bytes

        core.send_message('test_message_too_large', 1, {}, message)

    def test_simple_send_and_receive_default_expiry(self):
        core = self._get_core()

        request_id = 27
        meta = {'app': 52}
        message = {'test': 'payload'}

        t = time.time()
        core.send_message('test_simple_send_and_receive', request_id, meta, message)

        response = core.receive_message('test_simple_send_and_receive')

        self.assertEqual(request_id, response[0])
        self.assertEqual(meta, response[1])
        self.assertEqual(message, response[2])

        self.assertTrue((t + 59.9) < meta['__expiry__'] < (t + 61.1))

    def test_simple_send_and_receive_expiry_override(self):
        core = self._get_core()

        request_id = 31
        meta = {'app': 52}
        message = {'test': 'payload'}

        t = time.time()
        core.send_message('test_simple_send_and_receive', request_id, meta, message, message_expiry_in_seconds=10)

        response = core.receive_message('test_simple_send_and_receive')

        self.assertEqual(request_id, response[0])
        self.assertEqual(meta, response[1])
        self.assertEqual(message, response[2])

        self.assertTrue((t + 9.9) < meta['__expiry__'] < (t + 10.1))

    def test_send_queue_full(self):
        core = self._get_core(queue_full_retries=1, queue_capacity=3)

        request_id1 = 32
        request_id2 = 33
        request_id3 = 34
        request_id4 = 35
        request_id5 = 36

        core.send_message('test_send_queue_full', request_id1, {}, {'test': 'payload1'})
        core.send_message('test_send_queue_full', request_id2, {}, {'test': 'payload2'})
        core.send_message('test_send_queue_full', request_id3, {}, {'test': 'payload3'})

        with self.assertRaises(MessageSendError) as error_context:
            core.send_message('test_send_queue_full', request_id4, {}, {'test': 'payload4'})

        self.assertTrue('test_send_queue_full was full' in error_context.exception.args[0])

        response = core.receive_message('test_send_queue_full')
        self.assertEqual(request_id1, response[0])
        self.assertEqual('payload1', response[2]['test'])

        core.send_message('test_send_queue_full', request_id4, {}, {'test': 'payload4'})

        with self.assertRaises(MessageSendError) as error_context:
            core.send_message('test_send_queue_full', request_id5, {}, {'test': 'payload5'})

        self.assertTrue('test_send_queue_full was full' in error_context.exception.args[0])

        response = core.receive_message('test_send_queue_full')
        self.assertEqual(request_id2, response[0])
        self.assertEqual('payload2', response[2]['test'])

        core.send_message('test_send_queue_full', request_id5, {}, {'test': 'payload5'})

        response = core.receive_message('test_send_queue_full')
        self.assertEqual(request_id3, response[0])
        self.assertEqual('payload3', response[2]['test'])

        response = core.receive_message('test_send_queue_full')
        self.assertEqual(request_id4, response[0])
        self.assertEqual('payload4', response[2]['test'])

        response = core.receive_message('test_send_queue_full')
        self.assertEqual(request_id5, response[0])
        self.assertEqual('payload5', response[2]['test'])

    def test_receive_timeout_default(self):
        core = self._get_core(receive_timeout_in_seconds=1)

        start = timeit.default_timer()
        with self.assertRaises(MessageReceiveTimeout) as error_context:
            core.receive_message('test_receive_timeout')
        elapsed = timeit.default_timer() - start

        self.assertTrue('received' in error_context.exception.args[0])
        self.assertTrue(0.9 < elapsed < 1.1)

    def test_receive_timeout_override(self):
        core = self._get_core()

        start = timeit.default_timer()
        with self.assertRaises(MessageReceiveTimeout) as error_context:
            core.receive_message('test_receive_timeout', receive_timeout_in_seconds=1)
        elapsed = timeit.default_timer() - start

        self.assertTrue('received' in error_context.exception.args[0])
        self.assertTrue(0.9 < elapsed < 1.1)

    def test_expired_message(self):
        core = self._get_core(receive_timeout_in_seconds=3, message_expiry_in_seconds=10)

        with freezegun.freeze_time(ignore=['mockredis.client', 'mockredis.clock', 'timeit']) as frozen_time:
            core.send_message('test_expired_message', 42, {}, {'test': 'payload'})

            frozen_time.tick(datetime.timedelta(seconds=11))

            start = timeit.default_timer()
            with self.assertRaises(MessageReceiveTimeout) as error_context:
                core.receive_message('test_expired_message')
            elapsed = timeit.default_timer() - start

            self.assertTrue(0 < elapsed < 0.1)  # This shouldn't actually take 3 seconds, it should be instant
            self.assertTrue('expired' in error_context.exception.args[0])

            frozen_time.tick(datetime.timedelta(seconds=1))

            request_id = 19
            core.send_message('test_expired_message', request_id, {}, {'test': 'payload'})

            frozen_time.tick(datetime.timedelta(seconds=10))

            start = timeit.default_timer()
            response = core.receive_message('test_expired_message')
            elapsed = timeit.default_timer() - start

            self.assertTrue(0 < elapsed < 0.1)
            self.assertEqual(request_id, response[0])

    @mock.patch('pysoa.common.transport.redis_gateway.core.StandardRedisClient')
    def test_content_type_default(self, mock_standard):
        core = self._get_core(receive_timeout_in_seconds=3, message_expiry_in_seconds=10)

        mock_standard.return_value.get_connection.return_value.blpop.return_value = [
            True,
            MsgpackSerializer().dict_to_blob({'request_id': 15, 'meta': {}, 'body': {'foo': 'bar'}}),
        ]

        request_id, meta, body = core.receive_message('test_content_type_default')

        self.assertEqual(15, request_id)
        self.assertEqual({}, meta)
        self.assertEqual({'foo': 'bar'}, body)

        mock_standard.return_value.get_connection.return_value.blpop.assert_called_once_with(
            ['pysoa:test_content_type_default'],
            timeout=core.receive_timeout_in_seconds,
        )

        core.send_message('test_content_type_default:reply', 15, meta, {'yep': 'nope'})

        call_kwargs = mock_standard.return_value.send_message_to_queue.call_args_list[0][1]

        self.assertEqual('pysoa:test_content_type_default:reply', call_kwargs['queue_key'])
        self.assertEqual(core.message_expiry_in_seconds, call_kwargs['expiry'])
        self.assertEqual(core.queue_capacity, call_kwargs['capacity'])
        self.assertEqual(mock_standard.return_value.get_connection.return_value, call_kwargs['connection'])

        message = MsgpackSerializer().blob_to_dict(call_kwargs['message'])
        self.assertEqual(15, message['request_id'])
        self.assertTrue(message['meta']['__expiry__'] <= time.time() + core.message_expiry_in_seconds)
        self.assertTrue({'yep': 'nope'}, message['body'])

    @mock.patch('pysoa.common.transport.redis_gateway.core.StandardRedisClient')
    def test_content_type_explicit_msgpack(self, mock_standard):
        core = self._get_core(receive_timeout_in_seconds=3, message_expiry_in_seconds=10)

        mock_standard.return_value.get_connection.return_value.blpop.return_value = [
            True,
            (
                b'content-type:application/msgpack;' +
                MsgpackSerializer().dict_to_blob({'request_id': 15, 'meta': {}, 'body': {'foo': 'bar'}})
            ),
        ]

        request_id, meta, body = core.receive_message('test_content_type_default')

        self.assertEqual(15, request_id)
        self.assertIn('serializer', meta)
        self.assertEqual(1, len(meta))
        self.assertIsInstance(meta['serializer'], MsgpackSerializer)
        self.assertEqual({'foo': 'bar'}, body)

        mock_standard.return_value.get_connection.return_value.blpop.assert_called_once_with(
            ['pysoa:test_content_type_default'],
            timeout=core.receive_timeout_in_seconds,
        )

        core.send_message('test_content_type_default:reply', 15, meta, {'yep': 'nope'})

        call_kwargs = mock_standard.return_value.send_message_to_queue.call_args_list[0][1]

        self.assertEqual('pysoa:test_content_type_default:reply', call_kwargs['queue_key'])
        self.assertEqual(core.message_expiry_in_seconds, call_kwargs['expiry'])
        self.assertEqual(core.queue_capacity, call_kwargs['capacity'])
        self.assertEqual(mock_standard.return_value.get_connection.return_value, call_kwargs['connection'])

        self.assertTrue(call_kwargs['message'].startswith(b'content-type:application/msgpack;'))

        message = MsgpackSerializer().blob_to_dict(call_kwargs['message'][len(b'content-type:application/msgpack;'):])
        self.assertEqual(15, message['request_id'])
        self.assertTrue(message['meta']['__expiry__'] <= time.time() + core.message_expiry_in_seconds)
        self.assertTrue({'yep': 'nope'}, message['body'])

    @mock.patch('pysoa.common.transport.redis_gateway.core.StandardRedisClient')
    def test_content_type_explicit_json(self, mock_standard):
        core = self._get_core(receive_timeout_in_seconds=3, message_expiry_in_seconds=10)

        mock_standard.return_value.get_connection.return_value.blpop.return_value = [
            True,
            (
                b'content-type : application/json ;' +
                JSONSerializer().dict_to_blob({'request_id': 15, 'meta': {}, 'body': {'foo': 'bar'}})
            ),
        ]

        request_id, meta, body = core.receive_message('test_content_type_default')

        self.assertEqual(15, request_id)
        self.assertIn('serializer', meta)
        self.assertEqual(1, len(meta))
        self.assertIsInstance(meta['serializer'], JSONSerializer)
        self.assertEqual({'foo': 'bar'}, body)

        mock_standard.return_value.get_connection.return_value.blpop.assert_called_once_with(
            ['pysoa:test_content_type_default'],
            timeout=core.receive_timeout_in_seconds,
        )

        core.send_message('test_content_type_default:reply', 15, meta, {'yep': 'nope'})

        call_kwargs = mock_standard.return_value.send_message_to_queue.call_args_list[0][1]

        self.assertEqual('pysoa:test_content_type_default:reply', call_kwargs['queue_key'])
        self.assertEqual(core.message_expiry_in_seconds, call_kwargs['expiry'])
        self.assertEqual(core.queue_capacity, call_kwargs['capacity'])
        self.assertEqual(mock_standard.return_value.get_connection.return_value, call_kwargs['connection'])

        self.assertTrue(call_kwargs['message'].startswith(b'content-type:application/json;'))

        message = JSONSerializer().blob_to_dict(call_kwargs['message'][len(b'content-type:application/json;'):])
        self.assertEqual(15, message['request_id'])
        self.assertTrue(message['meta']['__expiry__'] <= time.time() + core.message_expiry_in_seconds)
        self.assertTrue({'yep': 'nope'}, message['body'])
