from __future__ import unicode_literals

from asgi_redis import RedisChannelLayer
import mock
import pytest

from pysoa.common.metrics import NoOpMetricsRecorder
from pysoa.common.transport.asgi import (
    ASGIClientTransport,
    ASGIServerTransport,
)
from pysoa.common.transport.asgi.constants import (
    ASGI_CHANNEL_TYPE_LOCAL,
    ASGI_CHANNEL_TYPE_REDIS,
)
from pysoa.common.transport.asgi.core import ASGITransportCore
from pysoa.common.transport.exceptions import (
    MessageTooLarge,
    MessageReceiveError,
    MessageSendError,
    InvalidMessageError,
)


class TestASGITransportCore(object):

    @mock.patch('pysoa.common.transport.asgi.core.RedisChannelLayer.send', side_effect=RedisChannelLayer.ChannelFull)
    def test_send_message_exception(self, _):
        """The transport should raise a MessageSendError if the channel layer is full after sufficient retries"""
        core = ASGITransportCore(asgi_channel_type=ASGI_CHANNEL_TYPE_REDIS, channel_full_retries=0)
        with pytest.raises(MessageSendError):
            core.send_message('channel1234', 1, {}, 'this is an important message')

    @mock.patch('pysoa.common.transport.asgi.core.RedisChannelLayer.receive', side_effect=Exception)
    def test_receive_message_exception(self, _):
        """The transport should raise a MessageReceiveError if the channel layer raises any exception"""
        core = ASGITransportCore(asgi_channel_type=ASGI_CHANNEL_TYPE_REDIS)
        with pytest.raises(MessageReceiveError):
            core.receive_message('channel1234')

    @mock.patch('pysoa.common.transport.asgi.core.RedisChannelLayer')
    def test_send_message_too_large(self, _):
        core = ASGITransportCore(asgi_channel_type=ASGI_CHANNEL_TYPE_REDIS)
        body = 'a' * (core.BODY_MAX_SIZE + 1)
        with pytest.raises(MessageTooLarge):
            core.send_message('channel1234', 1, {}, body)


class TestASGIClientTransport(object):

    @mock.patch('pysoa.common.transport.asgi.core.RedisChannelLayer')
    def test_send_request_runs_without_errors(self, _):
        """Calling send_request_message with a valid request should produce no exceptions."""
        client_transport = ASGIClientTransport(
            'test',
            NoOpMetricsRecorder(),
            asgi_channel_type=ASGI_CHANNEL_TYPE_REDIS,
        )
        message_body = 'this is an important message'
        meta = {'foo': 1}
        request_id = 1
        client_transport.send_request_message(request_id, meta, message_body)

    def test_valid_response(self):
        """The transport should pass ID, meta and body fields back to the caller"""
        response_message = {
            'meta': {'reply_to': 'clientID1234'},
            'request_id': 1,
            'body': 'this is an important message',
        }

        with mock.patch('pysoa.common.transport.asgi.core.RedisChannelLayer.receive',
                        return_value=('channelName', response_message)):
            client_transport = ASGIClientTransport(
                'test',
                NoOpMetricsRecorder(),
                asgi_channel_type=ASGI_CHANNEL_TYPE_REDIS,
            )
            # We don't get anything back unless the outstanding response counter is > 0
            request_id, meta, message_body = client_transport.receive_response_message()
            assert request_id is meta is message_body is None
            client_transport.requests_outstanding = 1
            request_id, meta, message_body = client_transport.receive_response_message()
            assert request_id == response_message['request_id']
            assert meta == response_message['meta']
            assert message_body == response_message['body']

    def test_response_id_required(self):
        """The transport should raise an exception if it receives a response without an ID"""
        response_message = {
            'meta': {'reply_to': 'clientID1234'},
            'body': 'this is an important message',
        }

        with mock.patch('pysoa.common.transport.asgi.core.RedisChannelLayer.receive',
                        return_value=('channelName', response_message)):
            client_transport = ASGIClientTransport(
                'test',
                NoOpMetricsRecorder(),
                asgi_channel_type=ASGI_CHANNEL_TYPE_REDIS,
            )
            client_transport.requests_outstanding = 1
            with pytest.raises(InvalidMessageError):
                client_transport.receive_response_message()

    def test_response_field_defaults(self):
        """The transport should return sane defaults if the meta or body fields are missing from a response"""
        response_message = {'request_id': 1}

        with mock.patch('pysoa.common.transport.asgi.core.RedisChannelLayer.receive',
                        return_value=('channelName', response_message)):
            client_transport = ASGIClientTransport(
                'test',
                NoOpMetricsRecorder(),
                asgi_channel_type=ASGI_CHANNEL_TYPE_REDIS,
            )
            client_transport.requests_outstanding = 1
            _, meta, message_body = client_transport.receive_response_message()
            assert meta == {}
            assert message_body is None


