from __future__ import (
    absolute_import,
    unicode_literals,
)

import datetime
import os
import signal
import sys
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

    def test_no_arguments(self):
        server_getter = mock.MagicMock()

        sys.argv = ['/path/to/example_service/standalone.py']

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
        assert mock_get_reloader.call_args_list[0][0][0] in ('', 'pytest', 'coverage')
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
        assert mock_get_reloader.call_args_list[0][0][0] in ('', 'pytest', 'coverage')
        assert mock_get_reloader.call_args_list[0][0][1] == ['example', 'pysoa', 'conformity']
        assert mock_get_reloader.call_args_list[0][1]['signal_forks'] is False

        self.assertEqual(1, mock_get_reloader.return_value.main.call_count)
        self.assertEqual(0, mock_get_reloader.return_value.main.call_args_list[0][0][1][0].fork_processes)
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
        assert mock_get_reloader.call_args_list[0][0][0] in ('', 'pytest', 'coverage')
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
        assert mock_get_reloader.call_args_list[0][0][0] in ('', 'pytest', 'coverage')
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
            mock_process.side_effect = processes

            standalone.simple_main(server_getter)  # type: ignore

            server_getter.assert_called_once_with()
            self.assertFalse(server_getter.return_value.main.called)

            self.assertEqual(10, mock_process.call_count)
            i = 1
            for call in mock_process.call_args_list:
                self.assertEqual(server_getter.return_value.main, call[1]['target'])
                self.assertEqual('pysoa-worker-{}'.format(i), call[1]['name'])
                self.assertEqual((i, ), call[1]['args'])
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
            mock_process.side_effect = processes

            standalone.simple_main(server_getter)  # type: ignore

            server_getter.assert_called_once_with()
            self.assertFalse(server_getter.return_value.main.called)

            self.assertEqual(5, mock_process.call_count)
            i = 1
            for call in mock_process.call_args_list:
                self.assertEqual(server_getter.return_value.main, call[1]['target'])
                self.assertEqual('pysoa-worker-{}'.format(i), call[1]['name'])
                self.assertEqual((i, ), call[1]['args'])
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

            def patched_freeze_time():
                # TODO Until https://github.com/spulec/freezegun/issues/307 is fixed
                f = freezegun.freeze_time()
                f.ignore = tuple(set(f.ignore) - {'threading'})
                return f

            with patched_freeze_time() as frozen_time:
                def tick_six_se():
                    frozen_time.tick(datetime.timedelta(seconds=6))

                def tick_twenty_se():
                    frozen_time.tick(datetime.timedelta(seconds=20))

                def signal_se():
                    os.kill(os.getpid(), signal.SIGTERM)
                    time.sleep(0.3)

                def se(target, name, args):
                    process = mock.MagicMock()
                    process.culprit = (target, name, args)
                    if args[0] == 1:
                        # If it's the first process, we want to actually live. This tests normal operation.
                        living_processes.append(process)
                        if len(living_processes) == 6:
                            raise ValueError('Too many, too many!')
                        elif len(living_processes) == 5:
                            process.join.side_effect = signal_se
                        else:
                            process.join.side_effect = tick_twenty_se
                        if len(living_processes) == 1:
                            time.sleep(3)  # sleep 3 seconds so that all of these happen after quick- and slow-dying
                    elif args[0] == 2:
                        # If it's the second process, we want to die quickly. This tests the 15-second respawn limit.
                        quick_dying_processes.append(process)
                        # no sleep so that all of these happen before any ticks, before slow-dying and living
                    elif args[0] == 3:
                        # If it's the third process, we want to die slowly. This tests the 60-second respawn limit.
                        slow_dying_processes.append(process)
                        process.join.side_effect = tick_six_se
                        if len(slow_dying_processes) == 1:
                            time.sleep(1)  # sleep 1 second so that all of these happen after quick-dying
                    else:
                        bad_processes.append((target, name, args))
                        raise ValueError('Nope nope nope')
                    return process

                mock_process.side_effect = se

                standalone.simple_main(server_getter)  # type: ignore

            server_getter.assert_called_once_with()
            assert server_getter.return_value.main.called is False

            assert len(bad_processes) == 0
            assert len(quick_dying_processes) == 4
            assert len(slow_dying_processes) == 9
            assert len(living_processes) == 5

            for i, p in enumerate(living_processes):
                assert p.culprit[0] is server_getter.return_value.main
                assert p.culprit[1] == 'pysoa-worker-1'
                assert p.culprit[2] == (1, )
                if i < 5:
                    p.start.assert_called_once_with()
                    p.join.assert_called_once_with()
            for p in living_processes[:-1]:
                assert p.terminate.called is False
            living_processes[-1].terminate.assert_called_once_with()

            for p in quick_dying_processes:
                assert p.culprit[0] is server_getter.return_value.main
                assert p.culprit[1] == 'pysoa-worker-2'
                assert p.culprit[2] == (2, )
                p.start.assert_called_once_with()
                p.join.assert_called_once_with()
                assert p.terminate.called is False

            for p in slow_dying_processes:
                assert p.culprit[0] is server_getter.return_value.main
                assert p.culprit[1] == 'pysoa-worker-3'
                assert p.culprit[2] == (3, )
                p.start.assert_called_once_with()
                p.join.assert_called_once_with()
                assert p.terminate.called is False
        finally:
            if prev_sigint is not None:
                signal.signal(signal.SIGINT, prev_sigint or signal.SIG_IGN)
            if prev_sigterm is not None:
                signal.signal(signal.SIGTERM, prev_sigterm or signal.SIG_IGN)
            if prev_sighup is not None:
                signal.signal(signal.SIGHUP, prev_sighup or signal.SIG_IGN)
