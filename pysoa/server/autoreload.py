"""
Autoreloading Launcher
Borrowed/adapted from Django Autoreload Utility (https://github.com/django/django/...autoreload.py)
Borrowed from Peter Hunt and the CherryPy project (http://www.cherrypy.org).
Some taken from Ian Bicking's Paste (http://pythonpaste.org/).

Portions copyright (c) 2004, CherryPy Team (team@cherrypy.org).
All rights reserved.

Portions copyright (c) 2017, Django Software Foundation and individual contributors.
All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the
following conditions are met:

    1. Redistributions of source code must retain the above copyright notice, this list of conditions, and the
       following disclaimer.
    2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions, and the
       following disclaimer in the documentation and/or other materials provided with the distribution.
    3. Neither the name of the Django or the CherryPy Team, nor the names of its contributors, may be used to endorse
       or promote products derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES,
INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

The following changes were made to the borrowed code. This is a summary only, and does not detail every minor change:

    - Converted to an object-oriented structure with instance variables that carry the state of the reloader instead
      of using `global` to modify module globals that carry the state of the reloader.
    - Abandoned the use of the non-standard `_thread` module in favor of the `threading` module.
    - Moved the reloader into a daemonic thread (it was previously in the main thread) so that PyInotify can exit
      when the main thread exits. Moved the main program execution into the main thread (it was previously in a
      non-daemonic background thread) so that it can use `signal.signal`.
    - Eliminated the carrying of "error files," which are no longer necessary since the main program execution now
      happens in the main thread.
    - Properly signal the main program thread to shutdown cleanly instead of killing it harshly.
    - Added input variables for filtering modules to monitor and for indicating the `-m` main module used to execute
      the program.
    - Renamed a bunch of variables and functions/methods to reduce ambiguity and have more-self-documenting code.
    - Added considerable documentation about the operation of the reloader.
"""
from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
)

import abc
import os
import re
import signal
import subprocess
import sys
import threading
import time

import six


USE_PY_INOTIFY = False
try:
    # Test whether inotify is enabled and likely to work
    # noinspection PyPackageRequirements
    import pyinotify

    fd = pyinotify.INotifyWrapper.create().inotify_init()
    if fd >= 0:
        USE_PY_INOTIFY = True
        os.close(fd)
except ImportError:
    pyinotify = None


__all__ = (
    'get_reloader',
)


NEED_RELOAD_EXIT_CODE = 3


def _clean_files(file_list):
    file_names = []
    for file_name in file_list:
        if not file_name:
            continue
        if file_name.endswith('.pyc') or file_name.endswith('.pyo'):
            file_name = file_name[:-1]
        if file_name.endswith('$py.class'):
            file_name = file_name[:-9] + 'py'
        if os.path.exists(file_name):
            file_names.append(file_name)
    return file_names


