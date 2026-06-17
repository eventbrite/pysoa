from __future__ import (
    absolute_import,
    unicode_literals,
)

import argparse
import collections
import importlib
import logging
import multiprocessing
import os
import signal
import sys
import threading
import time
from typing import (
    Any,
    Callable,
    Deque,
    List,
    Optional,
    Type,
)

import attr
import six

from pysoa.server.server import Server
import pysoa.utils


__all__ = (
    'django_main',
    'simple_main',
)


def is_double_import():  # type: () -> bool
    # - When Python is invoked using `python -m some_module`, the first item in the path is always empty in Python 2.7
    #   through 3.6. In 3.7+, it is equal to the full path to and including the module file.
    # - When Python is invoked using an entry-point binary, the first item in the path is a /bin folder somewhere
    # - When Python is invoked using `python /path/to/file.py`, the first item in the path is `/path/to`
    #
    # We want to require an entry-point binary or `-m` and disallow `python /path/to/file.py`. In Python 2.7-3.6 we
    # can just check sys.path, but in Python 3.7 we must check the raw interpreter arguments.
    if not sys.path[0] or sys.path[0].endswith('/bin') or sys.path[0].endswith('/sbin'):
        return False

    return '-m' not in pysoa.utils.get_python_interpreter_arguments()


if is_double_import():
    print(
        'ERROR: You have triggered a double-import trap (see '
        'http://python-notes.curiousefficiency.org/en/latest/python_concepts/import_traps.html#the-double-import-trap '
        'for more information on what this is). In short, you cannot start this service with '
        '`python /path/to/standalone.py`, because that puts all the modules in this service on the path as top-level '
        'modules, potentially masking builtins and breaking all sorts of things with hard-to-diagnose errors. Instead, '
        'you must start this service with `python -m module.to.standalone` or by simply calling the `service_name` '
        'entry point executable. Debug information: {} / {}'.format(sys.path[0], sys.argv)
    )
    exit(99)


def _get_arg_parser():  # type: () -> argparse.ArgumentParser
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-f', '--fork-processes', '--fork',
        help='The number of worker processes to fork (defaults to 1; use 0 to run the server directly in the current '
             'process without forking, which is not recommended for production)',
        required=False,
        type=int,
        default=1,
    )
    parser.add_argument(
        '--no-respawn',
        help='When -f/--fork is used, PySOA will respawn crashed workers by default (unless a worker crashes 3 times '
             'in 15 seconds or 8 times in 60 seconds, in which case PySOA will give up respawning that worker). Use '
             '--no-respawn to disable this behavior and never respawn failed workers.',
        required=False,
        action='store_true',
        default=False,
    )
    parser.add_argument(
        '--process-shutdown-timeout',
        help='When shutting down, the number of seconds to wait for a worker process to exit after sending SIGTERM '
             'before escalating to SIGKILL (default: 30)',
        required=False,
        type=int,
        default=30,
    )
    parser.add_argument(
        '--ping-timeout',
        help='The number of seconds a worker process may spend processing a single request before the parent kills '
             'it with SIGKILL. The child process pings the parent when it starts and finishes each request; if the '
             'parent does not receive a ping within this timeout, it assumes the child is hung (default: 10)',
        required=False,
        type=int,
        default=10,
    )
    parser.add_argument(
        '--startup-timeout',
        help='The number of seconds allowed for a worker process to start up and send its first ping before the '
             'parent kills it with SIGKILL. This is separate from --ping-timeout, which governs per-request watchdog '
             'checks after the first ping has been received (default: 60)',
        required=False,
        type=int,
        default=60,
    )
    parser.add_argument(
        '--use-file-watcher',
        help='If specified, PySOA will watch service files for changes and restart the service automatically. If no '
             'arguments are provided with this option, it will watch all modules. Or, you can provide a '
             'comma-separated list of modules to watch for changes. This feature is only recommended for use in '
             'development environments; it could cause instability in production environments.',
        required=False,
        nargs='?',
        type=lambda v: (list(map(lambda s: s.strip(), v.split(','))) or None) if v else None,
        default=False,
    )
    return parser


def _get_args(parser):  # type: (argparse.ArgumentParser) -> argparse.Namespace
    return parser.parse_known_args()[0]


@attr.s
class _SignalContext(object):
    signaled = attr.ib(default=False)  # type: bool


