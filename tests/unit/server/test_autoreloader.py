"""isort:skip_file until https://github.com/timothycrosley/isort/issues/726 is fixed"""
from __future__ import (
    absolute_import,
    unicode_literals,
)

import codecs
import importlib
import os
import signal
import sys
import tempfile
import time
from typing import (
    Dict,
    Optional,
)
import unittest

import pysoa
import pysoa.client
import pysoa.server
import pysoa.server.autoreload
# noinspection PyProtectedMember
from pysoa.server.autoreload import (
    NEED_RELOAD_EXIT_CODE,
    AbstractReloader,
    _PollingReloader,
    _PyInotifyReloader,
    get_reloader,
)
from pysoa.server.autoreload import _clean_files  # noqa
from pysoa.test.compatibility import mock
import pysoa.version


HAS_PY_INOTIFY = pysoa.server.autoreload.USE_PY_INOTIFY


class MockReloader(AbstractReloader):
    def __init__(self, *args, **kwargs):
        super(MockReloader, self).__init__(*args, **kwargs)
        self.code_changed_called = False
        self.code_changed_return_value = False
        self.code_changed_set_watching_to = False  # type: Optional[bool]

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

    @unittest.skipIf(HAS_PY_INOTIFY, 'This test should only run when PyInotify is not installed')
    def test_get_reloader_without_pyinotify(self):
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
            pysoa.server.autoreload.USE_PY_INOTIFY = HAS_PY_INOTIFY

    @unittest.skipIf(not HAS_PY_INOTIFY, 'This test should only run when PyInotify is installed')
    def test_get_reloader_with_pyinotify(self):
        reloader = get_reloader('example_service.server.standalone', ['example', 'pysoa', 'conformity'])

        self.assertIsInstance(reloader, _PyInotifyReloader)
        self.assertEqual('example_service.server.standalone', reloader.main_module_name)
        self.assertIsNotNone(reloader.watch_modules)
        self.assertFalse(reloader.signal_forks)

        reloader = get_reloader('example_service.standalone', [], signal_forks=True)

        self.assertIsInstance(reloader, _PyInotifyReloader)
        self.assertEqual('example_service.standalone', reloader.main_module_name)
        self.assertIsNone(reloader.watch_modules)
        self.assertTrue(reloader.signal_forks)

        pysoa.server.autoreload.USE_PY_INOTIFY = False

        try:
            reloader = get_reloader('example_service.standalone', [], signal_forks=True)

            self.assertIsInstance(reloader, _PollingReloader)
            self.assertEqual('example_service.standalone', reloader.main_module_name)
            self.assertIsNone(reloader.watch_modules)
            self.assertTrue(reloader.signal_forks)
        finally:
            pysoa.server.autoreload.USE_PY_INOTIFY = HAS_PY_INOTIFY