@six.add_metaclass(abc.ABCMeta)
class AbstractReloader(object):
    """
    This is the abstract base reloader, which handles most of the code associated with watching files for changes and
    reloading the application when changes are detected. All base classes must implement the logic for actually
    determining when changes happen to files (encapsulated within the abstract method `code_changed`).

    This base class does the following:

        - If this is the parent process, it starts a clone child process with the reloader enabled
        - If this is the parent process and the clone child process exits with exit code `NEED_RELOAD_EXIT_CODE`,
          it restarts the clone child process with the reloader enabled. If the child process exits with any other exit
          code, it exits with the same exit code.
        - If this is the child process, it starts a daemonic thread for watching files for changes and then executes
          the main program callable in the main thread.
        - The child process daemonic watching thread gets a list of files (possibly filtered by the `watch_modules`
          constructor parameter) that should be watched for changes and then watches them for changes. If changes
          occur, it signals the server process to shut down and then exits with exit code `NEED_RELOAD_EXIT_CODE`
          when it does.
    """

    def __init__(self, main_module_name, watch_modules, signal_forks=False):
        """
        Constructs a new abstract reloader. All subclasses must call `super(...).__init__(...)`.

        This sets up some important instance variables:

            - `main_module_name` from the constructor parameter
            - `watch_modules` is a compiled regular expression for matching module names based on the array from the
              constructor parameter, or `None` if `None` is passed in
            - `signal_forks` from the constructor parameter
            - `cached_modules` is a set of modules that have already been seen by `get_watch_file_names`
            - `cached_file_names` is a list of files that have already been seen by `get_cached_file_names`
            - `watching` is a flag to indicate whether the watcher is currently running; it is also used to tell the
              watcher to stop running.
            - `shutting_down_for_reload` is a flag that the watcher thread sets to tell the main thread that the
              server is shutting down due to file changes, so that the main thread knows to exit with exit code
              `NEED_RELOAD_EXIT_CODE`.

        See the documentation for `get_reloader` below for the meaning of the constructor parameters.
        """
        self.main_module_name = main_module_name
        self.watch_modules = re.compile(
            r'^{}'.format('|'.join(watch_modules).replace('.', r'\.'))
        ) if watch_modules else None
        self.signal_forks = signal_forks
        self.cached_modules = set()
        self.cached_file_names = []
        self.watching = False
        self.shutting_down_for_reload = False

    def get_watch_file_names(self, only_new=False):
        """
        This determines which files we need to watch for changes. For starters, we only watch those modules that have
        been loaded as of startup. Furthermore, if `watch_modules` has been specified, we only watch loaded modules
        that match the name or names provided, or whose parents match the name or names provided.

        To be efficient, we cache the models and files initially looked at, and only look again if new modules have
        been loaded since we last looked.

        :param only_new: `True` means only return the file names that have not been returned on a previous call
        :return: A list of files that we need to watch
        """
        self.cached_file_names = _clean_files(self.cached_file_names)

        module_values = set(sys.modules.values())
        if self.cached_modules == module_values:
            if only_new:
                return []
            else:
                return self.cached_file_names

        new_modules = module_values - self.cached_modules
        self.cached_modules = self.cached_modules.union(new_modules)

        if self.watch_modules:
            new_file_names = _clean_files(
                m.__file__ for m in new_modules if hasattr(m, '__file__') and self.watch_modules.match(m.__name__)
            )
        else:
            new_file_names = _clean_files(m.__file__ for m in new_modules if hasattr(m, '__file__'))

        self.cached_file_names += new_file_names

        if only_new:
            return new_file_names
        else:
            return self.cached_file_names

    @abc.abstractmethod
    def code_changed(self):
        """
        All subclasses must implement this. It should either block indefinitely until a file changes and then return
        `True`, or it should return `True` or `False` immediately to indicate whether files have changed since it was
        last called.

        :return: `True` or `False, has one or more files changed to require a reload
        """
        raise NotImplementedError()

    def watch_files(self):
        """
        Depending on the implementation, this loops or blocks indefinitely until the file watcher indicates code has
        changed, at which point it causes a process exit with the exit code `NEED_RELOAD_EXIT_CODE`.
        """
        self.watching = True
        while self.watching:
            if self.code_changed():
                # Signal the server process that we want it to stop (including its forks), and tell the reloader why
                self.shutting_down_for_reload = True
                os.kill(os.getpid(), signal.SIGTERM)
                if self.signal_forks:
                    os.kill(os.getpid(), signal.SIGHUP)
                # The server should only take 5 seconds to shut down; if it takes longer, send it another signal
                i = 0
                while self.watching:
                    time.sleep(0.5)
                    i += 1
                    if i > 12:
                        print("Process took too long to stop after file change; signaling again (won't restart)")
                        os.kill(os.getpid(), signal.SIGTERM)
                        break
                break
            time.sleep(1)

    def stop_watching(self):
        """
        This allows the main thread to signal the watcher thread that it should stop watching files. Subclasses may
        override this to perform additional stop-watching operations, but they must call `super(...).stop_watching()`.
        """
        self.watching = False

    def restart_with_reloader(self):
        """
        This starts a subprocess that is a clone of the current process, with all the same arguments, but with the
        `RUN_RELOADER_MAIN` environment variable added to the subprocess's environment. It blocks until that subprocess
        exits, and then examines its exit code. If the exit code is `NEED_RELOAD_EXIT_CODE`, this means the file
        watcher indicated files have changed and need to be reloaded and exited, so this loops and starts the process
        again.

        :return: The code with which the clone subprocess exited if not `NEED_RELOAD_EXIT_CODE`.
        """
        command = [sys.executable] + ['-W{}'.format(o) for o in sys.warnoptions]
        if self.main_module_name and '{}.py'.format(self.main_module_name.replace('.', '/')) in sys.argv[0]:
            # The server was started with `python -m some_module`, so sys.argv is "wrong." Fix it.
            command += ['-m', self.main_module_name]
            command += sys.argv[1:]
        else:
            # The server was started with /path/to/file.py, so sys.argv is "right."
            command += sys.argv
        new_environment = os.environ.copy()
        new_environment['RUN_RELOADER_MAIN'] = 'true'

        while True:
            # We don't want these signals to actually kill this process; just sub-processes
            signal.signal(signal.SIGINT, signal.SIG_IGN)
            signal.signal(signal.SIGTERM, signal.SIG_IGN)

            exit_code = subprocess.call(command, env=new_environment)
            if exit_code != NEED_RELOAD_EXIT_CODE:
                return exit_code

    def watch_and_reload(self, func, args, kwargs):
        """
        This is what gets the watching process started. In order to monitor for changes and control process restarts,
        we actually need to start the entire server process from the watcher. But the server process has already
        started. So, if this is the original server process (environment variable `RUN_RELOADER_MAIN` is not set), we
        call `restart_with_reloader` to actually start the server process again with files watched. If this is the
        restarted server process (environment variable `RUN_RELOADER_MAIN` _is_ set), then we start the reloading loop.

        The original started process does not die. It continues running until `restart_with_reloader` returns, which
        doesn't happen until the restarted (child) server process exits with a code other than `NEED_RELOAD_EXIT_CODE`.

        :param func: The main program execution function, usually something like ExampleServer.main
        :param args: The positional arguments that should be passed to the main program execution function
        :param kwargs: The keyword arguments that should be passed to the main program execution function
        """
        if os.environ.get('RUN_RELOADER_MAIN') == 'true':
            thread = threading.Thread(target=self.watch_files)
            thread.daemon = True  # we don't want this thread to stop the program from exiting
            thread.start()

            try:
                func(*args, **kwargs)
            except KeyboardInterrupt:
                pass
            except BaseException:
                self.stop_watching()
                raise

            self.stop_watching()
            if self.shutting_down_for_reload:
                sys.exit(NEED_RELOAD_EXIT_CODE)  # server process shut down because the reloader asked it to
            else:
                sys.exit(0)  # server process terminated naturally
        else:
            try:
                exit_code = self.restart_with_reloader()
                if exit_code < 0:
                    # Python docs say: A negative exit code -N indicates that the child was terminated by signal N.
                    os.kill(os.getpid(), -exit_code)
                else:
                    sys.exit(exit_code)
            except KeyboardInterrupt:
                pass

    def main(self, func, args=None, kwargs=None):
        """
        This is the method that all consumers of the reloader should call. Pass it the main program execution function,
        along with the args and kwargs that should be passed to the main program execution function, and it will
        supervise the execution of the main program function and watch for file changes. It will then restart the
        process if any file changes occur. See the documentation for the other methods to understand how this work in
        more detail.

        :param func: The main program execution function, usually something like ExampleServer.main
        :param args: The positional arguments that should be passed to the main program execution function
        :param kwargs: The keyword arguments that should be passed to the main program execution function
        """
        if args is None:
            args = ()
        if kwargs is None:
            kwargs = {}

        self.watch_and_reload(func, args, kwargs)


