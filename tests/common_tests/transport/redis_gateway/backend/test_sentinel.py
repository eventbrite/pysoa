from __future__ import absolute_import, unicode_literals

import unittest

import mock
import msgpack

from pysoa.common.transport.redis_gateway.backend.sentinel import SentinelRedisClient

from .test_standard import mockredis  # To ensure all the patching over there happens over here


class MockSentinelRedis(mockredis.MockRedis):
    MASTERS = {'service1': {}, 'service2': {}, 'service3': {}}

    def __init__(self):
        super(MockSentinelRedis, self).__init__(strict=True, load_lua_dependencies=False)

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


@mock.patch('redis.sentinel.Sentinel', new=MockSentinel)
class TestSentinelRedisChannelClient(unittest.TestCase):
    @staticmethod
    def _set_up_client(**kwargs):
        return SentinelRedisClient(
            hosts=[('169.254.7.12', 26379), ('169.254.8.12', 26379), ('169.254.9.12', 26379)],
            **kwargs
        )

    def test_invalid_hosts(self):
        with self.assertRaises(ValueError):
            SentinelRedisClient(hosts='redis://localhost:1234/0')

        with self.assertRaises(ValueError):
            SentinelRedisClient(hosts=['redis://localhost:1234/0'])

    def test_invalid_services(self):
        with self.assertRaises(ValueError):
            self._set_up_client(sentinel_services='service1')

        with self.assertRaises(ValueError):
            self._set_up_client(sentinel_services=[1234])

    def test_simple_send_and_receive(self):
        client = self._set_up_client()

        payload = {'test': 'test_simple_send_receive'}

        client.send_message_to_queue(
            queue_key='test_simple_send_receive',
            message=msgpack.packb(payload),
            expiry=10,
            capacity=10,
            connection=client.get_connection('test_simple_send_receive'),
        )

        message = None
        for i in range(3):
            # Message will be on random server
            message = message or client.get_connection('test_simple_send_receive').lpop('test_simple_send_receive')

        self.assertIsNotNone(message)
        self.assertEqual(payload, msgpack.unpackb(message, encoding='utf-8'))

    def test_services_send_receive(self):
        client = self._set_up_client(sentinel_services=['service1', 'service2', 'service3'])

        payload = {'test': 'test_services_send_receive'}

        client.send_message_to_queue(
            queue_key='test_services_send_receive',
            message=msgpack.packb(payload),
            expiry=10,
            capacity=10,
            connection=client.get_connection('test_services_send_receive'),
        )

        message = None
        for i in range(3):
            # Message will be on random server
            message = message or client.get_connection('test_services_send_receive').lpop('test_services_send_receive')

        self.assertIsNotNone(message)
        self.assertEqual(payload, msgpack.unpackb(message, encoding='utf-8'))

    def test_no_hosts_send_receive(self):
        client = SentinelRedisClient()

        payload = {'test': 'test_no_hosts_send_receive'}

        client.send_message_to_queue(
            queue_key='test_no_hosts_send_receive',
            message=msgpack.packb(payload),
            expiry=10,
            capacity=10,
            connection=client.get_connection('test_no_hosts_send_receive'),
        )

        message = None
        for i in range(3):
            # Message will be on random server
            message = message or client.get_connection('test_no_hosts_send_receive').lpop('test_no_hosts_send_receive')

        self.assertIsNotNone(message)
        self.assertEqual(payload, msgpack.unpackb(message, encoding='utf-8'))

    def test_refresh_interval_hashed_server_send_receive(self):
        client = self._set_up_client(sentinel_refresh_interval=10)

        payload1 = {'test': 'some value'}

        client.send_message_to_queue(
            queue_key='test_hashed_send_receive!',
            message=msgpack.packb(payload1),
            expiry=10,
            capacity=10,
            connection=client.get_connection('test_hashed_send_receive!'),
        )

        message = client.get_connection('test_hashed_send_receive!').lpop('test_hashed_send_receive!')

        self.assertIsNotNone(message)
        self.assertEqual(payload1, msgpack.unpackb(message, encoding='utf-8'))

        payload2 = {'for': 'another value'}

        client.send_message_to_queue(
            queue_key='test_hashed_send_receive!',
            message=msgpack.packb(payload2),
            expiry=10,
            capacity=10,
            connection=client.get_connection('test_hashed_send_receive!'),
        )

        message = client.get_connection('test_hashed_send_receive!').lpop('test_hashed_send_receive!')

        self.assertIsNotNone(message)
        self.assertEqual(payload2, msgpack.unpackb(message, encoding='utf-8'))

        payload3 = {'hashing': 'will this work'}

        client.send_message_to_queue(
            queue_key='test_hashed_send_receive!',
            message=msgpack.packb(payload3),
            expiry=10,
            capacity=10,
            connection=client.get_connection('test_hashed_send_receive!'),
        )

        message = client.get_connection('test_hashed_send_receive!').lpop('test_hashed_send_receive!')

        self.assertIsNotNone(message)
        self.assertEqual(payload3, msgpack.unpackb(message, encoding='utf-8'))