class TestAbstractReloader(unittest.TestCase):
    """
    We can't unit test much of the reloader; a lot of it simply can only be tested manually. But we test what we can.
    """
    def test_cannot_instantiate_abstract_class(self):
        with self.assertRaises(TypeError):
            AbstractReloader('example_service.name', None)  # type: ignore

    # noinspection PyCompatibility
    def test_constructor(self):
        reloader = MockReloader('example_service.standalone', None)
        assert reloader.main_module_name == 'example_service.standalone'
        assert reloader.signal_forks is False
        assert reloader.watch_modules is None

        reloader = MockReloader('example_service.another', [], True)
        assert reloader.main_module_name == 'example_service.another'
        assert reloader.signal_forks is True
        assert reloader.watch_modules is None

        reloader = MockReloader('example_service.server', ['example', 'pysoa', 'django'])
        assert reloader.main_module_name == 'example_service.server'
        assert reloader.signal_forks is False
        assert reloader.watch_modules is not None

        assert reloader.watch_modules.search('example_service'), reloader.watch_modules
        assert reloader.watch_modules.search('example_service.actions'), reloader.watch_modules
        assert reloader.watch_modules.search('example_service.models'), reloader.watch_modules
        assert reloader.watch_modules.search('example_service.server'), reloader.watch_modules
        assert reloader.watch_modules.search('example_library'), reloader.watch_modules
        assert reloader.watch_modules.search('example_library.utils'), reloader.watch_modules
        assert reloader.watch_modules.search('pysoa'), reloader.watch_modules
        assert reloader.watch_modules.search('pysoa.server'), reloader.watch_modules
        assert reloader.watch_modules.search('pysoa.version'), reloader.watch_modules
        assert reloader.watch_modules.search('django'), reloader.watch_modules
        assert reloader.watch_modules.search('django.conf'), reloader.watch_modules

        assert not reloader.watch_modules.search('another_library'), reloader.watch_modules

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
        called_signals = {}  # type: Dict[int, int]

        def _sig_called(sig_num, _stack_frame):
            called_signals.setdefault(sig_num, 0)
            called_signals[sig_num] += 1

        prev_sigterm = prev_sighup = None
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
            if prev_sigterm is not None:
                signal.signal(signal.SIGTERM, prev_sigterm or signal.SIG_IGN)
            if prev_sighup is not None:
                signal.signal(signal.SIGHUP, prev_sighup or signal.SIG_IGN)

    def test_watch_files_with_forks(self):
        called_signals = {}  # type: Dict[int, int]

        def _sig_called(sig_num, _stack_frame):
            called_signals.setdefault(sig_num, 0)
            called_signals[sig_num] += 1

        prev_sigterm = prev_sighup = None
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
            assert 1.5 > time.time() - start > 0.95

            reloader.code_changed_return_value = True

            start = time.time()
            reloader.watch_files()

            self.assertTrue(reloader.shutting_down_for_reload)
            self.assertTrue(reloader.code_changed_called)
            self.assertEqual(2, len(called_signals))
            self.assertEqual(1, called_signals[signal.SIGTERM])
            self.assertEqual(1, called_signals[signal.SIGHUP])
            assert time.time() - start < 0.3
        finally:
            if prev_sigterm is not None:
                signal.signal(signal.SIGTERM, prev_sigterm or signal.SIG_IGN)
            if prev_sighup is not None:
                signal.signal(signal.SIGHUP, prev_sighup or signal.SIG_IGN)

    @mock.patch('pysoa.server.autoreload.subprocess')
    def test_restart_with_reloader_use_module(self, mock_subprocess):
        se_context = {'i': 0}

        def se(*_, **__):
            if se_context['i'] == 5:
                os.kill(os.getpid(), signal.SIGTERM)
            se_context['i'] += 1
            return 52 if se_context['i'] == 6 else NEED_RELOAD_EXIT_CODE

        mock_subprocess.Popen.return_value.wait.side_effect = se

        prev_arg_0 = sys.argv[0]
        sys.argv[0] = '/path/to/example_service/standalone.py'

        try:
            reloader = MockReloader('example_service.standalone', ['pysoa'])

            assert reloader.restart_with_reloader() == 52

            self.assertEqual(6, mock_subprocess.Popen.call_count)

            i = 0
            for call in mock_subprocess.Popen.call_args_list:
                i += 1
                self.assertEqual(
                    [sys.executable, '-m', 'example_service.standalone'] + sys.argv[1:],
                    call[0][0],
                )
                env = call[1]['env'].copy()
                self.assertTrue('PYSOA_RELOADER_RUN_MAIN', env)
                del env['PYSOA_RELOADER_RUN_MAIN']
                self.assertEqual(os.environ, env)

            self.assertEqual(6, i)

            assert mock_subprocess.Popen.return_value.wait.call_count == 6
            assert mock_subprocess.Popen.return_value.terminate.call_count == 1
        finally:
            sys.argv[0] = prev_arg_0

    @mock.patch('pysoa.server.autoreload.subprocess')
    def test_restart_with_reloader_use_script(self, mock_subprocess):
        mock_subprocess.Popen.return_value.wait.side_effect = [
            NEED_RELOAD_EXIT_CODE,
            NEED_RELOAD_EXIT_CODE,
            NEED_RELOAD_EXIT_CODE,
            NEED_RELOAD_EXIT_CODE,
            67,
        ]

        os.environ['PYSOA_RELOADER_WRAPPER_BIN'] = 'coverage run --append'

        try:
            reloader = MockReloader('example_service.standalone', ['pysoa'])

            assert reloader.restart_with_reloader() == 67

            self.assertEqual(5, mock_subprocess.Popen.call_count)

            i = 0
            for call in mock_subprocess.Popen.call_args_list:
                i += 1
                self.assertEqual(
                    ['coverage', 'run', '--append'] + sys.argv,
                    call[0][0],
                )
                env = call[1]['env'].copy()
                self.assertTrue('PYSOA_RELOADER_RUN_MAIN', env)
                del env['PYSOA_RELOADER_RUN_MAIN']
                self.assertEqual(os.environ, env)

            self.assertEqual(5, i)

            assert mock_subprocess.Popen.return_value.wait.call_count == 5
            assert mock_subprocess.Popen.return_value.terminate.call_count == 0
        finally:
            del os.environ['PYSOA_RELOADER_WRAPPER_BIN']

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
            mock_os.environ.get.assert_called_once_with('PYSOA_RELOADER_RUN_MAIN')
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
            mock_os.environ.get.assert_called_once_with('PYSOA_RELOADER_RUN_MAIN')
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
            mock_os.environ.get.assert_called_once_with('PYSOA_RELOADER_RUN_MAIN')
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
            mock_os.environ.get.assert_called_once_with('PYSOA_RELOADER_RUN_MAIN')
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
            mock_os.environ.get.assert_called_once_with('PYSOA_RELOADER_RUN_MAIN')
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
    def test_code_changed(self):
        codec = codecs.lookup('utf8')

        with tempfile.NamedTemporaryFile('wb') as tmp_file1, tempfile.NamedTemporaryFile('wb') as tmp_file2, \
                codecs.StreamReaderWriter(tmp_file1, codec.streamreader, codec.streamwriter, 'strict') as file1, \
                codecs.StreamReaderWriter(tmp_file2, codec.streamreader, codec.streamwriter, 'strict') as file2:
            reloader = _PollingReloader('example_service.standalone', ['pysoa'])

            file1.write('test 1')
            file1.flush()

            file2.write('test 2')
            file2.flush()

            # noinspection PyUnresolvedReferences
            with mock.patch.object(target=reloader, attribute='get_watch_file_names') as mock_get_watch_file_names:
                mock_get_watch_file_names.return_value = [file1.name, file2.name]

                self.assertFalse(reloader.code_changed())

                time.sleep(1.1)

                file1.write('test changed 1')
                file1.flush()

                self.assertTrue(reloader.code_changed())
                self.assertFalse(reloader.code_changed())

                time.sleep(1.1)

                file2.write('test changed 2')
                file2.flush()

                self.assertTrue(reloader.code_changed())
                self.assertFalse(reloader.code_changed())

                time.sleep(1.1)

                file2.write('test changed 2 again')
                file2.flush()

                self.assertTrue(reloader.code_changed())