class _PyInotifyReloader(AbstractReloader):
    """
    This concrete class completes the reloader by using the PyInotify API. It is only supported on Linux operating
    systems with kernel version >= 2.6.13.
    """

    def __init__(self, main_module_name, watch_modules, signal_forks=False):
        self.notifier = None
        super(_PyInotifyReloader, self).__init__(main_module_name, watch_modules, signal_forks)

    def code_changed(self):
        notify_mask = (
            pyinotify.IN_MODIFY |
            pyinotify.IN_DELETE |
            pyinotify.IN_ATTRIB |
            pyinotify.IN_MOVED_FROM |
            pyinotify.IN_MOVED_TO |
            pyinotify.IN_CREATE |
            pyinotify.IN_DELETE_SELF |
            pyinotify.IN_MOVE_SELF
        )

        class EventHandler(pyinotify.ProcessEvent):
            def process_default(self, event):
                pass

        watch_manager = pyinotify.WatchManager()
        self.notifier = pyinotify.Notifier(watch_manager, EventHandler())

        file_names = self.get_watch_file_names(only_new=True)

        for file_name in file_names:
            watch_manager.add_watch(file_name, notify_mask)

        self.notifier.check_events(timeout=None)
        if self.watching:
            self.notifier.read_events()
            self.notifier.process_events()
            self.notifier.stop()
            self.notifier = None

            # If we are here, then one or more files must have changed
            return True

        return False

    def stop_watching(self):
        if self.watching:
            # The first time this is called, stop the notifier
            super(_PyInotifyReloader, self).stop_watching()
            if self.notifier:
                self.notifier.stop()
                self.notifier = None
        else:
            super(_PyInotifyReloader, self).stop_watching()


