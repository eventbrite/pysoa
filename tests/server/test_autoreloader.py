from __future__ import absolute_import, unicode_literals

import importlib
import os
import signal
import sys
import unittest
import time

import pysoa
import pysoa.client
import pysoa.server
import pysoa.server.autoreload
# noinspection PyProtectedMember
from pysoa.server.autoreload import (
    _clean_files,  # noqa
    _PollingReloader,
    _PyInotifyReloader,
    AbstractReloader,
    get_reloader,
    NEED_RELOAD_EXIT_CODE,
)
from pysoa.test.compatibility import mock
import pysoa.version


class MockReloader(AbstractReloader):
    def __init__(self, *args, **kwargs):
        super(MockReloader, self).__init__(*args, **kwargs)
        self.code_changed_called = False
        self.code_changed_return_value = False
        self.code_changed_set_watching_to = False

    def code_changed(self):
        self.code_changed_called = True
        assert self.watching is True, '`self.watching` should be true'
        if self.code_changed_set_watching_to is not None:
            self.watching = self.code_changed_set_watching_to
        return self.code_changed_return_value


class TestReloaderModule(unittest.TestCase):
    def test_clean_files(self):
        self.assertEqual(
            [
                pysoa.__file__.replace('.pyc', '.py'),
                pysoa.client.__file__.replace('.pyc', '.py'),
                pysoa.server.__file__.replace('.pyc', '.py'),
                pysoa.version.__file__.replace('.pyc', '.py'),
            ],
            _clean_files([
                '/path/to/my/project/something.py',
                pysoa.__file__.replace('.pyc', '.py'),
                pysoa.client.__file__.replace('.pyc', '.py') + 'o',
                pysoa.server.__file__.replace('.pyc', '.py')[:-2] + '$py.class',
                pysoa.version.__file__.replace('.pyc', '.py') + 'c',
                '',
                None,
            ]),
        )

    def test_get_reloader(self):
        reloader = get_reloader('example_service.server.standalone', ['example', 'pysoa', 'conformity'])

        self.assertIsInstance(reloader, _PollingReloader)
        self.assertEqual('example_service.server.standalone', reloader.main_module_name)
        self.assertIsNotNone(reloader.watch_modules)
        self.assertFalse(reloader.signal_forks)

        reloader = get_reloader('example_service.standalone', [], signal_forks=True)

        self.assertIsInstance(reloader, _PollingReloader)
        self.assertEqual('example_service.standalone', reloader.main_module_name)
        self.assertIsNone(reloader.watch_modules)
        self.assertTrue(reloader.signal_forks)

        pysoa.server.autoreload.USE_PY_INOTIFY = True

        try:
            reloader = get_reloader('example_service.standalone', [], signal_forks=True)

            self.assertIsInstance(reloader, _PyInotifyReloader)
            self.assertEqual('example_service.standalone', reloader.main_module_name)
            self.assertIsNone(reloader.watch_modules)
            self.assertTrue(reloader.signal_forks)
        finally:
            pysoa.server.autoreload.USE_PY_INOTIFY = False


