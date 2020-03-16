from __future__ import (
    absolute_import,
    unicode_literals,
)

from typing import (
    Any,
    Dict,
)
import unittest

import msgpack
import redis.sentinel
import six

from pysoa.common.transport.redis_gateway.backend.base import CannotGetConnectionError
from pysoa.common.transport.redis_gateway.backend.sentinel import SentinelRedisClient
from pysoa.test.compatibility import mock

# To ensure all the patching over there happens over here
from tests.unit.common.transport.redis_gateway.backend.test_standard import mockredis


class MockSentinelRedis(mockredis.MockRedis):
    MASTERS = {'service1': {}, 'service2': {}, 'service3': {}}  # type: Dict[six.text_type, Dict[Any, Any]]

    def __init__(self):
        super(MockSentinelRedis, self).__init__(strict=True, load_lua_dependencies=False)
        self.connection_pool = mock.MagicMock()
        self.connection_pool.get_master_address.return_value = ('192.0.2.13', '6379')  # used official "example" address

    def sentinel_masters(self):
        return self.MASTERS


class MockSentinel(object):
    MASTERS = {'service1': MockSentinelRedis(), 'service2': MockSentinelRedis(), 'service3': MockSentinelRedis()}

    def __init__(self, *_, **__):
        pass

    @property
    def sentinels(self):
        return self.MASTERS.values()

    def master_for(self, service):
        return self.MASTERS[service]


