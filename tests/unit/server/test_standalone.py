from __future__ import (
    absolute_import,
    unicode_literals,
)

import collections
import datetime
import multiprocessing
import os
import signal
import sys
import threading
import time
from types import ModuleType
from typing import Optional
import unittest

import freezegun

from pysoa.test.compatibility import mock


standalone = None  # type: Optional[ModuleType]


def setup_module(_):
    """
    We want this setup to run before any of the tests in this module, to ensure that the `standalone` module gets
    imported.
    """
    global standalone

    with mock.patch('pysoa.utils.get_python_interpreter_arguments') as mock_get_args:
        prev_path_0 = sys.path[0]
        mock_get_args.return_value = ['python', '/path/to/module.py']

        # Force this to bad
        sys.path[0] = '/path/to/module.py'
        try:
            from pysoa.server import standalone  # type: ignore
            assert False, 'Should not have been able to import standalone; should have received SystemExit'
        except SystemExit as e:
            # This first bit is actually a test; it confirms that the double-import trap is triggered
            assert e.args[0] == 99
        finally:
            # ...and then we put this back so that we haven't caused any problems.
            sys.path[0] = prev_path_0

        # Now we actually import the module, but we have to make sure the double-import trap isn't triggered before we
        # do. Running `pytest` or `setup.py` looks to `standalone` like there is a problem, so we temporarily remove
        # `pytest` or `setup.py` from the first path item if it's Py<3.7, change return value of mock for 3.7+...
        if sys.version_info < (3, 7):
            sys.path[0] = ''
        else:
            mock_get_args.return_value = ['python', '-m', 'service_module']
        try:
            from pysoa.server import standalone  # type: ignore
        except SystemExit as e:
            assert False, 'Expected import to succeed, instead got SystemExit with code {}'.format(e.args[0])
        finally:
            # ...and then we put this back so that we haven't caused any problems.
            sys.path[0] = prev_path_0


