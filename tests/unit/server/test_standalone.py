from __future__ import (
    absolute_import,
    unicode_literals,
)

import os
import signal
import sys
import unittest

from pysoa.test.compatibility import mock


standalone = None


def setup_module(_):
    """
    We want this setup to run before any of the tests in this module, to ensure that the `standalone` module gets
    imported.
    """
    global standalone
    try:
        from pysoa.server import standalone
        assert False, 'Should not have been able to import standalone; should have received SystemExit'
    except SystemExit as e:
        # This first bit is actually a test; it confirms that the double-import trap is triggered
        assert e.args[0] == 99

    # Now we actually import the module, but we have to make sure the double-import trap isn't triggered before we do.
    # Running `pytest` or `setup.py` looks to `standalone` like there is a problem, so we temporarily remove `pytest`
    # or `setup.py` from the first path item...
    prev_path_0 = sys.path[0]
    sys.path[0] = ''
    try:
        from pysoa.server import standalone
    except SystemExit as e:
        assert False, 'Expected import to succeed, instead got SystemExit with code {}'.format(e.args[0])
    finally:
        # ...and then we put it back in so that we haven't caused any problems.
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

        standalone.simple_main(server_getter)

        server_getter.assert_called_once_with()
        server_getter.return_value.main.assert_called_once_with()

    @mock.patch('pysoa.server.autoreload.get_reloader')
    def test_only_file_watcher_argument_no_values(self, mock_get_reloader):
        server_getter = mock.MagicMock()

        sys.argv = ['/path/to/example_service/standalone.py', '--use-file-watcher']

        standalone.simple_main(server_getter)

        server_getter.assert_called_once_with()
        self.assertFalse(server_getter.return_value.main.called)

        mock_get_reloader.assert_called_once_with('', None, signal_forks=False)
        self.assertEqual(1, mock_get_reloader.return_value.main.call_count)
        self.assertEqual(
            server_getter.return_value,
            mock_get_reloader.return_value.main.call_args_list[0][0][1][1],
        )

    @mock.patch('pysoa.server.autoreload.get_reloader')
    def test_only_file_watcher_argument_some_values(self, mock_get_reloader):
        server_getter = mock.MagicMock()

        sys.argv = ['/path/to/example_service/standalone.py', '--use-file-watcher', 'example,pysoa,conformity']

        standalone.simple_main(server_getter)

        server_getter.assert_called_once_with()
        self.assertFalse(server_getter.return_value.main.called)

        mock_get_reloader.assert_called_once_with('', ['example', 'pysoa', 'conformity'], signal_forks=False)
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

        standalone.simple_main(server_getter)

        server_getter.assert_called_once_with()
        self.assertFalse(server_getter.return_value.main.called)

        mock_get_reloader.assert_called_once_with('', None, signal_forks=True)
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

        standalone.simple_main(server_getter)

        server_getter.assert_called_once_with()
        self.assertFalse(server_getter.return_value.main.called)

        mock_get_reloader.assert_called_once_with('', ['pysoa'], signal_forks=True)
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

        sys.argv = ['/path/to/example_service/standalone.py', '-f', '10']

        prev_sigint = prev_sigterm = prev_sighup = False
        try:
            prev_sigint = signal.signal(signal.SIGINT, signal.SIG_IGN)
            prev_sigterm = signal.signal(signal.SIGTERM, signal.SIG_IGN)
            prev_sighup = signal.signal(signal.SIGHUP, signal.SIG_IGN)

            processes = [mock.MagicMock() for _ in range(0, 10)]
            mock_process.side_effect = processes

            standalone.simple_main(server_getter)

            server_getter.assert_called_once_with()
            self.assertFalse(server_getter.return_value.main.called)

            self.assertEqual(10, mock_process.call_count)
            i = 0
            for i, call in enumerate(mock_process.call_args_list):
                self.assertEqual(server_getter.return_value.main, call[1]['target'])
                self.assertEqual('pysoa-worker-{}'.format(i), call[1]['name'])
                i += 1
            self.assertEqual(10, i)

            for i, process in enumerate(processes):
                self.assertTrue(process.start.called, 'Process {} was not started'.format(i))
                self.assertTrue(process.join.called, 'Process {} was not joined'.format(i))
                self.assertFalse(process.terminate.called, 'Process {} should not have been terminated'.format(i))

            os.kill(os.getpid(), signal.SIGHUP)

            for i, process in enumerate(processes):
                self.assertTrue(process.terminate.called, 'Process {} was terminated'.format(i))
        finally:
            if prev_sigint is not False:
                signal.signal(signal.SIGINT, prev_sigint or signal.SIG_IGN)
            if prev_sigterm is not False:
                signal.signal(signal.SIGTERM, prev_sigterm or signal.SIG_IGN)
            if prev_sighup is not False:
                signal.signal(signal.SIGHUP, prev_sighup or signal.SIG_IGN)

    @mock.patch('multiprocessing.Process')
    @mock.patch('multiprocessing.cpu_count')
    def test_only_forking_limited(self, mock_cpu_count, mock_process):
        server_getter = mock.MagicMock()

        mock_cpu_count.return_value = 1

        sys.argv = ['/path/to/example_service/standalone.py', '-f', '10']

        prev_sigint = prev_sigterm = prev_sighup = False
        try:
            prev_sigint = signal.signal(signal.SIGINT, signal.SIG_IGN)
            prev_sigterm = signal.signal(signal.SIGTERM, signal.SIG_IGN)
            prev_sighup = signal.signal(signal.SIGHUP, signal.SIG_IGN)

            processes = [mock.MagicMock() for _ in range(0, 5)]
            mock_process.side_effect = processes

            standalone.simple_main(server_getter)

            server_getter.assert_called_once_with()
            self.assertFalse(server_getter.return_value.main.called)

            self.assertEqual(5, mock_process.call_count)
            i = 0
            for i, call in enumerate(mock_process.call_args_list):
                self.assertEqual(server_getter.return_value.main, call[1]['target'])
                self.assertEqual('pysoa-worker-{}'.format(i), call[1]['name'])
                i += 1
            self.assertEqual(5, i)

            for i, process in enumerate(processes):
                self.assertTrue(process.start.called, 'Process {} was not started'.format(i))
                self.assertTrue(process.join.called, 'Process {} was not joined'.format(i))
                self.assertFalse(process.terminate.called, 'Process {} should not have been terminated'.format(i))

            os.kill(os.getpid(), signal.SIGHUP)

            for i, process in enumerate(processes):
                self.assertTrue(process.terminate.called, 'Process {} was terminated'.format(i))
        finally:
            if prev_sigint is not False:
                signal.signal(signal.SIGINT, prev_sigint or signal.SIG_IGN)
            if prev_sigterm is not False:
                signal.signal(signal.SIGTERM, prev_sigterm or signal.SIG_IGN)
            if prev_sighup is not False:
                signal.signal(signal.SIGHUP, prev_sighup or signal.SIG_IGN)