class TestSentinelRedisChannelClient(unittest.TestCase):
    @staticmethod
    def _set_up_client(**kwargs):
        return SentinelRedisClient(
            hosts=[('169.254.7.12', 26379), ('169.254.8.12', 26379), '169.254.9.12'],
            **kwargs
        )

    @mock.patch('redis.sentinel.Sentinel', new=MockSentinel)
    def test_invalid_hosts(self):
        with self.assertRaises(ValueError):
            SentinelRedisClient(hosts='redis://localhost:1234/0')  # type: ignore

        with self.assertRaises(ValueError):
            SentinelRedisClient(hosts=[1234])  # type: ignore

        with self.assertRaises(ValueError):
            SentinelRedisClient(hosts=[('host_name', 'not_an_int')])  # type: ignore

    @mock.patch('redis.sentinel.Sentinel', new=MockSentinel)
    def test_invalid_services(self):
        with self.assertRaises(ValueError):
            self._set_up_client(sentinel_services='service1')

        with self.assertRaises(ValueError):
            self._set_up_client(sentinel_services=[1234])

    @mock.patch('redis.sentinel.Sentinel')
    def test_master_not_found_no_retry(self, mock_sentinel):
        mock_sentinel.return_value.master_for.return_value = MockSentinelRedis()

        client = self._set_up_client(sentinel_services=['service1', 'service2', 'service3'])
        client.reset_clients()

        mock_sentinel.return_value.master_for.reset_mock()
        mock_sentinel.return_value.master_for.side_effect = redis.sentinel.MasterNotFoundError

        with self.assertRaises(CannotGetConnectionError):
            client.get_connection('test_master_not_found_no_retry')

        self.assertEqual(1, mock_sentinel.return_value.master_for.call_count)
        self.assertIn(mock_sentinel.return_value.master_for.call_args[0][0], {'service1', 'service2', 'service3'})

    @mock.patch('redis.sentinel.Sentinel')
    def test_master_not_found_max_retries(self, mock_sentinel):
        mock_sentinel.return_value.master_for.return_value = MockSentinelRedis()

        client = self._set_up_client(sentinel_failover_retries=2, sentinel_services=['service1', 'service2'])
        client.reset_clients()

        mock_sentinel.return_value.master_for.reset_mock()
        mock_sentinel.return_value.master_for.side_effect = redis.sentinel.MasterNotFoundError

        with self.assertRaises(CannotGetConnectionError):
            client.get_connection('test_master_not_found_max_retries')

        self.assertEqual(3, mock_sentinel.return_value.master_for.call_count)
        self.assertIn(
            mock_sentinel.return_value.master_for.call_args_list[0][0][0],
            {'service1', 'service2', 'service3'},
        )
        self.assertIn(
            mock_sentinel.return_value.master_for.call_args_list[1][0][0],
            {'service1', 'service2', 'service3'},
        )
        self.assertIn(
            mock_sentinel.return_value.master_for.call_args_list[2][0][0],
            {'service1', 'service2', 'service3'},
        )

    @mock.patch('redis.sentinel.Sentinel')
    def test_master_not_found_worked_after_retries(self, mock_sentinel):
        mock_sentinel.return_value.master_for.return_value = MockSentinelRedis()

        client = self._set_up_client(sentinel_failover_retries=2, sentinel_services=['service1', 'service2'])
        client.reset_clients()

        mock_sentinel.return_value.master_for.reset_mock()
        mock_sentinel.return_value.master_for.side_effect = (
            redis.sentinel.MasterNotFoundError,
            redis.sentinel.MasterNotFoundError,
            MockSentinelRedis(),
        )

        connection = client.get_connection('test_master_not_found_worked_after_retries')
        self.assertIsNotNone(connection)

        self.assertEqual(3, mock_sentinel.return_value.master_for.call_count)
        self.assertIn(
            mock_sentinel.return_value.master_for.call_args_list[0][0][0],
            {'service1', 'service2', 'service3'},
        )
        self.assertIn(
            mock_sentinel.return_value.master_for.call_args_list[1][0][0],
            {'service1', 'service2', 'service3'},
        )
        self.assertIn(
            mock_sentinel.return_value.master_for.call_args_list[2][0][0],
            {'service1', 'service2', 'service3'},
        )

    @mock.patch('redis.sentinel.Sentinel', new=MockSentinel)
    def test_simple_send_and_receive(self):
        client = self._set_up_client()

        payload = {'test': 'test_simple_send_receive'}

        client.send_message_to_queue(
            queue_key='test_simple_send_receive',
            message=msgpack.packb(payload, use_bin_type=True),
            expiry=10,
            capacity=10,
            connection=client.get_connection('test_simple_send_receive'),
        )

        message = None
        for i in range(3):
            # Message will be on random server
            message = message or client.get_connection('test_simple_send_receive').lpop('test_simple_send_receive')

        self.assertIsNotNone(message)
        self.assertEqual(payload, msgpack.unpackb(message, raw=False))

    @mock.patch('redis.sentinel.Sentinel', new=MockSentinel)
    def test_services_send_receive(self):
        client = self._set_up_client(sentinel_services=['service1', 'service2', 'service3'])

        payload = {'test': 'test_services_send_receive'}

        client.send_message_to_queue(
            queue_key='test_services_send_receive',
            message=msgpack.packb(payload, use_bin_type=True),
            expiry=10,
            capacity=10,
            connection=client.get_connection('test_services_send_receive'),
        )

        message = None
        for i in range(3):
            # Message will be on random server
            message = message or client.get_connection('test_services_send_receive').lpop('test_services_send_receive')

        self.assertIsNotNone(message)
        self.assertEqual(payload, msgpack.unpackb(message, raw=False))

    @mock.patch('redis.sentinel.Sentinel', new=MockSentinel)
    def test_no_hosts_send_receive(self):
        client = SentinelRedisClient()

        payload = {'test': 'test_no_hosts_send_receive'}

        client.send_message_to_queue(
            queue_key='test_no_hosts_send_receive',
            message=msgpack.packb(payload, use_bin_type=True),
            expiry=10,
            capacity=10,
            connection=client.get_connection('test_no_hosts_send_receive'),
        )

        message = None
        for i in range(3):
            # Message will be on random server
            message = message or client.get_connection('test_no_hosts_send_receive').lpop('test_no_hosts_send_receive')

        self.assertIsNotNone(message)
        self.assertEqual(payload, msgpack.unpackb(message, raw=False))

    @mock.patch('redis.sentinel.Sentinel', new=MockSentinel)
    def test_hashed_server_send_receive(self):
        client = self._set_up_client()

        payload1 = {'test': 'some value'}

        client.send_message_to_queue(
            queue_key='test_hashed_send_receive!',
            message=msgpack.packb(payload1, use_bin_type=True),
            expiry=10,
            capacity=10,
            connection=client.get_connection('test_hashed_send_receive!'),
        )

        message = client.get_connection('test_hashed_send_receive!').lpop('test_hashed_send_receive!')

        self.assertIsNotNone(message)
        self.assertEqual(payload1, msgpack.unpackb(message, raw=False))

        payload2 = {'for': 'another value'}

        client.send_message_to_queue(
            queue_key='test_hashed_send_receive!',
            message=msgpack.packb(payload2, use_bin_type=True),
            expiry=10,
            capacity=10,
            connection=client.get_connection('test_hashed_send_receive!'),
        )

        message = client.get_connection('test_hashed_send_receive!').lpop('test_hashed_send_receive!')

        self.assertIsNotNone(message)
        self.assertEqual(payload2, msgpack.unpackb(message, raw=False))

        payload3 = {'hashing': 'will this work'}

        client.send_message_to_queue(
            queue_key='test_hashed_send_receive!',
            message=msgpack.packb(payload3, use_bin_type=True),
            expiry=10,
            capacity=10,
            connection=client.get_connection('test_hashed_send_receive!'),
        )

        message = client.get_connection('test_hashed_send_receive!').lpop('test_hashed_send_receive!')

        self.assertIsNotNone(message)
        self.assertEqual(payload3, msgpack.unpackb(message, raw=False))
