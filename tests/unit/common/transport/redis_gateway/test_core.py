from __future__ import (
    absolute_import,
    unicode_literals,
)

import datetime
import time
import timeit
from typing import (
    Any,
    Dict,
)

import attr
import freezegun
import pytest
import six

from pysoa.common.serializer.json_serializer import JSONSerializer
from pysoa.common.serializer.msgpack_serializer import MsgpackSerializer
from pysoa.common.transport.errors import (
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
    ProtocolVersion,
)
from pysoa.common.transport.redis_gateway.core import (
    RedisTransportClientCore,
    RedisTransportCore,
    RedisTransportServerCore,
)
from pysoa.test.compatibility import mock

# To ensure all the patching over there happens over here
from tests.unit.common.transport.redis_gateway.backend.test_standard import mockredis


@attr.s
class MockSerializer(object):
    kwarg1 = attr.ib(default=None)
    kwarg2 = attr.ib(default=None)


@mock.patch('redis.Redis', new=mockredis.mock_redis_client)
class TestRedisTransportCore(object):
    def setup_method(self, _method):
        RedisTransportCore._backend_layer_cache = {}

    def test_invalid_backend_type(self):
        with pytest.raises(ValueError):
            # noinspection PyArgumentList
            RedisTransportServerCore(backend_type='hello')

    @mock.patch('pysoa.common.transport.redis_gateway.core.SentinelRedisClient')
    @mock.patch('pysoa.common.transport.redis_gateway.core.StandardRedisClient')
    def test_standard_client_created_with_defaults(self, mock_standard, mock_sentinel):
        # noinspection PyArgumentList
        core = RedisTransportServerCore(backend_type=REDIS_BACKEND_TYPE_STANDARD)
        core.backend_layer.anything()  # type: ignore

        assert core.message_expiry_in_seconds == 60
        assert core.queue_capacity == 10000
        assert core.queue_full_retries == 10
        assert core.receive_timeout_in_seconds == 5
        assert isinstance(core.default_serializer, MsgpackSerializer)

        mock_standard.assert_called_once_with()
        mock_standard.return_value.anything.assert_called_once_with()
        assert not mock_sentinel.called

    @mock.patch('pysoa.common.transport.redis_gateway.core.SentinelRedisClient')
    @mock.patch('pysoa.common.transport.redis_gateway.core.StandardRedisClient')
    def test_standard_client_created(self, mock_standard, mock_sentinel):
        # noinspection PyArgumentList
        core = RedisTransportServerCore(
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
        core.backend_layer.anything()  # type: ignore

        assert core.service_name == 'example'
        assert core.message_expiry_in_seconds == 30
        assert core.queue_capacity == 100
        assert core.queue_full_retries == 7
        assert core.receive_timeout_in_seconds == 10
        assert isinstance(core.default_serializer, MockSerializer)
        assert core.default_serializer.kwarg1 == 'hello'

        mock_standard.assert_called_once_with(
            hosts=[('localhost', 6379), ('far_away_host', 1098)],
            connection_kwargs={'db': 2},
        )
        mock_standard.return_value.anything.assert_called_once_with()
        assert not mock_sentinel.called

    @mock.patch('pysoa.common.transport.redis_gateway.core.SentinelRedisClient')
    @mock.patch('pysoa.common.transport.redis_gateway.core.StandardRedisClient')
    def test_sentinel_client_created(self, mock_standard, mock_sentinel):
        # noinspection PyArgumentList
        core = RedisTransportServerCore(
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
        core.backend_layer.anything()  # type: ignore

        assert core.message_expiry_in_seconds == 45
        assert core.queue_capacity == 7500
        assert core.queue_full_retries == 4
        assert core.receive_timeout_in_seconds == 6
        assert isinstance(core.default_serializer, MockSerializer)
        assert core.default_serializer.kwarg2 == 'goodbye'

        mock_sentinel.assert_called_once_with(
            hosts=[('another_host', 6379)],
            connection_kwargs={'db': 5, 'hello': 'world'},
            sentinel_refresh_interval=13,
            sentinel_services=['svc1', 'svc2', 'svc3'],
            sentinel_failover_retries=5,
        )
        mock_sentinel.return_value.anything.assert_called_once_with()
        assert not mock_standard.called

    @mock.patch('pysoa.common.transport.redis_gateway.core.SentinelRedisClient')
    @mock.patch('pysoa.common.transport.redis_gateway.core.StandardRedisClient')
    def test_chunking_not_supported_on_client(self, mock_standard, mock_sentinel):
        with pytest.raises(TypeError) as error_context:
            # noinspection PyArgumentList
            RedisTransportClientCore(  # type: ignore
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
                chunk_messages_larger_than_bytes=102400,
            )

        assert "unexpected keyword argument 'chunk_messages_larger_than_bytes'" in error_context.value.args[0]

        assert not mock_standard.called
        assert not mock_sentinel.called

    @mock.patch('pysoa.common.transport.redis_gateway.core.SentinelRedisClient')
    @mock.patch('pysoa.common.transport.redis_gateway.core.StandardRedisClient')
    def test_chunking_too_small_on_server(self, mock_standard, mock_sentinel):
        with pytest.raises(ValueError) as error_context:
            # noinspection PyArgumentList
            RedisTransportServerCore(
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
                chunk_messages_larger_than_bytes=1024,
            )

        assert 'must be >= 102400' in error_context.value.args[0]

        assert not mock_standard.called
        assert not mock_sentinel.called

    @mock.patch('pysoa.common.transport.redis_gateway.core.SentinelRedisClient')
    @mock.patch('pysoa.common.transport.redis_gateway.core.StandardRedisClient')
    def test_max_message_size_not_bigger_enough_than_chunking_on_server(self, mock_standard, mock_sentinel):
        with pytest.raises(ValueError) as error_context:
            # noinspection PyArgumentList
            RedisTransportServerCore(
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
                chunk_messages_larger_than_bytes=102400,
                maximum_message_size_in_bytes=(102400 * 5) - 2,
            )

        assert 'at least 5 times larger' in error_context.value.args[0]

        assert not mock_standard.called
        assert not mock_sentinel.called

    @mock.patch('pysoa.common.transport.redis_gateway.core.SentinelRedisClient')
    @mock.patch('pysoa.common.transport.redis_gateway.core.StandardRedisClient')
    def test_chunking_supported_on_server(self, mock_standard, mock_sentinel):
        # noinspection PyArgumentList
        core = RedisTransportServerCore(
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
            chunk_messages_larger_than_bytes=102400,
            maximum_message_size_in_bytes=102400 * 5,
        )
        core.backend_layer.anything()  # type: ignore

        assert core.message_expiry_in_seconds == 45
        assert core.queue_capacity == 7500
        assert core.queue_full_retries == 4
        assert core.receive_timeout_in_seconds == 6
        assert core.chunk_messages_larger_than_bytes == 102400
        assert core.maximum_message_size_in_bytes == 102400 * 5
        assert isinstance(core.default_serializer, MockSerializer)
        assert core.default_serializer.kwarg2 == 'goodbye'

        mock_sentinel.assert_called_once_with(
            hosts=[('another_host', 6379)],
            connection_kwargs={'db': 5, 'hello': 'world'},
            sentinel_refresh_interval=13,
            sentinel_services=['svc1', 'svc2', 'svc3'],
            sentinel_failover_retries=5,
        )
        mock_sentinel.return_value.anything.assert_called_once_with()
        assert not mock_standard.called

    @mock.patch('pysoa.common.transport.redis_gateway.core.SentinelRedisClient')
    @mock.patch('pysoa.common.transport.redis_gateway.core.StandardRedisClient')
    def test_cannot_get_connection_error_on_send(self, mock_standard, mock_sentinel):
        # noinspection PyArgumentList
        core = RedisTransportServerCore(backend_type=REDIS_BACKEND_TYPE_STANDARD)

        mock_standard.return_value.get_connection.side_effect = CannotGetConnectionError('This is my error')

        with pytest.raises(MessageSendError) as error_context:
            core.send_message('my_queue', 71, {}, {})

        assert error_context.value.args[0] == 'Cannot get connection: This is my error'

        assert not mock_sentinel.called
        mock_standard.return_value.get_connection.assert_called_once_with('pysoa:my_queue')

    @mock.patch('pysoa.common.transport.redis_gateway.core.SentinelRedisClient')
    @mock.patch('pysoa.common.transport.redis_gateway.core.StandardRedisClient')
    def test_cannot_get_connection_error_on_receive(self, mock_standard, mock_sentinel):
        # noinspection PyArgumentList
        core = RedisTransportServerCore(backend_type=REDIS_BACKEND_TYPE_STANDARD)

        mock_standard.return_value.get_connection.side_effect = CannotGetConnectionError('This is another error')

        with pytest.raises(MessageReceiveError) as error_context:
            core.receive_message('your_queue')

        assert error_context.value.args[0] == 'Cannot get connection: This is another error'

        assert not mock_sentinel.called
        mock_standard.return_value.get_connection.assert_called_once_with('pysoa:your_queue')

    @staticmethod
    def _get_server_core(**kwargs):
        # noinspection PyArgumentList
        return RedisTransportServerCore(backend_type=REDIS_BACKEND_TYPE_STANDARD, **kwargs)

    @staticmethod
    def _get_client_core(**kwargs):
        # noinspection PyArgumentList
        return RedisTransportClientCore(backend_type=REDIS_BACKEND_TYPE_STANDARD, **kwargs)

    def test_invalid_request_id(self):
        core = self._get_server_core()

        with pytest.raises(InvalidMessageError):
            # noinspection PyTypeChecker
            core.send_message('test_invalid_request_id', None, {}, {'test': 'payload'})

    def test_message_too_large_client_default(self):
        core = self._get_client_core()

        message = {'test': ['payload%i' % i for i in range(1000, 9530)]}  # This creates a message > 102,400 bytes

        with pytest.raises(MessageTooLarge):
            core.send_message('test_message_too_large_client_default', 0, {}, message)

    def test_message_too_large_server_default(self):
        core = self._get_server_core()

        message = {'test': ['payload%i' % i for i in range(1000, 9530)]}  # This creates a message > 102,400 bytes
        core.send_message('test_message_too_large_server_default_ok', 0, {}, message)

        message = {'test': ['payload%i' % i for i in range(10000, 29900)]}  # This creates a message > 257,024 bytes

        with pytest.raises(MessageTooLarge):
            core.send_message('test_message_too_large_server_default_not_ok', 0, {}, message)

    def test_message_too_large_configurable(self):
        core = self._get_server_core(maximum_message_size_in_bytes=150)

        message = {'test': ['payload%i' % i for i in range(100, 110)]}  # This creates a message > 150 bytes

        with pytest.raises(MessageTooLarge):
            core.send_message('test_message_too_large', 1, {}, message)

    def test_oversized_message_is_logged(self):
        core = self._get_server_core(log_messages_larger_than_bytes=150)

        message = {'test': ['payload%i' % i for i in range(100, 110)]}  # This creates a message > 150 bytes

        core.send_message('test_message_too_large', 1, {}, message)

    def test_simple_send_and_receive_default_expiry(self):
        core = self._get_server_core()

        request_id = 27
        meta = {'app': 52}
        message = {'test': 'payload'}

        t = time.time()
        core.send_message('test_simple_send_and_receive_default_expiry', request_id, meta, message)

        response = core.receive_message('test_simple_send_and_receive_default_expiry')

        assert response.request_id == request_id
        assert response.meta['app'] == 52
        assert 'serializer' in response.meta
        assert 'protocol_version' in response.meta
        assert '__expiry__' in response.meta
        assert len(response.meta) == 4
        assert response.body == message

        assert '__expiry__' in meta
        assert response[1]['__expiry__'] == meta['__expiry__']
        assert (t + 59.9) < meta['__expiry__'] < (t + 61.1)

    def test_simple_send_and_receive_expiry_override(self):
        core = self._get_server_core()

        request_id = 31
        meta = {'application': 79}
        message = {'test': 'payload'}

        t = time.time()
        core.send_message(
            'test_simple_send_and_receive_expiry_override',
            request_id,
            meta,
            message,
            message_expiry_in_seconds=10,
        )

        response = core.receive_message('test_simple_send_and_receive_expiry_override')

        assert response.request_id == request_id
        assert response.meta['application'] == 79
        assert 'serializer' in response.meta
        assert 'protocol_version' in response.meta
        assert '__expiry__' in response.meta
        assert len(response.meta) == 4
        assert response.body == message

        assert '__expiry__' in meta
        assert response[1]['__expiry__'] == meta['__expiry__']
        assert (t + 9.9) < meta['__expiry__'] < (t + 10.1)

    def test_send_queue_full(self):
        core = self._get_server_core(queue_full_retries=1, queue_capacity=3)

        request_id1 = 32
        request_id2 = 33
        request_id3 = 34
        request_id4 = 35
        request_id5 = 36

        core.send_message('test_send_queue_full', request_id1, {}, {'test': 'payload1'})
        core.send_message('test_send_queue_full', request_id2, {}, {'test': 'payload2'})
        core.send_message('test_send_queue_full', request_id3, {}, {'test': 'payload3'})

        with pytest.raises(MessageSendError) as error_context:
            core.send_message('test_send_queue_full', request_id4, {}, {'test': 'payload4'})

        assert 'test_send_queue_full was full' in error_context.value.args[0]

        response = core.receive_message('test_send_queue_full')
        assert response[0] == request_id1
        assert response[2]['test'] == 'payload1'

        core.send_message('test_send_queue_full', request_id4, {}, {'test': 'payload4'})

        with pytest.raises(MessageSendError) as error_context:
            core.send_message('test_send_queue_full', request_id5, {}, {'test': 'payload5'})

        assert 'test_send_queue_full was full' in error_context.value.args[0]

        response = core.receive_message('test_send_queue_full')
        assert response[0] == request_id2
        assert response[2]['test'] == 'payload2'

        core.send_message('test_send_queue_full', request_id5, {}, {'test': 'payload5'})

        response = core.receive_message('test_send_queue_full')
        assert response[0] == request_id3
        assert response[2]['test'] == 'payload3'

        response = core.receive_message('test_send_queue_full')
        assert response[0] == request_id4
        assert response[2]['test'] == 'payload4'

        response = core.receive_message('test_send_queue_full')
        assert response[0] == request_id5
        assert response[2]['test'] == 'payload5'

    def test_receive_timeout_default(self):
        core = self._get_server_core(receive_timeout_in_seconds=1)

        start = timeit.default_timer()
        with pytest.raises(MessageReceiveTimeout) as error_context:
            core.receive_message('test_receive_timeout')
        elapsed = timeit.default_timer() - start

        assert 'received' in error_context.value.args[0]
        assert 0.9 < elapsed < 1.1

    def test_receive_timeout_override(self):
        core = self._get_server_core()

        start = timeit.default_timer()
        with pytest.raises(MessageReceiveTimeout) as error_context:
            core.receive_message('test_receive_timeout', receive_timeout_in_seconds=1)
        elapsed = timeit.default_timer() - start

        assert 'received' in error_context.value.args[0]
        assert 0.9 < elapsed < 1.1

    def test_expired_message(self):
        core = self._get_server_core(receive_timeout_in_seconds=3, message_expiry_in_seconds=10)

        with freezegun.freeze_time(ignore=['mockredis.client', 'mockredis.clock', 'timeit']) as frozen_time:
            core.send_message('test_expired_message', 42, {}, {'test': 'payload'})

            frozen_time.tick(datetime.timedelta(seconds=11))

            start = timeit.default_timer()
            with pytest.raises(MessageReceiveTimeout) as error_context:
                core.receive_message('test_expired_message')
            elapsed = timeit.default_timer() - start

            assert 0 < elapsed < 0.1  # This shouldn't actually take 3 seconds, it should be instant
            assert 'expired' in error_context.value.args[0]

            frozen_time.tick(datetime.timedelta(seconds=1))

            request_id = 19
            core.send_message('test_expired_message', request_id, {}, {'test': 'payload'})

            frozen_time.tick(datetime.timedelta(seconds=10))

            start = timeit.default_timer()
            response = core.receive_message('test_expired_message')
            elapsed = timeit.default_timer() - start

            assert 0 < elapsed < 0.1
            assert response[0] == request_id

    @mock.patch('pysoa.common.transport.redis_gateway.core.StandardRedisClient')
    def test_content_type_default(self, mock_standard):
        core = self._get_server_core(receive_timeout_in_seconds=3, message_expiry_in_seconds=10)

        mock_standard.return_value.get_connection.return_value.blpop.return_value = [
            True,
            MsgpackSerializer().dict_to_blob({'request_id': 15, 'meta': {}, 'body': {'foo': 'bar'}}),
        ]

        request_id, meta, body = core.receive_message('test_content_type_default')

        assert request_id == 15
        assert 'serializer' in meta
        assert 'protocol_version' in meta
        assert len(meta) == 2
        assert meta['protocol_version'] == ProtocolVersion.VERSION_1
        assert isinstance(meta['serializer'], MsgpackSerializer)
        assert body == {'foo': 'bar'}

        mock_standard.return_value.get_connection.return_value.blpop.assert_called_once_with(
            ['pysoa:test_content_type_default'],
            timeout=core.receive_timeout_in_seconds,
        )

        core.send_message('test_content_type_default:reply', 15, meta, {'yep': 'nope'})

        call_kwargs = mock_standard.return_value.send_message_to_queue.call_args_list[0][1]

        assert call_kwargs['queue_key'] == 'pysoa:test_content_type_default:reply'
        assert call_kwargs['expiry'] == core.message_expiry_in_seconds
        assert call_kwargs['capacity'] == core.queue_capacity
        assert call_kwargs['connection'] == mock_standard.return_value.get_connection.return_value

        assert not call_kwargs['message'].startswith(b'pysoa-redis/')
        assert not call_kwargs['message'].startswith(b'content-type')

        message = MsgpackSerializer().blob_to_dict(call_kwargs['message'])
        assert message['request_id'] == 15
        assert message['meta']['__expiry__'] <= time.time() + core.message_expiry_in_seconds
        assert message['body'] == {'yep': 'nope'}

    @mock.patch('pysoa.common.transport.redis_gateway.core.StandardRedisClient')
    def test_content_type_default_with_version(self, mock_standard):
        core = self._get_server_core(receive_timeout_in_seconds=3, message_expiry_in_seconds=10)

        mock_standard.return_value.get_connection.return_value.blpop.return_value = [
            True,
            (
                b'pysoa-redis/3//' +
                MsgpackSerializer().dict_to_blob({'request_id': 16, 'meta': {}, 'body': {'foo': 'bar'}})
            ),
        ]

        request_id, meta, body = core.receive_message('test_content_type_default_with_version')

        assert request_id == 16
        assert 'serializer' in meta
        assert 'protocol_version' in meta
        assert len(meta) == 2
        assert meta['protocol_version'] == ProtocolVersion.VERSION_3
        assert isinstance(meta['serializer'], MsgpackSerializer)
        assert body == {'foo': 'bar'}

        mock_standard.return_value.get_connection.return_value.blpop.assert_called_once_with(
            ['pysoa:test_content_type_default_with_version'],
            timeout=core.receive_timeout_in_seconds,
        )

        core.send_message('test_content_type_default_with_version:reply', 16, meta, {'yep': 'nope'})

        call_kwargs = mock_standard.return_value.send_message_to_queue.call_args_list[0][1]

        assert call_kwargs['queue_key'] == 'pysoa:test_content_type_default_with_version:reply'
        assert call_kwargs['expiry'] == core.message_expiry_in_seconds
        assert call_kwargs['capacity'] == core.queue_capacity
        assert call_kwargs['connection'] == mock_standard.return_value.get_connection.return_value

        assert call_kwargs['message'].startswith(b'pysoa-redis/3//content-type:application/msgpack;')

        message = MsgpackSerializer().blob_to_dict(
            call_kwargs['message'][len(b'pysoa-redis/3//content-type:application/msgpack;'):],
        )
        assert message['request_id'] == 16
        assert message['meta']['__expiry__'] <= time.time() + core.message_expiry_in_seconds
        assert message['body'] == {'yep': 'nope'}

    @mock.patch('pysoa.common.transport.redis_gateway.core.StandardRedisClient')
    def test_content_type_explicit_msgpack(self, mock_standard):
        core = self._get_server_core(receive_timeout_in_seconds=3, message_expiry_in_seconds=10)

        mock_standard.return_value.get_connection.return_value.blpop.return_value = [
            True,
            (
                b'content-type:application/msgpack;' +
                MsgpackSerializer().dict_to_blob({'request_id': 71, 'meta': {}, 'body': {'baz': 'qux'}})
            ),
        ]

        request_id, meta, body = core.receive_message('test_content_type_explicit_msgpack')

        assert request_id == 71
        assert 'serializer' in meta
        assert 'protocol_version' in meta
        assert len(meta) == 2
        assert meta['protocol_version'] == ProtocolVersion.VERSION_2
        assert isinstance(meta['serializer'], MsgpackSerializer)
        assert body == {'baz': 'qux'}

        mock_standard.return_value.get_connection.return_value.blpop.assert_called_once_with(
            ['pysoa:test_content_type_explicit_msgpack'],
            timeout=core.receive_timeout_in_seconds,
        )

        core.send_message('test_content_type_explicit_msgpack:reply', 71, meta, {'nope': 'yep'})

        call_kwargs = mock_standard.return_value.send_message_to_queue.call_args_list[0][1]

        assert call_kwargs['queue_key'] == 'pysoa:test_content_type_explicit_msgpack:reply'
        assert call_kwargs['expiry'] == core.message_expiry_in_seconds
        assert call_kwargs['capacity'] == core.queue_capacity
        assert call_kwargs['connection'] == mock_standard.return_value.get_connection.return_value

        assert call_kwargs['message'].startswith(b'content-type:application/msgpack;')

        message = MsgpackSerializer().blob_to_dict(call_kwargs['message'][len(b'content-type:application/msgpack;'):])
        assert message['request_id'] == 71
        assert message['meta']['__expiry__'] <= time.time() + core.message_expiry_in_seconds
        assert message['body'] == {'nope': 'yep'}

    @mock.patch('pysoa.common.transport.redis_gateway.core.StandardRedisClient')
    def test_content_type_explicit_msgpack_with_version(self, mock_standard):
        core = self._get_server_core(receive_timeout_in_seconds=3, message_expiry_in_seconds=10)

        mock_standard.return_value.get_connection.return_value.blpop.return_value = [
            True,
            (
                    b'pysoa-redis/3//content-type:application/msgpack;' +
                    MsgpackSerializer().dict_to_blob({'request_id': 72, 'meta': {}, 'body': {'baz': 'qux'}})
            ),
        ]

        request_id, meta, body = core.receive_message('test_content_type_explicit_msgpack_with_version')

        assert request_id == 72
        assert 'serializer' in meta
        assert 'protocol_version' in meta
        assert len(meta) == 2
        assert meta['protocol_version'] == ProtocolVersion.VERSION_3
        assert isinstance(meta['serializer'], MsgpackSerializer)
        assert body == {'baz': 'qux'}

        mock_standard.return_value.get_connection.return_value.blpop.assert_called_once_with(
            ['pysoa:test_content_type_explicit_msgpack_with_version'],
            timeout=core.receive_timeout_in_seconds,
        )

        core.send_message('test_content_type_explicit_msgpack_with_version:reply', 72, meta, {'nope': 'yep'})

        call_kwargs = mock_standard.return_value.send_message_to_queue.call_args_list[0][1]

        assert call_kwargs['queue_key'] == 'pysoa:test_content_type_explicit_msgpack_with_version:reply'
        assert call_kwargs['expiry'] == core.message_expiry_in_seconds
        assert call_kwargs['capacity'] == core.queue_capacity
        assert call_kwargs['connection'] == mock_standard.return_value.get_connection.return_value

        assert call_kwargs['message'].startswith(b'pysoa-redis/3//content-type:application/msgpack;')

        message = MsgpackSerializer().blob_to_dict(
            call_kwargs['message'][len(b'pysoa-redis/3//content-type:application/msgpack;'):],
        )
        assert message['request_id'] == 72
        assert message['meta']['__expiry__'] <= time.time() + core.message_expiry_in_seconds
        assert message['body'] == {'nope': 'yep'}

    @mock.patch('pysoa.common.transport.redis_gateway.core.StandardRedisClient')
    def test_content_type_explicit_json(self, mock_standard):
        core = self._get_server_core(receive_timeout_in_seconds=3, message_expiry_in_seconds=10)

        mock_standard.return_value.get_connection.return_value.blpop.return_value = [
            True,
            (
                b'content-type : application/json ;' +
                JSONSerializer().dict_to_blob({'request_id': 43, 'meta': {}, 'body': {'foo': 'bar'}})
            ),
        ]

        request_id, meta, body = core.receive_message('test_content_type_explicit_json')

        assert request_id == 43
        assert 'serializer' in meta
        assert 'protocol_version' in meta
        assert len(meta) == 2
        assert meta['protocol_version'] == ProtocolVersion.VERSION_2
        assert isinstance(meta['serializer'], JSONSerializer)
        assert body == {'foo': 'bar'}

        mock_standard.return_value.get_connection.return_value.blpop.assert_called_once_with(
            ['pysoa:test_content_type_explicit_json'],
            timeout=core.receive_timeout_in_seconds,
        )

        core.send_message('test_content_type_explicit_json:reply', 43, meta, {'yep': 'nope'})

        call_kwargs = mock_standard.return_value.send_message_to_queue.call_args_list[0][1]

        assert call_kwargs['queue_key'] == 'pysoa:test_content_type_explicit_json:reply'
        assert call_kwargs['expiry'] == core.message_expiry_in_seconds
        assert call_kwargs['capacity'] == core.queue_capacity
        assert call_kwargs['connection'] == mock_standard.return_value.get_connection.return_value

        assert call_kwargs['message'].startswith(b'content-type:application/json;')

        message = JSONSerializer().blob_to_dict(call_kwargs['message'][len(b'content-type:application/json;'):])
        assert message['request_id'] == 43
        assert message['meta']['__expiry__'] <= time.time() + core.message_expiry_in_seconds
        assert message['body'] == {'yep': 'nope'}

    @mock.patch('pysoa.common.transport.redis_gateway.core.StandardRedisClient')
    def test_content_type_explicit_json_with_version(self, mock_standard):
        core = self._get_server_core(receive_timeout_in_seconds=3, message_expiry_in_seconds=10)

        mock_standard.return_value.get_connection.return_value.blpop.return_value = [
            True,
            (
                    b'pysoa-redis/3//content-type : application/json ;' +
                    JSONSerializer().dict_to_blob({'request_id': 44, 'meta': {}, 'body': {'foo': 'bar'}})
            ),
        ]

        request_id, meta, body = core.receive_message('test_content_type_explicit_json_with_version')

        assert request_id == 44
        assert 'serializer' in meta
        assert 'protocol_version' in meta
        assert len(meta) == 2
        assert meta['protocol_version'] == ProtocolVersion.VERSION_3
        assert isinstance(meta['serializer'], JSONSerializer)
        assert body == {'foo': 'bar'}

        mock_standard.return_value.get_connection.return_value.blpop.assert_called_once_with(
            ['pysoa:test_content_type_explicit_json_with_version'],
            timeout=core.receive_timeout_in_seconds,
        )

        core.send_message('test_content_type_explicit_json_with_version:reply', 44, meta, {'yep': 'nope'})

        call_kwargs = mock_standard.return_value.send_message_to_queue.call_args_list[0][1]

        assert call_kwargs['queue_key'] == 'pysoa:test_content_type_explicit_json_with_version:reply'
        assert call_kwargs['expiry'] == core.message_expiry_in_seconds
        assert call_kwargs['capacity'] == core.queue_capacity
        assert call_kwargs['connection'] == mock_standard.return_value.get_connection.return_value

        assert call_kwargs['message'].startswith(b'pysoa-redis/3//content-type:application/json;')

        message = JSONSerializer().blob_to_dict(
            call_kwargs['message'][len(b'pysoa-redis/3//content-type:application/json;'):],
        )
        assert message['request_id'] == 44
        assert message['meta']['__expiry__'] <= time.time() + core.message_expiry_in_seconds
        assert message['body'] == {'yep': 'nope'}

    @mock.patch('pysoa.common.transport.redis_gateway.core.StandardRedisClient')
    def test_receive_chunking_prohibited_on_server(self, mock_standard):
        core = self._get_server_core(receive_timeout_in_seconds=3, message_expiry_in_seconds=10)

        message = {'request_id': 79, 'meta': {'yes': 'no'}, 'body': {'baz': 'qux'}}
        message['body'].update({'key-{}'.format(i): 'value-{}'.format(i) for i in range(200)})  # type: ignore

        serialized = MsgpackSerializer().dict_to_blob(message)

        mock_standard.return_value.get_connection.return_value.blpop.side_effect = [
            [True, (b'pysoa-redis/3//chunk-count:4;chunk-id:1;' + serialized[0:1000])],
            [True, (b'pysoa-redis/3//chunk-count:4;chunk-id:2;' + serialized[1000:2000])],
            [True, (b'pysoa-redis/3//chunk-count:4;chunk-id:3;' + serialized[2000:3000])],
            [True, (b'pysoa-redis/3//chunk-count:4;chunk-id:4;' + serialized[3000:])],
        ]

        with pytest.raises(InvalidMessageError) as error_context:
            core.receive_message('test_receive_chunking_prohibited_on_server')

        assert 'Unsupported chunked request' in error_context.value.args[0]

    @mock.patch('pysoa.common.transport.redis_gateway.core.StandardRedisClient')
    def test_receive_chunking_successful_on_client(self, mock_standard):
        core = self._get_client_core(receive_timeout_in_seconds=3, message_expiry_in_seconds=10)

        message = {'request_id': 79, 'meta': {'yes': 'no'}, 'body': {'baz': 'qux'}}
        message['body'].update({'key-{}'.format(i): 'value-{}'.format(i) for i in range(200)})  # type: ignore

        serialized = MsgpackSerializer().dict_to_blob(message)

        mock_standard.return_value.get_connection.return_value.blpop.side_effect = [
            [True, (b'pysoa-redis/3//chunk-count:4;chunk-id:1;' + serialized[0:1000])],
            [True, (b'pysoa-redis/3//chunk-count:4;chunk-id:2;' + serialized[1000:2000])],
            [True, (b'pysoa-redis/3//chunk-count:4;chunk-id:3;' + serialized[2000:3000])],
            [True, (b'pysoa-redis/3//chunk-count:4;chunk-id:4;' + serialized[3000:])],
        ]

        request_id, meta, body = core.receive_message('test_receive_chunking_successful_on_client')

        assert request_id == 79
        assert 'serializer' in meta
        assert 'protocol_version' in meta
        assert meta['yes'] == 'no'
        assert len(meta) == 3
        assert meta['protocol_version'] == ProtocolVersion.VERSION_3
        assert isinstance(meta['serializer'], MsgpackSerializer)
        assert body == message['body']

    @mock.patch('pysoa.common.transport.redis_gateway.core.StandardRedisClient')
    def test_receive_chunking_successful_on_client_with_msgpack_content_type(self, mock_standard):
        core = self._get_client_core(receive_timeout_in_seconds=3, message_expiry_in_seconds=10)

        message = {'request_id': 80, 'meta': {'no': 'yes'}, 'body': {'foo': 'bar'}}
        message['body'].update({'key-{}'.format(i): 'value-{}'.format(i) for i in range(200)})  # type: ignore

        serialized = MsgpackSerializer().dict_to_blob(message)

        mock_standard.return_value.get_connection.return_value.blpop.side_effect = [
            [True, (b'pysoa-redis/3//chunk-count:4;content-type:application/msgpack;chunk-id:1;' + serialized[0:1000])],
            [True, (b'pysoa-redis/3//chunk-count:4;chunk-id:2;' + serialized[1000:2000])],
            [True, (b'pysoa-redis/3//chunk-count:4;chunk-id:3;' + serialized[2000:3000])],
            [True, (b'pysoa-redis/3//chunk-count:4;chunk-id:4;' + serialized[3000:])],
        ]

        request_id, meta, body = core.receive_message(
            'test_receive_chunking_successful_on_client_with_msgpack_content_type',
        )

        assert request_id == 80
        assert 'serializer' in meta
        assert 'protocol_version' in meta
        assert meta['no'] == 'yes'
        assert len(meta) == 3
        assert meta['protocol_version'] == ProtocolVersion.VERSION_3
        assert isinstance(meta['serializer'], MsgpackSerializer)
        assert body == message['body']

    @mock.patch('pysoa.common.transport.redis_gateway.core.StandardRedisClient')
    def test_receive_chunking_successful_on_client_with_json_content_type(self, mock_standard):
        core = self._get_client_core(receive_timeout_in_seconds=3, message_expiry_in_seconds=10)

        message = {'request_id': 83, 'meta': {'no': 'yes'}, 'body': {'baz': 'qux'}}
        message['body'].update({'key-{}'.format(i): 'value-{}'.format(i) for i in range(200)})  # type: ignore

        serialized = JSONSerializer().dict_to_blob(message)

        mock_standard.return_value.get_connection.return_value.blpop.side_effect = [
            [True, (b'pysoa-redis/3//chunk-count:4;chunk-id:1;content-type:application/json;' + serialized[0:1000])],
            [True, (b'pysoa-redis/3//chunk-count:4;chunk-id:2;' + serialized[1000:2000])],
            [True, (b'pysoa-redis/3//chunk-count:4;chunk-id:3;' + serialized[2000:3000])],
            [True, (b'pysoa-redis/3//chunk-count:4;chunk-id:4;' + serialized[3000:])],
        ]

        request_id, meta, body = core.receive_message(
            'test_receive_chunking_successful_on_client_with_json_content_type',
        )

        assert request_id == 83
        assert 'serializer' in meta
        assert 'protocol_version' in meta
        assert meta['no'] == 'yes'
        assert len(meta) == 3
        assert meta['protocol_version'] == ProtocolVersion.VERSION_3
        assert isinstance(meta['serializer'], JSONSerializer)
        assert body == message['body']

    @mock.patch('pysoa.common.transport.redis_gateway.core.StandardRedisClient')
    def test_receive_chunking_fails_on_client_missing_header(self, mock_standard):
        core = self._get_client_core(receive_timeout_in_seconds=3, message_expiry_in_seconds=10)

        message = {'request_id': 79, 'meta': {'yes': 'no'}, 'body': {'baz': 'qux'}}
        message['body'].update({'key-{}'.format(i): 'value-{}'.format(i) for i in range(200)})  # type: ignore

        serialized = MsgpackSerializer().dict_to_blob(message)

        mock_standard.return_value.get_connection.return_value.blpop.side_effect = [
            [True, (b'pysoa-redis/3//chunk-count:4;' + serialized[0:1000])],
            [True, (b'pysoa-redis/3//chunk-count:4;chunk-id:2;' + serialized[1000:2000])],
            [True, (b'pysoa-redis/3//chunk-count:4;chunk-id:3;' + serialized[2000:3000])],
            [True, (b'pysoa-redis/3//chunk-count:4;chunk-id:4;' + serialized[3000:])],
        ]

        with pytest.raises(InvalidMessageError) as error_context:
            core.receive_message('test_receive_chunking_fails_on_client_missing_header')

        assert 'missing chunk ID' in error_context.value.args[0]

    @mock.patch('pysoa.common.transport.redis_gateway.core.StandardRedisClient')
    def test_receive_chunking_fails_on_client_subsequent_chunk_missing_headers(self, mock_standard):
        core = self._get_client_core(receive_timeout_in_seconds=3, message_expiry_in_seconds=10)

        message = {'request_id': 79, 'meta': {'yes': 'no'}, 'body': {'baz': 'qux'}}
        message['body'].update({'key-{}'.format(i): 'value-{}'.format(i) for i in range(200)})  # type: ignore

        serialized = MsgpackSerializer().dict_to_blob(message)

        mock_standard.return_value.get_connection.return_value.blpop.side_effect = [
            [True, (b'pysoa-redis/3//chunk-count:4;chunk-id:1;' + serialized[0:1000])],
            [True, (b'pysoa-redis/3//chunk-id:2;' + serialized[1000:2000])],
            [True, (b'pysoa-redis/3//chunk-count:4;chunk-id:3;' + serialized[2000:3000])],
            [True, (b'pysoa-redis/3//chunk-count:4;chunk-id:4;' + serialized[3000:])],
        ]

        with pytest.raises(InvalidMessageError) as error_context:
            core.receive_message('test_receive_chunking_fails_on_client_subsequent_chunk_missing_headers')

        assert 'missing chunk headers' in error_context.value.args[0]

    @mock.patch('pysoa.common.transport.redis_gateway.core.StandardRedisClient')
    def test_receive_chunking_fails_on_client_subsequent_chunk_count_differs(self, mock_standard):
        core = self._get_client_core(receive_timeout_in_seconds=3, message_expiry_in_seconds=10)

        message = {'request_id': 79, 'meta': {'yes': 'no'}, 'body': {'baz': 'qux'}}
        message['body'].update({'key-{}'.format(i): 'value-{}'.format(i) for i in range(200)})  # type: ignore

        serialized = MsgpackSerializer().dict_to_blob(message)

        mock_standard.return_value.get_connection.return_value.blpop.side_effect = [
            [True, (b'pysoa-redis/3//chunk-count:4;chunk-id:1;' + serialized[0:1000])],
            [True, (b'pysoa-redis/3//chunk-count:4;chunk-id:2;' + serialized[1000:2000])],
            [True, (b'pysoa-redis/3//chunk-count:4;chunk-id:3;' + serialized[2000:3000])],
            [True, (b'pysoa-redis/3//chunk-count:5;chunk-id:4;' + serialized[3000:])],
        ]

        with pytest.raises(InvalidMessageError) as error_context:
            core.receive_message('test_receive_chunking_fails_on_client_subsequent_chunk_count_differs')

        assert 'different chunk count' in error_context.value.args[0]

    @mock.patch('pysoa.common.transport.redis_gateway.core.StandardRedisClient')
    def test_receive_chunking_fails_on_client_subsequent_chunk_id_is_unexpected(self, mock_standard):
        core = self._get_client_core(receive_timeout_in_seconds=3, message_expiry_in_seconds=10)

        message = {'request_id': 79, 'meta': {'yes': 'no'}, 'body': {'baz': 'qux'}}
        message['body'].update({'key-{}'.format(i): 'value-{}'.format(i) for i in range(200)})  # type: ignore

        serialized = MsgpackSerializer().dict_to_blob(message)

        mock_standard.return_value.get_connection.return_value.blpop.side_effect = [
            [True, (b'pysoa-redis/3//chunk-count:4;chunk-id:1;' + serialized[0:1000])],
            [True, (b'pysoa-redis/3//chunk-count:4;chunk-id:2;' + serialized[1000:2000])],
            [True, (b'pysoa-redis/3//chunk-count:4;chunk-id:4;' + serialized[2000:3000])],
            [True, (b'pysoa-redis/3//chunk-count:4;chunk-id:5;' + serialized[3000:])],
        ]

        with pytest.raises(InvalidMessageError) as error_context:
            core.receive_message('test_receive_chunking_fails_on_client_subsequent_chunk_count_differs')

        assert 'incorrect chunk ID' in error_context.value.args[0]

    @pytest.mark.parametrize(
        ('version', ),
        (
            (ProtocolVersion.VERSION_1, ),
            (ProtocolVersion.VERSION_2, ),
        ),
    )
    @mock.patch('pysoa.common.transport.redis_gateway.core.StandardRedisClient')
    def test_send_chunking_fails_if_client_does_not_support(self, mock_standard, version):
        core = self._get_server_core(
            chunk_messages_larger_than_bytes=102400,
            maximum_message_size_in_bytes=102400 * 6,
        )

        meta = {'protocol_version': version} if version else {}
        body = {'test': ['payload%i' % i for i in range(10000, 30000)]}  # 2.5 chunks needed

        with pytest.raises(MessageTooLarge) as error_context:
            core.send_message('test_send_chunking_fails_if_client_does_not_support', 103, meta, body)

        assert 'client does not support chunking' in error_context.value.args[0]

        assert not mock_standard.return_value.send_message_to_queue.called

    @mock.patch('pysoa.common.transport.redis_gateway.core.StandardRedisClient')
    def test_send_chunking_works_three_chunks(self, mock_standard):
        core = self._get_server_core(
            chunk_messages_larger_than_bytes=102400,
            maximum_message_size_in_bytes=102400 * 6,
        )

        meta = {'protocol_version': ProtocolVersion.VERSION_3}
        body = {'test': ['payload%i' % i for i in range(10000, 30000)]}  # 2.5 chunks needed

        core.send_message('test_send_chunking_works_three_chunks', 103, meta, body)

        assert mock_standard.return_value.send_message_to_queue.call_count == 3

        starts_with = b'pysoa-redis/3//content-type:application/msgpack;chunk-count:3;chunk-id:'
        starts_with_length = len(starts_with) + 2

        payload = b''

        _, kwargs = mock_standard.return_value.send_message_to_queue.call_args_list[0]
        assert kwargs['message'].startswith(starts_with + b'1;')
        payload += kwargs['message'][starts_with_length:]

        _, kwargs = mock_standard.return_value.send_message_to_queue.call_args_list[1]
        assert kwargs['message'].startswith(starts_with + b'2;')
        payload += kwargs['message'][starts_with_length:]

        _, kwargs = mock_standard.return_value.send_message_to_queue.call_args_list[2]
        assert kwargs['message'].startswith(starts_with + b'3;')
        payload += kwargs['message'][starts_with_length:]

        deserialized = MsgpackSerializer().blob_to_dict(payload)
        assert deserialized['request_id'] == 103
        assert '__expiry__' in deserialized['meta']
        assert len(deserialized['meta']) == 1
        assert deserialized['body'] == body

    @mock.patch('pysoa.common.transport.redis_gateway.core.StandardRedisClient')
    def test_send_chunking_works_four_chunks(self, mock_standard):
        core = self._get_server_core(
            chunk_messages_larger_than_bytes=125000,
            maximum_message_size_in_bytes=125000 * 6,
        )

        meta = {'protocol_version': ProtocolVersion.VERSION_3, 'serializer': JSONSerializer()}
        body = {'test': ['payload%i' % i for i in range(10000, 40000)]}  # 3.8 chunks needed

        core.send_message('test_send_chunking_works_four_chunks', 115, meta, body)

        assert mock_standard.return_value.send_message_to_queue.call_count == 4

        starts_with = b'pysoa-redis/3//content-type:application/json;chunk-count:4;chunk-id:'
        starts_with_length = len(starts_with) + 2

        payload = b''

        _, kwargs = mock_standard.return_value.send_message_to_queue.call_args_list[0]
        assert kwargs['message'].startswith(starts_with + b'1;')
        payload += kwargs['message'][starts_with_length:]

        _, kwargs = mock_standard.return_value.send_message_to_queue.call_args_list[1]
        assert kwargs['message'].startswith(starts_with + b'2;')
        payload += kwargs['message'][starts_with_length:]

        _, kwargs = mock_standard.return_value.send_message_to_queue.call_args_list[2]
        assert kwargs['message'].startswith(starts_with + b'3;')
        payload += kwargs['message'][starts_with_length:]

        _, kwargs = mock_standard.return_value.send_message_to_queue.call_args_list[3]
        assert kwargs['message'].startswith(starts_with + b'4;')
        payload += kwargs['message'][starts_with_length:]

        deserialized = JSONSerializer().blob_to_dict(payload)
        assert deserialized['request_id'] == 115
        assert '__expiry__' in deserialized['meta']
        assert len(deserialized['meta']) == 1
        assert deserialized['body'] == body

    @mock.patch('pysoa.common.transport.redis_gateway.core.StandardRedisClient')
    def test_send_chunking_works_five_chunks(self, mock_standard):
        core = self._get_server_core(
            chunk_messages_larger_than_bytes=111111,
            maximum_message_size_in_bytes=111111 * 6,
        )

        meta = {'protocol_version': ProtocolVersion.VERSION_3}
        body = {'test': ['payload%i' % i for i in range(10000, 51000)]}  # 4.1 chunks needed

        core.send_message('test_send_chunking_works_five_chunks', 122, meta, body)

        assert mock_standard.return_value.send_message_to_queue.call_count == 5

        starts_with = b'pysoa-redis/3//content-type:application/msgpack;chunk-count:5;chunk-id:'
        starts_with_length = len(starts_with) + 2

        payload = b''

        _, kwargs = mock_standard.return_value.send_message_to_queue.call_args_list[0]
        assert kwargs['message'].startswith(starts_with + b'1;')
        payload += kwargs['message'][starts_with_length:]

        _, kwargs = mock_standard.return_value.send_message_to_queue.call_args_list[1]
        assert kwargs['message'].startswith(starts_with + b'2;')
        payload += kwargs['message'][starts_with_length:]

        _, kwargs = mock_standard.return_value.send_message_to_queue.call_args_list[2]
        assert kwargs['message'].startswith(starts_with + b'3;')
        payload += kwargs['message'][starts_with_length:]

        _, kwargs = mock_standard.return_value.send_message_to_queue.call_args_list[3]
        assert kwargs['message'].startswith(starts_with + b'4;')
        payload += kwargs['message'][starts_with_length:]

        _, kwargs = mock_standard.return_value.send_message_to_queue.call_args_list[4]
        assert kwargs['message'].startswith(starts_with + b'5;')
        payload += kwargs['message'][starts_with_length:]

        deserialized = MsgpackSerializer().blob_to_dict(payload)
        assert deserialized['request_id'] == 122
        assert '__expiry__' in deserialized['meta']
        assert len(deserialized['meta']) == 1
        assert deserialized['body'] == body

    @mock.patch('pysoa.common.transport.redis_gateway.core.StandardRedisClient')
    def test_send_chunking_can_still_hit_too_large_error(self, mock_standard):
        core = self._get_server_core(
            chunk_messages_larger_than_bytes=111111,
            maximum_message_size_in_bytes=111111 * 6,
        )

        meta = {}  # type: Dict[six.text_type, Any]
        body = {'test': ['payload%i' % i for i in range(10000, 75000)]}  # > 111111 * 6

        with pytest.raises(MessageTooLarge) as error_context:
            core.send_message('test_send_chunking_can_still_hit_too_large_error', 115, meta, body)

        assert 'exceeds maximum message size' in error_context.value.args[0]

        assert not mock_standard.return_value.send_message_to_queue.called

    @mock.patch('pysoa.common.transport.redis_gateway.core.StandardRedisClient')
    def test_send_chunking_works_round_trip_three_chunks(self, mock_standard):
        server_core = self._get_server_core(
            chunk_messages_larger_than_bytes=102400,
            maximum_message_size_in_bytes=102400 * 6,
        )
        client_core = self._get_client_core()

        meta = {'protocol_version': ProtocolVersion.VERSION_3}
        body = {'test': ['payload%i' % i for i in range(10000, 30000)]}  # 2.5 chunks needed

        server_core.send_message('test_send_chunking_works_round_trip_three_chunks', 103, meta, body)

        assert mock_standard.return_value.send_message_to_queue.call_count == 3

        mock_standard.return_value.get_connection.return_value.blpop.side_effect = [
            [True, (mock_standard.return_value.send_message_to_queue.call_args_list[0][1]['message'])],
            [True, (mock_standard.return_value.send_message_to_queue.call_args_list[1][1]['message'])],
            [True, (mock_standard.return_value.send_message_to_queue.call_args_list[2][1]['message'])],
        ]

        request_id, _, received_body = client_core.receive_message(
            'test_send_chunking_works_round_trip_three_chunks',
        )

        assert request_id == 103
        assert received_body == body

    @mock.patch('pysoa.common.transport.redis_gateway.core.StandardRedisClient')
    def test_send_chunking_works_round_trip_five_chunks(self, mock_standard):
        server_core = self._get_server_core(
            chunk_messages_larger_than_bytes=102400,
            maximum_message_size_in_bytes=102400 * 6,
        )
        client_core = self._get_client_core()

        meta = {'protocol_version': ProtocolVersion.VERSION_3}
        body = {'test': ['payload%i' % i for i in range(10000, 48000)]}  # 4.1 chunks needed

        server_core.send_message('test_send_chunking_works_round_trip_five_chunks', 103, meta, body)

        assert mock_standard.return_value.send_message_to_queue.call_count == 5

        mock_standard.return_value.get_connection.return_value.blpop.side_effect = [
            [True, (mock_standard.return_value.send_message_to_queue.call_args_list[0][1]['message'])],
            [True, (mock_standard.return_value.send_message_to_queue.call_args_list[1][1]['message'])],
            [True, (mock_standard.return_value.send_message_to_queue.call_args_list[2][1]['message'])],
            [True, (mock_standard.return_value.send_message_to_queue.call_args_list[3][1]['message'])],
            [True, (mock_standard.return_value.send_message_to_queue.call_args_list[4][1]['message'])],
        ]

        request_id, _, received_body = client_core.receive_message(
            'test_send_chunking_works_round_trip_five_chunks',
        )

        assert request_id == 103
        assert received_body == body

    @mock.patch('pysoa.common.transport.redis_gateway.core.StandardRedisClient')
    def test_send_chunking_works_round_trip_edge_case_1(self, mock_standard):
        server_core = self._get_server_core(
            chunk_messages_larger_than_bytes=102400,
            maximum_message_size_in_bytes=102400 * 6,
        )
        client_core = self._get_client_core()

        meta = {}  # type: Dict[six.text_type, Any]
        body = {'test': [
            '        h  e  l  l  o ,  w  o  r  l  d  #  {}        '.format(i)
            for i in range(10000, 18000)
        ]}

        server_core.send_message('test_send_chunking_works_round_trip_edge_case_1', 911461, meta, body)

        assert mock_standard.return_value.send_message_to_queue.call_count == 5

        mock_standard.return_value.get_connection.return_value.blpop.side_effect = [
            [True, item[1]['message']]
            for item in mock_standard.return_value.send_message_to_queue.call_args_list
        ]

        request_id, _, received_body = client_core.receive_message(
            'test_send_chunking_works_round_trip_edge_case_1',
        )

        assert request_id == 911461
        assert received_body == body

    @pytest.mark.parametrize(
        ('version', ),
        (
            (ProtocolVersion.VERSION_1, ),
            (ProtocolVersion.VERSION_2, ),
            (ProtocolVersion.VERSION_3, ),
            (None, ),
        ),
    )
    @mock.patch('pysoa.common.transport.redis_gateway.core.StandardRedisClient')
    def test_client_protocol_version_configuration(self, mock_standard, version):
        server_core = self._get_server_core()
        if version:
            client_core = self._get_client_core(protocol_version=version)
        else:
            client_core = self._get_client_core()

        body = {'foo': 'bar', 'baz': 'qux', 'hello': 'world', 'goodbye': 'friends'}

        client_core.send_message('test_client_protocol_version_configuration', 91, {}, body)

        assert mock_standard.return_value.send_message_to_queue.call_count == 1

        mock_standard.return_value.get_connection.return_value.blpop.side_effect = [
            [True, (mock_standard.return_value.send_message_to_queue.call_args_list[0][1]['message'])],
        ]

        request_id, meta, received_body = server_core.receive_message('test_client_protocol_version_configuration')

        assert request_id == 91
        assert 'protocol_version' in meta
        assert meta['protocol_version'] == (version if version else ProtocolVersion.VERSION_3)  # 3 is the default
        assert received_body == body