class TestAbstractReloader(unittest.TestCase):
    """
    We can't unit test much of the reloader; a lot of it simply can only be tested manually. But we test what we can.
    """
    def test_cannot_instantiate_abstract_class(self):
        with self.assertRaises(TypeError):
            AbstractReloader('example_service.name', None)

    def test_constructor(self):
        reloader = MockReloader('example_service.standalone', None)
        self.assertEqual('example_service.standalone', reloader.main_module_name)
        self.assertIsNone(reloader.watch_modules)
        self.assertFalse(reloader.signal_forks)

        reloader = MockReloader('example_service.another', [], True)
        self.assertEqual('example_service.another', reloader.main_module_name)
        self.assertIsNone(reloader.watch_modules)
        self.assertTrue(reloader.signal_forks)

        reloader = MockReloader('example_service.server', ['example', 'pysoa', 'django'])
        self.assertEqual('example_service.server', reloader.main_module_name)
        self.assertIsNotNone(reloader.watch_modules)
        self.assertFalse(reloader.signal_forks)

        self.assertRegexpMatches('example_service', reloader.watch_modules)
        self.assertRegexpMatches('example_service.actions', reloader.watch_modules)
        self.assertRegexpMatches('example_service.models', reloader.watch_modules)
        self.assertRegexpMatches('example_service.server', reloader.watch_modules)
        self.assertRegexpMatches('example_library', reloader.watch_modules)
        self.assertRegexpMatches('example_library.utils', reloader.watch_modules)
        self.assertRegexpMatches('pysoa', reloader.watch_modules)
        self.assertRegexpMatches('pysoa.server', reloader.watch_modules)
        self.assertRegexpMatches('pysoa.version', reloader.watch_modules)
        self.assertRegexpMatches('django', reloader.watch_modules)
        self.assertRegexpMatches('django.conf', reloader.watch_modules)

        self.assertFalse(reloader.watch_modules.match('another_library'))

    def test_get_watch_file_names(self):
        reloader = MockReloader(
            'example_service.server',
            ['pysoa.version', 'pysoa.server.autoreload', 'currint.tests.test_amount'],
        )

        self.assertEqual(
            {
                pysoa.version.__file__.replace('.pyc', '.py'),
                pysoa.server.autoreload.__file__.replace('.pyc', '.py'),
            },
            set(reloader.get_watch_file_names(only_new=True))
        )

        self.assertEqual(
            {
                pysoa.version.__file__.replace('.pyc', '.py'),
                pysoa.server.autoreload.__file__.replace('.pyc', '.py'),
            },
            set(reloader.get_watch_file_names())
        )

        self.assertEqual([], reloader.get_watch_file_names(only_new=True))

        test_amount = importlib.import_module('currint.tests.test_amount')

        self.assertEqual(
            {
                test_amount.__file__.replace('.pyc', '.py'),
            },
            set(reloader.get_watch_file_names(only_new=True))
        )

    def test_watch_files_no_forks(self):
        called_signals = {}

        def _sig_called(sig_num, *_):
            called_signals.setdefault(sig_num, 0)
            called_signals[sig_num] += 1

        prev_sigterm = prev_sighup = False
        try:
            prev_sigterm = signal.signal(signal.SIGTERM, _sig_called)
            prev_sighup = signal.signal(signal.SIGHUP, _sig_called)

            reloader = MockReloader('example_service.standalone', ['pysoa'])

            self.assertFalse(reloader.watching)
            self.assertFalse(reloader.shutting_down_for_reload)
            self.assertFalse(reloader.code_changed_called)
            self.assertEqual(0, len(called_signals))

            start = time.time()
            reloader.watch_files()

            self.assertFalse(reloader.shutting_down_for_reload)
            self.assertTrue(reloader.code_changed_called)
            self.assertEqual(0, len(called_signals))
            self.assertTrue(1.5 > time.time() - start > 0.95)

            reloader.code_changed_return_value = True

            start = time.time()
            reloader.watch_files()

            self.assertTrue(reloader.shutting_down_for_reload)
            self.assertTrue(reloader.code_changed_called)
            self.assertEqual(1, len(called_signals))
            self.assertEqual(1, called_signals[signal.SIGTERM])
            self.assertTrue(time.time() - start < 0.1)

            del called_signals[signal.SIGTERM]
            reloader.code_changed_return_value = True
            reloader.code_changed_set_watching_to = None

            start = time.time()
            reloader.watch_files()

            self.assertTrue(reloader.watching)
            self.assertTrue(reloader.shutting_down_for_reload)
            self.assertTrue(reloader.code_changed_called)
            self.assertEqual(1, len(called_signals))
            self.assertEqual(2, called_signals[signal.SIGTERM])
            self.assertTrue(7.0 > time.time() - start > 6.0)
        finally:
            if prev_sigterm is not False:
                signal.signal(signal.SIGTERM, prev_sigterm or signal.SIG_IGN)
            if prev_sighup is not False:
                signal.signal(signal.SIGHUP, prev_sighup or signal.SIG_IGN)

    def test_watch_files_with_forks(self):
        called_signals = {}

        def _sig_called(sig_num, *_):
            called_signals.setdefault(sig_num, 0)
            called_signals[sig_num] += 1

        prev_sigterm = prev_sighup = False
        try:
            prev_sigterm = signal.signal(signal.SIGTERM, _sig_called)
            prev_sighup = signal.signal(signal.SIGHUP, _sig_called)

            reloader = MockReloader('example_service.standalone', ['pysoa'], signal_forks=True)

            self.assertFalse(reloader.watching)
            self.assertFalse(reloader.shutting_down_for_reload)
            self.assertFalse(reloader.code_changed_called)
            self.assertEqual(0, len(called_signals))

            start = time.time()
            reloader.watch_files()

            self.assertFalse(reloader.shutting_down_for_reload)
            self.assertTrue(reloader.code_changed_called)
            self.assertEqual(0, len(called_signals))
            self.assertTrue(1.5 > time.time() - start > 0.95)

            reloader.code_changed_return_value = True

            start = time.time()
            reloader.watch_files()

            self.assertTrue(reloader.shutting_down_for_reload)
            self.assertTrue(reloader.code_changed_called)
            self.assertEqual(2, len(called_signals))
            self.assertEqual(1, called_signals[signal.SIGTERM])
            self.assertEqual(1, called_signals[signal.SIGHUP])
            self.assertTrue(time.time() - start < 0.1)
        finally:
            if prev_sigterm is not False:
                signal.signal(signal.SIGTERM, prev_sigterm or signal.SIG_IGN)
            if prev_sighup is not False:
                signal.signal(signal.SIGHUP, prev_sighup or signal.SIG_IGN)

    @mock.patch('pysoa.server.autoreload.subprocess')
    def test_restart_with_reloader_use_module(self, mock_subprocess):
        mock_subprocess.call.side_effect = [
            NEED_RELOAD_EXIT_CODE,
            NEED_RELOAD_EXIT_CODE,
            NEED_RELOAD_EXIT_CODE,
            NEED_RELOAD_EXIT_CODE,
            NEED_RELOAD_EXIT_CODE,
            52,
        ]

        prev_arg_0 = sys.argv[0]
        sys.argv[0] = '/path/to/example_service/standalone.py'

        try:
            reloader = MockReloader('example_service.standalone', ['pysoa'])

            reloader.restart_with_reloader()

            self.assertEqual(6, mock_subprocess.call.call_count)

            i = 0
            for call in mock_subprocess.call.call_args_list:
                i += 1
                self.assertEqual(
                    [sys.executable, '-m', 'example_service.standalone'] + sys.argv[1:],
                    call[0][0],
                )
                env = call[1]['env'].copy()
                self.assertTrue('RUN_RELOADER_MAIN', env)
                del env['RUN_RELOADER_MAIN']
                self.assertEqual(os.environ, env)

            self.assertEqual(6, i)
        finally:
            sys.argv[0] = prev_arg_0

    @mock.patch('pysoa.server.autoreload.subprocess')
    def test_restart_with_reloader_use_script(self, mock_subprocess):
        mock_subprocess.call.side_effect = [
            NEED_RELOAD_EXIT_CODE,
            NEED_RELOAD_EXIT_CODE,
            NEED_RELOAD_EXIT_CODE,
            NEED_RELOAD_EXIT_CODE,
            NEED_RELOAD_EXIT_CODE,
            52,
        ]

        reloader = MockReloader('example_service.standalone', ['pysoa'])

        reloader.restart_with_reloader()

        self.assertEqual(6, mock_subprocess.call.call_count)

        i = 0
        for call in mock_subprocess.call.call_args_list:
            i += 1
            self.assertEqual(
                [sys.executable] + sys.argv,
                call[0][0],
            )
            env = call[1]['env'].copy()
            self.assertTrue('RUN_RELOADER_MAIN', env)
            del env['RUN_RELOADER_MAIN']
            self.assertEqual(os.environ, env)

        self.assertEqual(6, i)

    @mock.patch('pysoa.server.autoreload.os')
    @mock.patch('pysoa.server.autoreload.sys')
    def test_watch_and_reload_for_restart(self, mock_sys, mock_os):
        reloader = MockReloader('example_service.standalone', ['pysoa'])

        mock_func = mock.MagicMock()

        # noinspection PyUnresolvedReferences
        with mock.patch.object(target=reloader, attribute='restart_with_reloader') as mock_restart_with_reloader,\
                mock.patch.object(target=reloader, attribute='watch_files') as mock_watch_files,\
                mock.patch.object(target=reloader, attribute='stop_watching') as mock_stop_watching:

            mock_os.environ.get.return_value = None
            mock_restart_with_reloader.return_value = 15

            reloader.watch_and_reload(mock_func, (), {})

            mock_restart_with_reloader.assert_called_once_with()
            mock_sys.exit.assert_called_once_with(15)
            mock_os.environ.get.assert_called_once_with('RUN_RELOADER_MAIN')
            self.assertFalse(mock_watch_files.called)
            self.assertFalse(mock_stop_watching.called)
            self.assertFalse(mock_os.getpid.called)
            self.assertFalse(mock_os.kill.called)

            mock_restart_with_reloader.reset_mock()
            mock_sys.reset_mock()
            mock_os.reset_mock()

            mock_restart_with_reloader.return_value = -21
            mock_os.getpid.return_value = 92738

            reloader.watch_and_reload(mock_func, (), {})

            mock_restart_with_reloader.assert_called_once_with()
            mock_os.getpid.assert_called_once_with()
            mock_os.kill.assert_called_once_with(92738, 21)
            mock_os.environ.get.assert_called_once_with('RUN_RELOADER_MAIN')
            self.assertFalse(mock_watch_files.called)
            self.assertFalse(mock_stop_watching.called)
            self.assertFalse(mock_sys.exit.called)

    @mock.patch('pysoa.server.autoreload.os')
    @mock.patch('pysoa.server.autoreload.sys')
    def test_watch_and_reload_for_watch_normal_exit(self, mock_sys, mock_os):
        reloader = MockReloader('example_service.standalone', ['pysoa'])

        mock_func = mock.MagicMock()

        # noinspection PyUnresolvedReferences
        with mock.patch.object(target=reloader, attribute='restart_with_reloader') as mock_restart_with_reloader, \
                mock.patch.object(target=reloader, attribute='watch_files') as mock_watch_files, \
                mock.patch.object(target=reloader, attribute='stop_watching') as mock_stop_watching:
            def _se(*_, **__):
                time.sleep(0.25)
                mock_watch_files.assert_called_once_with()
                self.assertFalse(mock_stop_watching.called)

            mock_os.environ.get.return_value = 'true'

            mock_func.side_effect = _se

            reloader.watch_and_reload(mock_func, ('a', 'b'), {'c': 'd'})

            mock_func.assert_called_once_with('a', 'b', c='d')
            mock_stop_watching.assert_called_once_with()
            mock_sys.exit.assert_called_once_with(0)
            mock_os.environ.get.assert_called_once_with('RUN_RELOADER_MAIN')
            self.assertFalse(mock_os.kill.called)
            self.assertFalse(mock_restart_with_reloader.called)

    @mock.patch('pysoa.server.autoreload.os')
    @mock.patch('pysoa.server.autoreload.sys')
    def test_watch_and_reload_for_watch_reload_exit(self, mock_sys, mock_os):
        reloader = MockReloader('example_service.standalone', ['pysoa'])

        mock_func = mock.MagicMock()

        # noinspection PyUnresolvedReferences
        with mock.patch.object(target=reloader, attribute='restart_with_reloader') as mock_restart_with_reloader, \
                mock.patch.object(target=reloader, attribute='watch_files') as mock_watch_files, \
                mock.patch.object(target=reloader, attribute='stop_watching') as mock_stop_watching:
            def _se(*_, **__):
                time.sleep(0.25)
                mock_watch_files.assert_called_once_with()
                self.assertFalse(mock_stop_watching.called)
                reloader.shutting_down_for_reload = True

            mock_os.environ.get.return_value = 'true'

            mock_func.side_effect = _se

            reloader.watch_and_reload(mock_func, ('foo', 'bar'), {'baz': 'qux'})

            mock_func.assert_called_once_with('foo', 'bar', baz='qux')
            mock_stop_watching.assert_called_once_with()
            mock_sys.exit.assert_called_once_with(NEED_RELOAD_EXIT_CODE)
            mock_os.environ.get.assert_called_once_with('RUN_RELOADER_MAIN')
            self.assertFalse(mock_os.kill.called)
            self.assertFalse(mock_restart_with_reloader.called)

    @mock.patch('pysoa.server.autoreload.os')
    @mock.patch('pysoa.server.autoreload.sys')
    def test_watch_and_reload_for_watch_exception(self, mock_sys, mock_os):
        reloader = MockReloader('example_service.standalone', ['pysoa'])

        mock_func = mock.MagicMock()

        class MockException(Exception):
            pass

        # noinspection PyUnresolvedReferences
        with mock.patch.object(target=reloader, attribute='restart_with_reloader') as mock_restart_with_reloader, \
                mock.patch.object(target=reloader, attribute='watch_files') as mock_watch_files, \
                mock.patch.object(target=reloader, attribute='stop_watching') as mock_stop_watching:
            def _se(*_, **__):
                time.sleep(0.25)
                mock_watch_files.assert_called_once_with()
                self.assertFalse(mock_stop_watching.called)
                raise MockException()

            mock_os.environ.get.return_value = 'true'

            mock_func.side_effect = _se

            with self.assertRaises(MockException):
                reloader.watch_and_reload(mock_func, ('a', 'b'), {'c': 'd'})

            mock_func.assert_called_once_with('a', 'b', c='d')
            mock_stop_watching.assert_called_once_with()
            mock_os.environ.get.assert_called_once_with('RUN_RELOADER_MAIN')
            self.assertFalse(mock_sys.exit.called)
            self.assertFalse(mock_os.kill.called)
            self.assertFalse(mock_restart_with_reloader.called)

    def test_main_no_args(self):
        reloader = MockReloader('example_service.standalone', ['pysoa'])

        mock_func = mock.MagicMock()

        # noinspection PyUnresolvedReferences
        with mock.patch.object(target=reloader, attribute='watch_and_reload') as mock_watch_and_reload:
            reloader.main(mock_func)

            mock_watch_and_reload.assert_called_once_with(mock_func, (), {})

        self.assertFalse(mock_func.called)

    def test_main_some_args(self):
        reloader = MockReloader('example_service.standalone', ['pysoa'])

        mock_func = mock.MagicMock()

        # noinspection PyUnresolvedReferences
        with mock.patch.object(target=reloader, attribute='watch_and_reload') as mock_watch_and_reload:
            reloader.main(mock_func, ('a', 'b'), {'c': 'd'})

            mock_watch_and_reload.assert_called_once_with(mock_func, ('a', 'b'), {'c': 'd'})

        self.assertFalse(mock_func.called)