class _ProcessMonitor(threading.Thread):
    """
    A helper thread that manages starting, monitoring, terminating and, upon premature termination, restarting of
    forked child server processes.
    """
    _POLL_INTERVAL = 1.0  # seconds between join() polls during normal operation

    def __init__(
        self,
        index,  # type: int
        signal_context,  # type: _SignalContext
        respawn,  # type: bool
        shutdown_timeout,  # type: int
        ping_timeout,  # type: int
        startup_timeout,  # type: int
        **kwargs  # type: Any
    ):  # type: (...) -> None
        self.index = index
        self.signal_context = signal_context
        self.respawn = respawn
        self.shutdown_timeout = shutdown_timeout
        self.ping_timeout = ping_timeout
        self.startup_timeout = startup_timeout

        # Shared-memory timestamp written by the child on every meaningful event
        # (request received, request complete, idle timeout) and read by this thread
        # to detect workers that are hung mid-request.
        self._ping_timestamp = multiprocessing.Value('d', time.monotonic())

        # Tracks when the current child process was last (re)started; used to distinguish
        # the startup phase (before the first child ping) from normal operation.
        # Initialised here and refreshed by _start_process() on each (re)spawn.
        self._process_started_at = time.monotonic()

        # Inject the timestamp and ping_timeout into the positional args forwarded to
        # server_class.main().  Both are passed explicitly so that the values are available
        # in the child process even on "spawn" start-mode platforms (Windows, macOS Python
        # 3.13+) where the child does not inherit the parent's sys.argv.
        existing_args = kwargs.pop('args', ())
        self.process_kwargs = dict(kwargs, args=existing_args + (self._ping_timestamp, self.ping_timeout))

        self.process = None  # type: Optional[multiprocessing.Process]
        self.one_minute_restart_times = collections.deque(maxlen=8)  # type: Deque[float]
        self.fifteen_second_restart_times = collections.deque(maxlen=3)  # type: Deque[float]
        super(_ProcessMonitor, self).__init__()

    def start_process(self):  # type: () -> _ProcessMonitor
        super(_ProcessMonitor, self).start()
        return self

    def terminate(self):  # type: () -> None
        if self.process:
            self.process.terminate()

    def _start_process(self):  # type: () -> None
        # Record the start time and reset the ping timestamp to that same instant.
        # Both are set atomically (same value) so that:
        #   _ping_timestamp.value == _process_started_at  →  child has not yet pinged
        #   _ping_timestamp.value  > _process_started_at  →  child has sent at least one ping
        # This also prevents a stale timestamp left by a crashed/killed worker from causing
        # the replacement child to be immediately SIGKILL-ed.
        t = time.monotonic()
        self._process_started_at = t
        self._ping_timestamp.value = t
        self.process = multiprocessing.Process(**self.process_kwargs)
        self.process.start()

    def _kill_process(self, reason=None):  # type: (Optional[str]) -> None
        """Forcefully kill the child process with SIGKILL and wait for it to exit."""
        if not self.process:
            return
        if reason is None:
            reason = 'did not exit within {} seconds of SIGTERM'.format(self.shutdown_timeout)
        sys.stdout.write(
            'Server process #{} {}; sending SIGKILL.\n'.format(self.index, reason)
        )
        sys.stdout.flush()
        try:
            os.kill(self.process.pid, signal.SIGKILL)
        except OSError:
            pass  # process may have exited between the is_alive() check and the kill
        self.process.join(timeout=self.shutdown_timeout)
        if self.process.is_alive():
            sys.stdout.write(
                'Server process #{} could not be killed with SIGKILL; giving up.\n'.format(self.index)
            )
            sys.stdout.flush()

    def run(self):  # type: () -> None
        self._start_process()
        assert self.process is not None

        while True:
            # Poll with a short timeout so we can react to shutdown signals promptly
            # rather than blocking indefinitely in join().
            self.process.join(timeout=self._POLL_INTERVAL)

            if not self.process.is_alive():
                # Child exited on its own (normal exit, harakiri os._exit, or crash).
                if self.signal_context.signaled or not self.respawn:
                    break

                t = time.time()

                if (
                    len(self.one_minute_restart_times) == self.one_minute_restart_times.maxlen and
                    t - self.one_minute_restart_times[0] < 60
                ):
                    sys.stdout.write(
                        'Server process #{} has crashed too many times ({}) in the last minute; '
                        'not respawning.\n'.format(self.index, self.one_minute_restart_times.maxlen),
                    )
                    sys.stdout.flush()
                    break
                elif (
                    len(self.fifteen_second_restart_times) == self.fifteen_second_restart_times.maxlen and
                    t - self.fifteen_second_restart_times[0] < 15
                ):
                    sys.stdout.write(
                        'Server process #{} has crashed too many times ({}) in the last 15 seconds; '
                        'not respawning.\n'.format(self.index, self.fifteen_second_restart_times.maxlen),
                    )
                    sys.stdout.flush()
                    break
                else:
                    sys.stdout.write('Re-spawning failed server process #{}\n'.format(self.index))
                    sys.stdout.flush()
                    self.one_minute_restart_times.append(t)
                    self.fifteen_second_restart_times.append(t)
                    self._start_process()

                continue

            if self.signal_context.signaled:
                # The parent received a shutdown signal and already sent SIGTERM via terminate().
                # Give the child a grace period to exit cleanly, then escalate to SIGKILL.
                self.process.join(timeout=self.shutdown_timeout)
                if self.process.is_alive():
                    self._kill_process()
                break

            # Check whether the child is hung.
            # _start_process sets both _ping_timestamp and _process_started_at to the same
            # instant, so:
            #   _ping_timestamp.value == _process_started_at  →  child has never pinged
            #   _ping_timestamp.value  > _process_started_at  →  at least one ping received
            # Before the first ping we apply startup_timeout (measured from process start)
            # to give slow-starting services room to initialise.  After the first ping we
            # apply ping_timeout (measured from the last ping) for per-request hang detection.
            now = time.monotonic()
            last_ping = self._ping_timestamp.value
            has_pinged = last_ping > self._process_started_at
            if has_pinged:
                if now - last_ping > self.ping_timeout:
                    self._kill_process(
                        'has not pinged in more than {} seconds'.format(self.ping_timeout)
                    )
                    # The process is now dead; loop back so is_alive() triggers the respawn logic above.
            else:
                if now - self._process_started_at > self.startup_timeout:
                    self._kill_process(
                        'did not ping within startup timeout of {} seconds'.format(self.startup_timeout)
                    )
                    # The process is now dead; loop back so is_alive() triggers the respawn logic above.

        self.process = None


