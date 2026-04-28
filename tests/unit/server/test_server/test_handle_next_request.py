from __future__ import (
    absolute_import,
    unicode_literals,
)

import multiprocessing
import time
from typing import Mapping
from unittest import TestCase

from conformity import fields
import six

from pysoa.common.transport.base import ServerTransport
from pysoa.common.transport.errors import MessageReceiveTimeout
from pysoa.server.server import Server
from pysoa.server.types import ActionType
from pysoa.test import factories
from pysoa.test.compatibility import mock


class HandleNextRequestServer(Server):
    """
    Stub server to test against.
    """
    service_name = 'test_service'
    action_class_map = {}  # type: Mapping[six.text_type, ActionType]


@fields.ClassConfigurationSchema.provider(fields.Dictionary({}))
class SimplePassthroughServerTransport(ServerTransport):
    def set_request(self, request):
        self._request = request

    def receive_request_message(self):
        return (0, {}, self._request)

    def send_response_message(self, request_id, meta, body):
        self._response = body

    def get_response(self):
        return self._response


@fields.ClassConfigurationSchema.provider(fields.Dictionary({}))
class TimeoutServerTransport(ServerTransport):
    """Transport that always raises MessageReceiveTimeout (simulates an idle server)."""

    def receive_request_message(self):
        raise MessageReceiveTimeout()

    def send_response_message(self, request_id, meta, body):
        pass


class TestProcessNextRequests(TestCase):
    def test_emtpy_request_returns_job_response_error(self):
        """
        Test that server can handle an emtpy job missing top level elements without throwing exceptions
        """
        settings = factories.ServerSettingsFactory()
        server = HandleNextRequestServer(settings=settings)
        server.transport = SimplePassthroughServerTransport(server.service_name)

        server.transport.set_request({})
        server.handle_next_request()
        response = server.transport.get_response()

        # Make sure we got an error
        self.assertTrue('errors' in response)
        errors = response['errors']
        self.assertEqual(len(errors), 3)
        self.assertEqual({'actions', 'control', 'context'}, set([e.get('field', None) for e in errors]))


# ---------------------------------------------------------------------------
# Tests for _ping_parent and the ping calls inside handle_next_request
# ---------------------------------------------------------------------------


class TestServerPingParent(TestCase):
    """Tests for the child-process heartbeat mechanism (_ping_parent)."""

    def _make_server(self):
        settings = factories.ServerSettingsFactory()
        return HandleNextRequestServer(settings=settings)

    def _make_server_with_ping(self):
        """Return a server wired up with a real shared-memory ping timestamp."""
        server = self._make_server()
        server._ping_timestamp = multiprocessing.Value('d', 0.0)
        return server

    # ------------------------------------------------------------------
    # _ping_parent unit tests
    # ------------------------------------------------------------------

    def test_ping_parent_noop_when_no_shared_memory(self):
        """_ping_parent must not raise when the server is not a forked child."""
        server = self._make_server()
        self.assertIsNone(server._ping_timestamp)
        # Should complete without error.
        server._ping_parent()

    def test_ping_parent_updates_timestamp(self):
        """_ping_parent writes a fresh monotonic timestamp."""
        server = self._make_server_with_ping()

        before = time.monotonic()
        server._ping_parent()
        after = time.monotonic()

        self.assertGreaterEqual(server._ping_timestamp.value, before)
        self.assertLessEqual(server._ping_timestamp.value, after)

    def test_ping_parent_updates_timestamp_on_each_call(self):
        """Each _ping_parent call must write a monotonically non-decreasing timestamp."""
        server = self._make_server_with_ping()

        server._ping_parent()
        ts1 = server._ping_timestamp.value

        server._ping_parent()
        ts2 = server._ping_timestamp.value

        self.assertGreaterEqual(ts2, ts1)

    # ------------------------------------------------------------------
    # Ping calls inside handle_next_request
    # ------------------------------------------------------------------

    def test_ping_on_receive_timeout(self):
        """handle_next_request pings the parent on MessageReceiveTimeout (idle)."""
        server = self._make_server_with_ping()
        server.transport = TimeoutServerTransport(server.service_name)

        before = time.monotonic()
        server.handle_next_request()

        self.assertGreaterEqual(server._ping_timestamp.value, before,
                                'Server should have updated ping timestamp on idle timeout')

    def test_ping_when_request_received(self):
        """handle_next_request pings the parent after a request is dequeued."""
        server = self._make_server_with_ping()
        server.transport = SimplePassthroughServerTransport(server.service_name)
        server.transport.set_request({})

        ping_calls = []
        original_ping = server._ping_parent

        def _capture_ping():
            ping_calls.append(time.monotonic())
            original_ping()

        with mock.patch.object(server, '_ping_parent', side_effect=_capture_ping):
            server.handle_next_request()

        # At least two pings: one on receive, one in the finally block.
        self.assertGreaterEqual(len(ping_calls), 2,
                                'Expected _ping_parent to be called at least twice per request')

    def test_ping_after_request_completes(self):
        """handle_next_request pings the parent in the finally block after the request finishes."""
        server = self._make_server_with_ping()
        server.transport = SimplePassthroughServerTransport(server.service_name)
        server.transport.set_request({})

        before = time.monotonic()
        server.handle_next_request()

        self.assertGreaterEqual(server._ping_timestamp.value, before,
                                'Server should have updated ping timestamp after the request finished')

    def test_ping_after_request_even_on_exception(self):
        """The finally-block ping must fire even when request processing raises an exception."""
        server = self._make_server_with_ping()
        server.transport = SimplePassthroughServerTransport(server.service_name)
        server.transport.set_request({})

        before = time.monotonic()
        with mock.patch.object(server, 'process_job', side_effect=RuntimeError('boom')):
            try:
                server.handle_next_request()
            except RuntimeError:
                pass

        self.assertGreaterEqual(server._ping_timestamp.value, before,
                                'Server must ping even when an exception escapes handle_next_request')