class _PollingReloader(AbstractReloader):
    """
    This concrete class completes the reloader by polling the last-modified time stat for every file being watched. It
    is not as fast as the PyInotify reloader in large applications, but it is supported on all operating systems.
    """
    is_windows = sys.platform == 'win32'

    def __init__(self, main_module_name, watch_modules, signal_forks=False):
        self.modified_times = {}
        super(_PollingReloader, self).__init__(main_module_name, watch_modules, signal_forks)

    def code_changed(self):
        file_names = self.get_watch_file_names()
        for file_name in file_names:
            stat = os.stat(file_name)
            modified_time = stat.st_mtime
            if self.is_windows:
                modified_time -= stat.st_ctime

            if file_name not in self.modified_times:
                self.modified_times[file_name] = modified_time
                continue

            if modified_time != self.modified_times[file_name]:
                self.modified_times = {}
                return True

        return False


def get_reloader(main_module_name, watch_modules, signal_forks=False):
    """
    Don't instantiate a reloader directly. Instead, call this method to get a reloader, and then call `main` on that
    reloader.

    See the documentation for `AbstractReloader.main` above to see how to call it.

    :param main_module_name: The main module name (such as "example_service.standalone"). It should be the value
                             that was passed to the `-m` parameter when starting the Python executable, or `None`
                             if the `-m` parameter was not used.
    :param watch_modules: If passed an iterable/generator of module names, file watching will be limited to modules
                          whose names start with one of these names (including their submodules). For example,
                          if passed `['example', 'pysoa']`, it will monitor all of PySOA's modules and submodules
                          and all of `example_service`'s modules and submodules, as well as any other modules that
                          start with `example`. If `None`, all files from all modules in all libraries, including
                          Python, will be watched.
    :param signal_forks: If `True`, this means the server process is actually multiprocessing/forking and its child
                         processes are the actual server processes. In this case, the file watcher also sends
                         `SIGHUP` in addition to `SIGTERM` to the clone process, and the clone process receives
                         this and knows to send `SIGTERM` to all of its forked child processes.
    :return: a new reloader instance.
    """
    if USE_PY_INOTIFY:
        return _PyInotifyReloader(main_module_name, watch_modules, signal_forks)
    return _PollingReloader(main_module_name, watch_modules, signal_forks)