def _run_server(args, server_class):  # type: (argparse.Namespace, Type[Server]) -> None
    if args.fork_processes >= 1:
        cpu_count = multiprocessing.cpu_count()
        num_processes = args.fork_processes
        max_processes = cpu_count * 5
        if num_processes > max_processes:
            sys.stdout.write(
                'WARNING: Number of requested process forks ({forks}) is greater than five times the number of CPU '
                'cores available ({cores} cores). Capping number of forks at {cap}.\n'.format(
                    forks=args.fork_processes,
                    cores=cpu_count,
                    cap=max_processes,
                )
            )
            sys.stdout.flush()
            num_processes = max_processes

        processes_monitors = []  # type: List[_ProcessMonitor]
        signal_lock = threading.Lock()
        signal_context = _SignalContext()

        # `kill -SIGNAL_NAME PID` sends the named signal to the given process, but no further (it does not propagate to
        # the entire process group unless you send it to the GID instead of the PID). But Ctrl+C sends SIGINT to ALL
        # foreground processes, which includes this process AND its children. So the child processes will need to be
        # smart enough to ignore the duplicate signals (and use non-re-entrant locks on the signal handlers to prevent
        # simultaneous signal handling). Also, this parent process can be an intermediate child (if it is wrapped by
        # the code reloader process), so we need to take similar precautions here.

        def signaled(_signal_number, _stack_frame):
            if not signal_lock.acquire(False) or signal_context.signaled:
                # Non-blocking acquire; duplicate simultaneous signals can be ignored
                return

            try:
                signal_context.signaled = True
                for process_monitor in processes_monitors:
                    process_monitor.terminate()
            finally:
                signal_lock.release()

        signal.signal(signal.SIGINT, signal.SIG_IGN)  # temporarily disable sigint before creating processes
        signal.signal(signal.SIGTERM, signal.SIG_IGN)  # temporarily disable sigterm before creating processes

        server_class.pre_fork()

        processes_monitors = [
            _ProcessMonitor(
                index=i,
                signal_context=signal_context,
                respawn=not args.no_respawn,
                shutdown_timeout=args.process_shutdown_timeout,
                ping_timeout=args.ping_timeout,
                startup_timeout=args.startup_timeout,
                target=server_class.main,
                name='pysoa-worker-{}'.format(i),
                args=(i, ),
            ).start_process()
            for i in range(1, num_processes + 1)
        ]

        signal.signal(signal.SIGINT, signaled)  # re-enable sigint after starting processes
        signal.signal(signal.SIGTERM, signaled)  # re-enable sigterm after starting processes
        signal.signal(signal.SIGHUP, signaled)  # special signal by file-watching auto-reloader

        time.sleep(1)

        for m in processes_monitors:
            if sys.version_info < (3, 3):
                # In Python < 3.3, Thread.join with no timeout cannot be interrupted by signals, but with timeout it can
                while m.is_alive():
                    m.join(2000000000)
            else:
                # In Python >= 3.3, we can join with no timeout safely
                m.join()
    else:
        server_class.main()