# ---------------------------------------------------------------------------
# Tests for the receive_timeout vs ping_timeout validation
# ---------------------------------------------------------------------------


class TestReceiveTimeoutValidation(TestCase):
    """
    Verify that _validate_receive_timeout_vs_ping_timeout raises ValueError when
    receive_timeout_in_seconds exceeds half the ping-timeout, which would make the
    watchdog unreliable.

    We test the extracted classmethod directly to avoid mocking Server.main's
    heavy infrastructure (settings loading, logging, server instantiation).
    """

    def _make_settings(self, receive_timeout):
        """Return a minimal fake settings mapping with the given transport receive timeout."""
        kwargs = {} if receive_timeout is None else {'receive_timeout_in_seconds': receive_timeout}
        return {'transport': {'object': SimplePassthroughServerTransport, 'kwargs': kwargs}}

    def test_raises_when_receive_timeout_exceeds_half_ping_timeout(self):
        """receive_timeout_in_seconds > ping_timeout/2 must raise ValueError."""
        settings = self._make_settings(receive_timeout=8)
        with self.assertRaises(ValueError) as ctx:
            HandleNextRequestServer._validate_receive_timeout_vs_ping_timeout(settings, ping_timeout=10)
        self.assertIn('receive_timeout_in_seconds', str(ctx.exception))
        self.assertIn('ping-timeout', str(ctx.exception))

    def test_does_not_raise_when_receive_timeout_equals_half_ping_timeout(self):
        """receive_timeout_in_seconds == ping_timeout/2 is exactly on the boundary and must not raise."""
        settings = self._make_settings(receive_timeout=5)
        HandleNextRequestServer._validate_receive_timeout_vs_ping_timeout(settings, ping_timeout=10)

    def test_does_not_raise_when_receive_timeout_is_below_half_ping_timeout(self):
        """receive_timeout_in_seconds < ping_timeout/2 must not raise."""
        settings = self._make_settings(receive_timeout=3)
        HandleNextRequestServer._validate_receive_timeout_vs_ping_timeout(settings, ping_timeout=10)

    def test_uses_redis_default_when_timeout_not_in_kwargs(self):
        """When receive_timeout_in_seconds is absent from kwargs the Redis default (5) is used."""
        # The Redis default is 5; with ping_timeout=8 the check is 5 > 4 → should raise.
        settings = self._make_settings(receive_timeout=None)
        # Inject a fake Redis transport to trigger the default-fallback branch.
        from pysoa.common.transport.redis_gateway.server import RedisServerTransport
        settings['transport']['object'] = RedisServerTransport
        with self.assertRaises(ValueError):
            HandleNextRequestServer._validate_receive_timeout_vs_ping_timeout(settings, ping_timeout=8)

    def test_skips_check_for_non_redis_transport_without_timeout(self):
        """Non-Redis transports that don't expose receive_timeout_in_seconds are silently skipped."""
        settings = self._make_settings(receive_timeout=None)
        # SimplePassthroughServerTransport is not a Redis transport; import should fail gracefully.
        with mock.patch('pysoa.server.server.Server._validate_receive_timeout_vs_ping_timeout',
                        wraps=HandleNextRequestServer._validate_receive_timeout_vs_ping_timeout):
            # Patch the Redis import to simulate a non-Redis environment.
            with mock.patch.dict('sys.modules', {'pysoa.common.transport.redis_gateway.core': None}):
                # Should not raise even though ping_timeout=1 would normally flag any timeout > 0.5.
                HandleNextRequestServer._validate_receive_timeout_vs_ping_timeout(settings, ping_timeout=1)