@unittest.skipIf(not HAS_PY_INOTIFY, 'This can only run if PyInotify is installed')
class TestPyInotifyReloader(unittest.TestCase):
    def test_code_changed(self):
        from multiprocessing.pool import ThreadPool

        codec = codecs.lookup('utf8')

        with tempfile.NamedTemporaryFile('wb') as tmp_file1, tempfile.NamedTemporaryFile('wb') as tmp_file2, \
                codecs.StreamReaderWriter(tmp_file1, codec.streamreader, codec.streamwriter, 'strict') as file1, \
                codecs.StreamReaderWriter(tmp_file2, codec.streamreader, codec.streamwriter, 'strict') as file2:
            reloader = _PyInotifyReloader('example_service.standalone', ['pysoa'])
            reloader.watching = True

            pool = ThreadPool(processes=1)

            file1.write('test 1')
            file1.flush()

            file2.write('test 2')
            file2.flush()

            # noinspection PyUnresolvedReferences
            with mock.patch.object(target=reloader, attribute='get_watch_file_names') as mock_get_watch_file_names:
                mock_get_watch_file_names.return_value = [file1.name, file2.name]

                result = pool.apply_async(reloader.code_changed)
                self.assertFalse(result.ready())

                time.sleep(0.2)

                self.assertFalse(result.ready())

                file1.write('test changed 1')
                file1.flush()

                time.sleep(0.2)

                self.assertTrue(result.ready())
                self.assertTrue(result.get())
                self.assertTrue(result.successful())

                result = pool.apply_async(reloader.code_changed)
                self.assertFalse(result.ready())

                time.sleep(0.2)

                self.assertFalse(result.ready())

                file2.write('test changed 2')
                file2.flush()

                time.sleep(0.2)

                self.assertTrue(result.ready())
                self.assertTrue(result.get())
                self.assertTrue(result.successful())

                result = pool.apply_async(reloader.code_changed)
                self.assertFalse(result.ready())

                time.sleep(0.2)

                self.assertFalse(result.ready())

                file2.write('test changed 2 again')
                file2.flush()

                time.sleep(0.2)

                self.assertTrue(result.ready())
                self.assertTrue(result.get())
                self.assertTrue(result.successful())