def _run_server_reloader_wrapper(args, server_class):  # type: (argparse.Namespace, Type[Server]) -> None
    if args.use_file_watcher is False:
        # The actual value False means that the option was not specified
        # Do not check for None, which is false-y, because that means it was specified for all modules
        _run_server(args, server_class)
    else:
        # We have to get the main module name, but the actual name (like example_service.standalone), not '__main__'
        # If IPython PDB set_trace() occurs before this, it will break __main__ and this won't work
        # This is, unfortunately, the only way to get the real main module name
        # noinspection PyUnresolvedReferences,PyPackageRequirements
        import __main__
        module_name = None  # type: Optional[six.text_type]
        if hasattr(__main__, '__loader__'):
            module_name = getattr(__main__.__loader__, 'name', None) or getattr(__main__.__loader__, 'fullname', None)
        if module_name == '__main__':
            # If the name is still __main__, this means Python was called without the -m
            module_name = ''

        from pysoa.server import autoreload
        autoreload.get_reloader(
            module_name or '',
            args.use_file_watcher,
            signal_forks=args.fork_processes >= 1
        ).main(
            _run_server,
            (args, server_class),
        )


def simple_main(server_getter):  # type: (Callable[[], Type[Server]]) -> None
    """
    Call this within `__main__` to start the service as a standalone server without Django support. Your server should
    not have `use_django=True`. If it does, see `django_main`, instead.

    :param server_getter: A callable that returns the service's `Server` class (not an instance of it)
    """
    _run_server_reloader_wrapper(_get_args(_get_arg_parser()), server_getter())


def django_main(server_getter):  # type: (Callable[[], Type[Server]]) -> None
    """
    Call this within `__main__` to start the service as a standalone server with Django support. Your server should have
    `use_django=True`. If it does not, see `simple_main`, instead.

    :param server_getter: A callable that returns the service's `Server` class (not an instance of it). Your service
                          code should not be imported until the `server_getter` callable is called, otherwise Django
                          errors will occur.
    """
    # noinspection PyUnresolvedReferences,PyPackageRequirements
    import django

    parser = _get_arg_parser()
    parser.add_argument(
        '-s', '--settings',
        help='The settings module to use (must be importable)',
        required='DJANGO_SETTINGS_MODULE' not in os.environ,  # if env var does not exist, this argument is required
    )
    args = _get_args(parser)
    if args.settings:
        os.environ['DJANGO_SETTINGS_MODULE'] = args.settings

    warn_about_logging = False

    try:
        # We have to import it manually, because we need to manipulate the settings before setup() is called, but we
        # can't import django.conf.settings until after setup() is called.
        django_settings = importlib.import_module(os.environ['DJANGO_SETTINGS_MODULE'])
        if 'logging' in django_settings.SOA_SERVER_SETTINGS:  # type: ignore
            if (
                getattr(django_settings, 'LOGGING', None) and
                django_settings.LOGGING != django_settings.SOA_SERVER_SETTINGS['logging']  # type: ignore
            ):
                warn_about_logging = True
            django_settings.LOGGING = django_settings.SOA_SERVER_SETTINGS['logging']  # type: ignore
        elif not getattr(django_settings, 'LOGGING', None):
            from pysoa.server.settings import ServerSettings
            django_settings.LOGGING = ServerSettings.defaults['logging']  # type: ignore
    except ImportError:
        raise ValueError('Cannot import Django settings module `{}`.'.format(os.environ['DJANGO_SETTINGS_MODULE']))
    except AttributeError:
        raise ValueError('Cannot find `SOA_SERVER_SETTINGS` in the Django settings module.')

    django.setup()

    if warn_about_logging:
        logging.warning(
            "Django setting `LOGGING` differs from `SOA_SERVER_SETTINGS['logging']` and has been overwritten with "
            "the value of `SOA_SERVER_SETTINGS['logging']`."
        )

    _run_server_reloader_wrapper(args, server_getter())