class TestPollingReloader(unittest.TestCase):
    class Stat(object):
        # noinspection SpellCheckingInspection
        def __init__(self, m, c):
            self.st_mtime = m
            self.st_ctime = c

    @mock.patch('pysoa.server.autoreload.os')
    def test_code_changed(self, mock_os):
        reloader = _PollingReloader('example_service.standalone', ['pysoa'])

        # noinspection PyUnresolvedReferences
        with mock.patch.object(target=reloader, attribute='get_watch_file_names') as mock_get_watch_file_names:
            mock_get_watch_file_names.return_value = [
                '/path/to/first/file.py',
                '/path/to/another/level.py',
            ]

            mock_os.stat.side_effect = [self.Stat(123456789, 0), self.Stat(987654321, 0)]

            self.assertFalse(reloader.code_changed())

            self.assertEqual(2, mock_os.stat.call_count)
            self.assertEqual('/path/to/first/file.py', mock_os.stat.call_args_list[0][0][0])
            self.assertEqual('/path/to/another/level.py', mock_os.stat.call_args_list[1][0][0])

            mock_os.reset_mock()
            mock_os.stat.side_effect = [self.Stat(123456789, 0), self.Stat(987654321, 0)]

            self.assertFalse(reloader.code_changed())

            self.assertEqual(2, mock_os.stat.call_count)
            self.assertEqual('/path/to/first/file.py', mock_os.stat.call_args_list[0][0][0])
            self.assertEqual('/path/to/another/level.py', mock_os.stat.call_args_list[1][0][0])

            mock_os.reset_mock()
            mock_os.stat.side_effect = [self.Stat(123456789, 0), self.Stat(987654322, 0)]

            self.assertTrue(reloader.code_changed())

            self.assertEqual(2, mock_os.stat.call_count)
            self.assertEqual('/path/to/first/file.py', mock_os.stat.call_args_list[0][0][0])
            self.assertEqual('/path/to/another/level.py', mock_os.stat.call_args_list[1][0][0])