class TestSimpleMain(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(standalone, 'Something went wrong with setup_module or the import')
        self.prev_argv = sys.argv

    def tearDown(self):
        sys.argv = self.prev_argv

    def test_no_arguments_explicit_no_fork(self):
        """With --fork 0, the server runs directly in the current process (no subprocess)."""
        server_getter = mock.MagicMock()

        sys.argv = ['/path/to/example_service/standalone.py', '--fork', '0']

        standalone.simple_main(server_getter)  # type: ignore

        server_getter.assert_called_once_with()
        server_getter.return_value.main.assert_called_once_with()

    @mock.patch('pysoa.server.autoreload.get_reloader')
    def test_only_file_watcher_argument_no_values(self, mock_get_reloader):
        server_getter = mock.MagicMock()

        sys.argv = ['/path/to/example_service/standalone.py', '--use-file-watcher']

        standalone.simple_main(server_getter)  # type: ignore

        server_getter.assert_called_once_with()
        self.assertFalse(server_getter.return_value.main.called)

        assert mock_get_reloader.call_count == 1
        assert mock_get_reloader.call_args_list[0][0][0] in ('', 'pytest', 'pytest.__main__', 'coverage')
        assert mock_get_reloader.call_args_list[0][0][1] is None
        assert mock_get_reloader.call_args_list[0][1]['signal_forks'] is False

        self.assertEqual(1, mock_get_reloader.return_value.main.call_count)
        self.assertEqual(
            server_getter.return_value,
            mock_get_reloader.return_value.main.call_args_list[0][0][1][1],
        )

    @mock.patch('pysoa.server.autoreload.get_reloader')
    def test_only_file_watcher_argument_some_values(self, mock_get_reloader):
        server_getter = mock.MagicMock()

        sys.argv = ['/path/to/example_service/standalone.py', '--use-file-watcher', 'example,pysoa,conformity']

        standalone.simple_main(server_getter)  # type: ignore

        server_getter.assert_called_once_with()
        self.assertFalse(server_getter.return_value.main.called)

        assert mock_get_reloader.call_count == 1
        assert mock_get_reloader.call_args_list[0][0][0] in ('', 'pytest', 'pytest.__main__', 'coverage')
        assert mock_get_reloader.call_args_list[0][0][1] == ['example', 'pysoa', 'conformity']
        assert mock_get_reloader.call_args_list[0][1]['signal_forks'] is False

        self.assertEqual(1, mock_get_reloader.return_value.main.call_count)
        self.assertEqual(1, mock_get_reloader.return_value.main.call_args_list[0][0][1][0].fork_processes)
        self.assertEqual(
            server_getter.return_value,
            mock_get_reloader.return_value.main.call_args_list[0][0][1][1],
        )

    @mock.patch('pysoa.server.autoreload.get_reloader')
    def test_file_watcher_argument_no_values_with_forking(self, mock_get_reloader):
        server_getter = mock.MagicMock()

        sys.argv = ['/path/to/example_service/standalone.py', '--use-file-watcher', '-f', '5']

        standalone.simple_main(server_getter)  # type: ignore

        server_getter.assert_called_once_with()
        self.assertFalse(server_getter.return_value.main.called)

        assert mock_get_reloader.call_count == 1
        assert mock_get_reloader.call_args_list[0][0][0] in ('', 'pytest', 'pytest.__main__', 'coverage')
        assert mock_get_reloader.call_args_list[0][0][1] is None
        assert mock_get_reloader.call_args_list[0][1]['signal_forks'] is True

        self.assertEqual(1, mock_get_reloader.return_value.main.call_count)
        self.assertEqual(5, mock_get_reloader.return_value.main.call_args_list[0][0][1][0].fork_processes)
        self.assertEqual(
            server_getter.return_value,
            mock_get_reloader.return_value.main.call_args_list[0][0][1][1],
        )

    @mock.patch('pysoa.server.autoreload.get_reloader')
    def test_file_watcher_argument_some_values_with_forking(self, mock_get_reloader):
        server_getter = mock.MagicMock()

        sys.argv = ['/path/to/example_service/standalone.py', '--use-file-watcher', 'pysoa', '-f', '5']

        standalone.simple_main(server_getter)  # type: ignore

        server_getter.assert_called_once_with()
        self.assertFalse(server_getter.return_value.main.called)

        assert mock_get_reloader.call_count == 1
        assert mock_get_reloader.call_args_list[0][0][0] in ('', 'pytest', 'pytest.__main__', 'coverage')
        assert mock_get_reloader.call_args_list[0][0][1] == ['pysoa']
        assert mock_get_reloader.call_args_list[0][1]['signal_forks'] is True

        self.assertEqual(1, mock_get_reloader.return_value.main.call_count)
        self.assertEqual(5, mock_get_reloader.return_value.main.call_args_list[0][0][1][0].fork_processes)
        self.assertEqual(
            server_getter.return_value,
            mock_get_reloader.return_value.main.call_args_list[0][0][1][1],
        )

    @mock.patch('multiprocessing.Process')
    @mock.patch('multiprocessing.cpu_count')
    def test_only_forking_not_limited(self, mock_cpu_count, mock_process):
        server_getter = mock.MagicMock()

        mock_cpu_count.return_value = 2

        sys.argv = ['/path/to/example_service/standalone.py', '-f', '10', '--no-respawn']

        prev_sigint = prev_sigterm = prev_sighup = None
        try:
            prev_sigint = signal.signal(signal.SIGINT, signal.SIG_IGN)
            prev_sigterm = signal.signal(signal.SIGTERM, signal.SIG_IGN)
            prev_sighup = signal.signal(signal.SIGHUP, signal.SIG_IGN)

            processes = [mock.MagicMock() for _ in range(0, 10)]
            # Each mock process must report is_alive()=False so the polling loop can exit.
            for p in processes:
                p.is_alive.return_value = False
            mock_process.side_effect = processes

            standalone.simple_main(server_getter)  # type: ignore

            server_getter.assert_called_once_with()
            self.assertFalse(server_getter.return_value.main.called)

            self.assertEqual(10, mock_process.call_count)

            found_ids = [0 for _ in range(0, 11)]
            i = 1
            for call in mock_process.call_args_list:
                # args[0] is still the forked_process_id; additional elements are the
                # shared-memory ping cells appended by _ProcessMonitor.__init__.
                id = call[1]['args'][0]
                self.assertEqual(server_getter.return_value.main, call[1]['target'])
                self.assertEqual('pysoa-worker-{}'.format(id), call[1]['name'])
                assert found_ids[id] == 0, "Already seen process id"
                found_ids[id] = i
                i += 1

            for i, process in enumerate(processes):
                self.assertTrue(process.start.called, 'Process {} was not started'.format(i))
                self.assertTrue(process.join.called, 'Process {} was not joined'.format(i))
                self.assertFalse(process.terminate.called, 'Process {} should not have been terminated'.format(i))

            for i, process in enumerate(processes):
                assert process.terminate.called is False
        finally:
            if prev_sigint is not None:
                signal.signal(signal.SIGINT, prev_sigint or signal.SIG_IGN)
            if prev_sigterm is not None:
                signal.signal(signal.SIGTERM, prev_sigterm or signal.SIG_IGN)
            if prev_sighup is not None:
                signal.signal(signal.SIGHUP, prev_sighup or signal.SIG_IGN)

    @mock.patch('multiprocessing.Process')
    @mock.patch('multiprocessing.cpu_count')
    def test_only_forking_limited(self, mock_cpu_count, mock_process):
        server_getter = mock.MagicMock()

        mock_cpu_count.return_value = 1

        sys.argv = ['/path/to/example_service/standalone.py', '-f', '10', '--no-respawn']

        prev_sigint = prev_sigterm = prev_sighup = None
        try:
            prev_sigint = signal.signal(signal.SIGINT, signal.SIG_IGN)
            prev_sigterm = signal.signal(signal.SIGTERM, signal.SIG_IGN)
            prev_sighup = signal.signal(signal.SIGHUP, signal.SIG_IGN)

            processes = [mock.MagicMock() for _ in range(0, 5)]
            for p in processes:
                p.is_alive.return_value = False
            mock_process.side_effect = processes

            standalone.simple_main(server_getter)  # type: ignore

            server_getter.assert_called_once_with()
            self.assertFalse(server_getter.return_value.main.called)

            self.assertEqual(5, mock_process.call_count)
            found_ids = [0 for _ in range(0, 6)]
            i = 1
            for call in mock_process.call_args_list:
                id = call[1]['args'][0]
                self.assertEqual(server_getter.return_value.main, call[1]['target'])
                self.assertEqual('pysoa-worker-{}'.format(id), call[1]['name'])
                assert found_ids[id] == 0, "Already seen process id"
                found_ids[id] = i
                i += 1

            for i, process in enumerate(processes):
                self.assertTrue(process.start.called, 'Process {} was not started'.format(i))
                self.assertTrue(process.join.called, 'Process {} was not joined'.format(i))
                self.assertFalse(process.terminate.called, 'Process {} should not have been terminated'.format(i))

            for i, process in enumerate(processes):
                assert process.terminate.called is False
        finally:
            if prev_sigint is not None:
                signal.signal(signal.SIGINT, prev_sigint or signal.SIG_IGN)
            if prev_sigterm is not None:
                signal.signal(signal.SIGTERM, prev_sigterm or signal.SIG_IGN)
            if prev_sighup is not None:
                signal.signal(signal.SIGHUP, prev_sighup or signal.SIG_IGN)

    class _MockProcess(object):
        def __init__(self, dying):
            self.start = mock.MagicMock()
            self.terminate = mock.MagicMock()
            self.join = mock.MagicMock()

            if not dying:
                def _join_se():
                    time.sleep(1)
                self.join.side_effect = _join_se

    @mock.patch('multiprocessing.Process')
    @mock.patch('multiprocessing.cpu_count')
    def test_forking_with_default_respawn(self, mock_cpu_count, mock_process):
        """
        Verifies respawn rate-limiting behaviour:

        * Worker 2 (quick-dying): crashes 3 times within 15 s → respawn stops after 4 total.
        * Worker 3 (slow-dying): crashes 8 times within 60 s → respawn stops after 9 total.
        * Worker 1 (living): stays alive until SIGTERM is sent; only 1 instance created.

        With the new polling model a process is considered dead when is_alive() returns
        False (not when join() returns). Time is advanced via freezegun ticks inside the
        constructor side-effect so that crash-rate deque checks see the right timestamps.
        """
        server_getter = mock.MagicMock()

        mock_cpu_count.return_value = 2

        sys.argv = ['/path/to/example_service/standalone.py', '-f', '3']

        prev_sigint = prev_sigterm = prev_sighup = None
        try:
            prev_sigint = signal.signal(signal.SIGINT, signal.SIG_IGN)
            prev_sigterm = signal.signal(signal.SIGTERM, signal.SIG_IGN)
            prev_sighup = signal.signal(signal.SIGHUP, signal.SIG_IGN)

            living_processes = []
            quick_dying_processes = []
            slow_dying_processes = []
            bad_processes = []

            # Shared flag: once the living worker fires SIGTERM, all living is_alive()
            # calls return False so every monitor thread can exit cleanly.
            living_should_die = False

            def patched_freeze_time():
                # TODO Until https://github.com/spulec/freezegun/issues/307 is fixed
                f = freezegun.freeze_time()
                f.ignore = tuple(set(f.ignore) - {'threading'})
                return f

            with patched_freeze_time() as frozen_time:
                def tick_six_se():
                    frozen_time.tick(datetime.timedelta(seconds=6))

                def se(target, name, args):
                    nonlocal living_should_die
                    process = mock.MagicMock()
                    # culprit[2][0] is the forked_process_id; additional elements are
                    # the shared-memory ping cells injected by _ProcessMonitor.__init__.
                    process.culprit = (target, name, args)
                    worker_id = args[0]

                    if worker_id == 1:
                        # Living worker: stays alive until SIGTERM fires.
                        living_processes.append(process)
                        if len(living_processes) > 1:
                            raise ValueError('Living worker spawned more than once!')

                        def signal_join(*a, **kw):
                            nonlocal living_should_die
                            os.kill(os.getpid(), signal.SIGTERM)
                            living_should_die = True
                            time.sleep(0.3)

                        process.join.side_effect = signal_join
                        process.is_alive.side_effect = lambda: not living_should_die

                        # Delay creation so quick- and slow-dying workers get a head start.
                        time.sleep(0.05)

                    elif worker_id == 2:
                        # Quick-dying: crashes immediately, hits 15-second rate limit.
                        quick_dying_processes.append(process)
                        process.is_alive.return_value = False  # dies on first poll

                    elif worker_id == 3:
                        # Slow-dying: each crash advances frozen time by 6 s; the 8-crash
                        # 60-second window fills before 60 s elapses (8 × 6 = 48 s < 60 s).
                        slow_dying_processes.append(process)
                        tick_six_se()  # advance time when the process is *created*
                        process.is_alive.return_value = False  # dies on first poll

                        # Slight delay to ensure quick-dying finishes first.
                        if len(slow_dying_processes) == 1:
                            time.sleep(0.02)

                    else:
                        bad_processes.append((target, name, args))
                        raise ValueError('Unexpected worker id {}'.format(worker_id))

                    return process

                mock_process.side_effect = se

                standalone.simple_main(server_getter)  # type: ignore

            server_getter.assert_called_once_with()
            assert server_getter.return_value.main.called is False

            assert len(bad_processes) == 0

            # 1 initial + 3 respawns before hitting 15-second crash limit.
            assert len(quick_dying_processes) == 4

            # 1 initial + 8 respawns before hitting 60-second crash limit.
            assert len(slow_dying_processes) == 9

            # Living worker is never respawned (it stays alive until shutdown).
            assert len(living_processes) == 1

            for p in living_processes:
                assert p.culprit[0] is server_getter.return_value.main
                assert p.culprit[1] == 'pysoa-worker-1'
                assert p.culprit[2][0] == 1
                p.start.assert_called_once_with()

            for p in quick_dying_processes:
                assert p.culprit[0] is server_getter.return_value.main
                assert p.culprit[1] == 'pysoa-worker-2'
                assert p.culprit[2][0] == 2
                p.start.assert_called_once_with()
                assert p.terminate.called is False

            for p in slow_dying_processes:
                assert p.culprit[0] is server_getter.return_value.main
                assert p.culprit[1] == 'pysoa-worker-3'
                assert p.culprit[2][0] == 3
                p.start.assert_called_once_with()
                assert p.terminate.called is False
        finally:
            if prev_sigint is not None:
                signal.signal(signal.SIGINT, prev_sigint or signal.SIG_IGN)
            if prev_sigterm is not None:
                signal.signal(signal.SIGTERM, prev_sigterm or signal.SIG_IGN)
            if prev_sighup is not None:
                signal.signal(signal.SIGHUP, prev_sighup or signal.SIG_IGN)


# ---------------------------------------------------------------------------
# Tests for the new default fork count and CLI argument defaults
# ---------------------------------------------------------------------------


class TestDefaultForkCount(unittest.TestCase):
    """Verify that the default number of fork processes is 1."""

    def setUp(self):
        self.assertIsNotNone(standalone, 'setup_module did not run correctly')
        self.prev_argv = sys.argv

    def tearDown(self):
        sys.argv = self.prev_argv

    @mock.patch('multiprocessing.Process')
    @mock.patch('multiprocessing.cpu_count')
    def test_default_fork_processes_is_one(self, mock_cpu_count, mock_process):
        """With no -f flag a single worker process is forked (not a direct main() call)."""
        mock_cpu_count.return_value = 4
        sys.argv = ['/path/to/example_service/standalone.py', '--no-respawn']

        mock_proc = mock.MagicMock()
        mock_proc.is_alive.return_value = False
        mock_process.return_value = mock_proc

        prev_sigint = prev_sigterm = prev_sighup = None
        try:
            prev_sigint = signal.signal(signal.SIGINT, signal.SIG_IGN)
            prev_sigterm = signal.signal(signal.SIGTERM, signal.SIG_IGN)
            prev_sighup = signal.signal(signal.SIGHUP, signal.SIG_IGN)

            standalone.simple_main(mock.MagicMock())  # type: ignore

            self.assertEqual(1, mock_process.call_count, 'Exactly one worker process expected')
            self.assertEqual(1, mock_process.call_args_list[0][1]['args'][0])
        finally:
            if prev_sigint is not None:
                signal.signal(signal.SIGINT, prev_sigint or signal.SIG_IGN)
            if prev_sigterm is not None:
                signal.signal(signal.SIGTERM, prev_sigterm or signal.SIG_IGN)
            if prev_sighup is not None:
                signal.signal(signal.SIGHUP, prev_sighup or signal.SIG_IGN)

    def test_ping_timeout_default_is_ten_seconds(self):
        parser = standalone._get_arg_parser()  # type: ignore
        args = parser.parse_args([])
        self.assertEqual(10, args.ping_timeout)

    def test_process_shutdown_timeout_default_is_thirty_seconds(self):
        parser = standalone._get_arg_parser()  # type: ignore
        args = parser.parse_args([])
        self.assertEqual(30, args.process_shutdown_timeout)


# ---------------------------------------------------------------------------
# Tests for _ProcessMonitor ping mechanism (parent-side watchdog)
# ---------------------------------------------------------------------------


class TestProcessMonitorPingMechanism(unittest.TestCase):
    """
    Unit tests for the parent-side watchdog that kills hung child processes.

    Each test creates a _ProcessMonitor directly, injects a fake child-process
    object, and runs the monitor thread with a very short poll interval so the
    suite stays fast.
    """

    _ORIGINAL_POLL_INTERVAL = None

    def setUp(self):
        self.assertIsNotNone(standalone, 'setup_module did not run correctly')
        TestProcessMonitorPingMechanism._ORIGINAL_POLL_INTERVAL = (
            standalone._ProcessMonitor._POLL_INTERVAL  # type: ignore
        )
        standalone._ProcessMonitor._POLL_INTERVAL = 0.01  # type: ignore

    def tearDown(self):
        standalone._ProcessMonitor._POLL_INTERVAL = (  # type: ignore
            TestProcessMonitorPingMechanism._ORIGINAL_POLL_INTERVAL
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _make_monitor(self, ping_timeout=10, shutdown_timeout=30, respawn=False):
        """Create a _ProcessMonitor whose child process is controlled by the test."""
        signal_context = standalone._SignalContext()  # type: ignore
        monitor = standalone._ProcessMonitor(  # type: ignore
            index=1,
            signal_context=signal_context,
            respawn=respawn,
            shutdown_timeout=shutdown_timeout,
            ping_timeout=ping_timeout,
            target=mock.MagicMock(),
            name='test-worker',
            args=(1,),
        )
        return monitor, signal_context

    # ------------------------------------------------------------------
    # Shared-memory injection
    # ------------------------------------------------------------------

    def test_ping_cells_injected_into_child_args(self):
        """ping_timestamp is appended to the child args tuple."""
        monitor, _ = self._make_monitor()
        child_args = monitor.process_kwargs['args']
        self.assertEqual(1, child_args[0])                        # forked_process_id
        self.assertIs(child_args[1], monitor._ping_timestamp)     # shared Value('d')
        self.assertEqual(2, len(child_args))

    def test_ping_timestamp_is_shared_double(self):
        """_ping_timestamp is a multiprocessing.Value that can hold a monotonic float."""
        monitor, _ = self._make_monitor()
        self.assertIsInstance(monitor._ping_timestamp, multiprocessing.sharedctypes.Synchronized)
        # Should be able to store a full-precision float (as used by time.monotonic()).
        ts = time.monotonic()
        monitor._ping_timestamp.value = ts
        self.assertAlmostEqual(ts, monitor._ping_timestamp.value, places=6)

    # ------------------------------------------------------------------
    # Ping-based SIGKILL
    # ------------------------------------------------------------------

    def test_kills_child_with_stale_ping(self):
        """SIGKILL is sent whenever the ping timestamp is stale beyond ping_timeout."""
        monitor, _ = self._make_monitor(ping_timeout=5, respawn=False)

        # Simulate: child has not pinged for 6 s (> 5 s timeout).
        monitor._ping_timestamp.value = time.monotonic() - 6

        fake = mock.MagicMock()
        fake.pid = 9999
        # First poll: alive (hung). After SIGKILL: dead.
        fake.is_alive.side_effect = [True, False]
        monitor.process = fake

        sent = []
        with mock.patch.object(monitor, '_start_process', side_effect=lambda: None):
            with mock.patch('os.kill', side_effect=lambda pid, sig: sent.append(sig)):
                monitor.start()
                monitor.join(timeout=5.0)

        self.assertFalse(monitor.is_alive(), 'Monitor thread did not exit')
        self.assertIn(signal.SIGKILL, sent, 'Expected SIGKILL for hung child')

    def test_fresh_ping_prevents_kill(self):
        """A child with a fresh ping timestamp must not be killed."""
        monitor, _ = self._make_monitor(ping_timeout=5, respawn=False)

        monitor._ping_timestamp.value = time.monotonic()  # fresh

        counter = [0]

        def _is_alive():
            counter[0] += 1
            return counter[0] <= 4

        fake = mock.MagicMock()
        fake.pid = 9999
        fake.is_alive.side_effect = _is_alive
        monitor.process = fake

        sent = []
        with mock.patch.object(monitor, '_start_process', side_effect=lambda: None):
            with mock.patch('os.kill', side_effect=lambda pid, sig: sent.append(sig)):
                monitor.start()
                monitor.join(timeout=5.0)

        self.assertNotIn(signal.SIGKILL, sent, 'Child with fresh ping must not be killed')

    # ------------------------------------------------------------------
    # Shutdown SIGKILL escalation
    # ------------------------------------------------------------------

    def test_sigkill_escalation_after_shutdown_timeout(self):
        """SIGTERM is escalated to SIGKILL when the child ignores the shutdown signal."""
        monitor, signal_context = self._make_monitor(shutdown_timeout=0, respawn=False)

        fake = mock.MagicMock()
        fake.pid = 9999
        fake.is_alive.return_value = True   # never exits on its own

        sent = []

        def _os_kill(pid, sig):
            sent.append(sig)
            if sig == signal.SIGKILL:
                fake.is_alive.return_value = False   # dead after SIGKILL

        def _trigger():
            time.sleep(0.05)
            signal_context.signaled = True
            monitor.terminate()

        monitor.process = fake
        with mock.patch.object(monitor, '_start_process', side_effect=lambda: None):
            with mock.patch('os.kill', side_effect=_os_kill):
                monitor.start()
                threading.Thread(target=_trigger, daemon=True).start()
                monitor.join(timeout=10.0)

        self.assertFalse(monitor.is_alive(), 'Monitor thread did not exit')
        self.assertIn(signal.SIGKILL, sent, 'Expected SIGKILL escalation after timeout')

    def test_no_sigkill_when_child_exits_gracefully(self):
        """A child that exits during the shutdown join window must not receive SIGKILL."""
        monitor, signal_context = self._make_monitor(shutdown_timeout=30, respawn=False)

        fake = mock.MagicMock()
        fake.pid = 9999
        fake.is_alive.return_value = True

        def _graceful_join(*args, **kwargs):
            # Simulate graceful exit the moment the parent waits.
            fake.is_alive.return_value = False

        fake.join.side_effect = _graceful_join

        sent = []

        def _trigger():
            time.sleep(0.05)
            signal_context.signaled = True
            monitor.terminate()

        monitor.process = fake
        with mock.patch.object(monitor, '_start_process', side_effect=lambda: None):
            with mock.patch('os.kill', side_effect=lambda pid, sig: sent.append(sig)):
                monitor.start()
                threading.Thread(target=_trigger, daemon=True).start()
                monitor.join(timeout=10.0)

        self.assertNotIn(signal.SIGKILL, sent, 'Gracefully-exiting child must not be SIGKILL-ed')

    # ------------------------------------------------------------------
    # Respawn after ping-kill
    # ------------------------------------------------------------------

    def test_respawns_after_ping_kill(self):
        """The monitor spawns a replacement process after killing a hung child."""
        monitor, signal_context = self._make_monitor(ping_timeout=5, respawn=True)

        calls = [0]

        def _start_proc():
            calls[0] += 1
            p = mock.MagicMock()
            p.pid = 9000 + calls[0]

            if calls[0] == 1:
                # First spawn: stuck — stale ping.
                monitor._ping_timestamp.value = time.monotonic() - 6
                p.is_alive.side_effect = [True, False]   # True → stuck, False → after kill
            else:
                # Second spawn: exits immediately and signals shutdown.
                p.is_alive.return_value = False
                signal_context.signaled = True

            monitor.process = p

        with mock.patch.object(monitor, '_start_process', side_effect=_start_proc):
            with mock.patch('os.kill'):
                monitor._start_process()   # wire up first process
                monitor.start()
                monitor.join(timeout=5.0)

        self.assertFalse(monitor.is_alive(), 'Monitor thread did not exit')
        self.assertEqual(2, calls[0], 'Expected initial spawn + one respawn after ping-kill')

    def test_start_process_resets_ping_state(self):
        """
        _start_process refreshes the ping timestamp before spawning a new child.

        Without this reset, a stale _ping_timestamp left by a crashed/killed worker
        would cause its replacement to be immediately SIGKILL-ed.
        """
        monitor, _ = self._make_monitor()

        # Simulate a stale timestamp left by a previously killed/crashed worker.
        monitor._ping_timestamp.value = 0.0          # epoch — obviously stale

        fake_process = mock.MagicMock()
        before = time.monotonic()

        with mock.patch('multiprocessing.Process', return_value=fake_process) as mock_mp:
            monitor._start_process()

        self.assertGreaterEqual(monitor._ping_timestamp.value, before,
                                '_start_process must refresh the ping timestamp')
        mock_mp.assert_called_once()
        fake_process.start.assert_called_once_with()

    def test_replacement_not_killed_due_to_stale_ping_from_previous_child(self):
        """
        After a ping-kill the replacement child must not be immediately SIGKILL-ed due to
        the stale _ping_timestamp left by the dead worker.

        We let the real _start_process run (so the timestamp reset actually fires) and
        only mock multiprocessing.Process to return a controllable fake child object.
        """
        monitor, signal_context = self._make_monitor(ping_timeout=5, respawn=True)

        spawn_count = [0]
        sigkills_per_spawn = collections.defaultdict(int)

        def make_process(**kwargs):
            spawn_count[0] += 1
            n = spawn_count[0]
            p = mock.MagicMock()
            p.pid = 9000 + n

            if n == 1:
                # First child: simulate it writing a stale timestamp to shared memory
                # (as a real child would when it started handling a request and then hung).
                def _start_first():
                    monitor._ping_timestamp.value = time.monotonic() - 6
                p.start.side_effect = _start_first
                # Alive on first poll (stuck), dead on second (after SIGKILL).
                p.is_alive.side_effect = [True, False]
            else:
                # Replacement: by this point _start_process has reset the ping state.
                # The replacement is alive for one poll (exercising the ping check) and
                # then exits naturally. Signal shutdown so the monitor doesn't respawn again.
                def _start_replacement():
                    signal_context.signaled = True
                p.start.side_effect = _start_replacement
                p.is_alive.side_effect = [True, False]

            return p

        def _os_kill(pid, sig):
            if sig == signal.SIGKILL:
                sigkills_per_spawn[spawn_count[0]] += 1

        with mock.patch('multiprocessing.Process', side_effect=make_process):
            with mock.patch('os.kill', side_effect=_os_kill):
                monitor.start()
                monitor.join(timeout=5.0)

        self.assertFalse(monitor.is_alive(), 'Monitor thread did not exit')
        self.assertEqual(2, spawn_count[0], 'Expected initial spawn + one respawn')
        self.assertEqual(1, sigkills_per_spawn[1], 'Expected exactly one SIGKILL for the stuck child')
        self.assertEqual(0, sigkills_per_spawn[2], 'Replacement child must not be SIGKILL-ed')