class TestASGIServerTransport(object):

    @mock.patch('pysoa.common.transport.asgi.core.RedisChannelLayer')
    def test_response_id_required(self, _):
        """The transport should raise an exception rather than send a response with no ID"""
        client = ASGIServerTransport('test', NoOpMetricsRecorder(), asgi_channel_type=ASGI_CHANNEL_TYPE_REDIS)
        message_body = 'this is an important message'
        meta = {'reply_to': 'channel1234'}
        with pytest.raises(InvalidMessageError):
            client.send_response_message(None, meta, message_body)

    @mock.patch('pysoa.common.transport.asgi.core.RedisChannelLayer')
    def test_response_reply_to_required(self, _):
        """The transport should raise an exception if send_response_message is called without a reply channel"""
        client = ASGIServerTransport('test', NoOpMetricsRecorder(), asgi_channel_type=ASGI_CHANNEL_TYPE_REDIS)
        message_body = 'this is an important message'
        meta = {}
        with pytest.raises(InvalidMessageError):
            client.send_response_message(1, meta, message_body)

    def test_request_defaults(self):
        """
        The transport should return sane defaults if the meta or body fields are missing from a request, including
        a valid channel name for meta['reply_to'].
        """
        request_message = {'request_id': 1}
        with mock.patch('pysoa.common.transport.asgi.core.RedisChannelLayer.receive',
                        return_value=('channelName', request_message)):
            server_transport = ASGIServerTransport(
                'test',
                NoOpMetricsRecorder(),
                asgi_channel_type=ASGI_CHANNEL_TYPE_REDIS,
            )
            request_id, meta, message_body = server_transport.receive_request_message()
            assert request_id == request_message['request_id']
            assert meta == {'reply_to': server_transport.receive_channel_name}
            assert message_body is None


class TestASGITransport(object):

    def test_send_receive_local(self):
        """The transport should successfully transmit a valid message over a local transport"""
        client_transport = ASGIClientTransport('test', NoOpMetricsRecorder(), asgi_channel_type=ASGI_CHANNEL_TYPE_LOCAL)
        server_transport = ASGIServerTransport('test', NoOpMetricsRecorder(), asgi_channel_type=ASGI_CHANNEL_TYPE_LOCAL)
        client_message_body = 'this is an important message'
        client_meta = {'foo': 1}
        client_request_id = 1
        client_transport.send_request_message(client_request_id, client_meta, client_message_body)
        server_request_id, meta, server_message_body = server_transport.receive_request_message()
        assert client_request_id == server_request_id
        assert client_message_body == server_message_body
        assert client_meta == meta

    def test_send_receive_redis(self):
        """The transport should successfully transmit a valid message over a redis transport"""
        class Nonlocal(object):
            message = None

        def _mock_send(_, message):
            Nonlocal.message = message

        client_request_id = 1
        client_request_meta = {}
        client_request_body = 'this is an important message'
        with mock.patch('pysoa.common.transport.asgi.core.RedisChannelLayer.send', side_effect=_mock_send):
            with mock.patch('pysoa.common.transport.asgi.core.RedisChannelLayer.receive') as mock_receive:
                client_transport = ASGIClientTransport(
                    'test',
                    NoOpMetricsRecorder(),
                    asgi_channel_type=ASGI_CHANNEL_TYPE_REDIS,
                )
                server_transport = ASGIServerTransport(
                    'test',
                    NoOpMetricsRecorder(),
                    asgi_channel_type=ASGI_CHANNEL_TYPE_REDIS,
                )
                client_transport.send_request_message(client_request_id, client_request_meta, client_request_body)
                mock_receive.return_value = ('some_channel', Nonlocal.message)
                server_request_id, server_request_meta, server_request_body = server_transport.receive_request_message()
                assert client_request_id == server_request_id
                assert client_request_meta == server_request_meta
                assert client_request_body == server_request_body
