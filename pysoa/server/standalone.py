from __future__ import (
    absolute_import,
    unicode_literals,
)

import importlib
import logging
import sys


__all__ = (
    'django_main',
    'simple_main',
)


if sys.path[0] and not sys.path[0].endswith('/bin'):
    # When Python is invoked using `python -m some_module`, the first item in the path is always empty
    # When Python is invoked using an entry-point binary, the first item in the path is a /bin folder somewhere
    # When Python is invoked using `python /path/to/file.py`, the first item in the path is `/path/to`, which is bad
    print(
        'ERROR: You have triggered a double-import trap (see '
        'http://python-notes.curiousefficiency.org/en/latest/python_concepts/import_traps.html#the-double-import-trap '
        'for more information on what this is). In short, you cannot start this service with '
        '`python /path/to/standalone.py`, because that puts all the modules in this service on the path as top-level '
        'modules, potentially masking builtins and breaking all sorts of things with hard-to-diagnose errors. Instead, '
        'you must start this service with `python -m module.to.standalone` or by simply calling the `service_name` '
        'entry point executable.'
    )
    exit(99)


def _get_arg_parser():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-f', '--fork-processes', '--fork',
        help='The number of processes to fork (if 0, 1, or none, no process is forked; the server is run directly)',
        required=False,
        type=int,
        default=0,
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


def _get_args(parser):
    return parser.parse_known_args()[0]


def _run_server(args, server_class):
    if args.fork_processes > 1:
        import multiprocessing
        import signal
        import time

        cpu_count = multiprocessing.cpu_count()
        num_processes = args.fork_processes
        max_processes = cpu_count * 5
        if num_processes > max_processes:
            print(
                'WARNING: Number of requested process forks ({forks}) is greater than five times the number of CPU '
                'cores available ({cores} cores). Capping number of forks at {cap}.'.format(
                    forks=args.fork_processes,
                    cores=cpu_count,
                    cap=max_processes,
                )
            )
            num_processes = max_processes

        processes = []

        def _sigterm_forks(*_, **__):
            for process in processes:
                process.terminate()

        # We don't want these signals to actually kill this process; just sub-processes
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        signal.signal(signal.SIGHUP, _sigterm_forks)  # special signal by reloader says we actually need to propagate

        processes = [
            multiprocessing.Process(target=server_class.main, name='pysoa-worker-{}'.format(i), args=(i + 1, ))
            for i in range(0, num_processes)
        ]
        for p in processes:
            p.start()

        time.sleep(1)

        for p in processes:
            p.join()
    else:
        server_class.main()


def _run_server_reloader_wrapper(args, server_class):
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
        module_name = None
        if hasattr(__main__, '__loader__'):
            module_name = getattr(__main__.__loader__, 'name', None) or getattr(__main__.__loader__, 'fullname', None)
        if module_name == '__main__':
            # If the name is still __main__, this means Python was called without the -m
            module_name = ''

        from pysoa.server import autoreload
        autoreload.get_reloader(
            module_name or '',
            args.use_file_watcher,
            signal_forks=args.fork_processes > 1
        ).main(
            _run_server,
            (args, server_class),
        )


def simple_main(server_getter):
    """
    Call this within `__main__` to start the service as a standalone server without Django support. Your server should
    not have `use_django=True`. If it does, see `django_main`, instead.

    :param server_getter: A callable that returns the service's `Server` class (not an instance of it)
    """
    _run_server_reloader_wrapper(_get_args(_get_arg_parser()), server_getter())


def django_main(server_getter):
    """
    Call this within `__main__` to start the service as a standalone server with Django support. Your server should have
    `use_django=True`. If it does not, see `simple_main`, instead.

    :param server_getter: A callable that returns the service's `Server` class (not an instance of it). Your service
                          code should not be imported until the `server_getter` callable is called, otherwise Django
                          errors will occur.
    """
    import os
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
        if (
            getattr(django_settings, 'LOGGING', None) and
            django_settings.LOGGING != django_settings.SOA_SERVER_SETTINGS['logging']
        ):
            warn_about_logging = True
        django_settings.LOGGING = django_settings.SOA_SERVER_SETTINGS['logging']
    except ImportError:
        raise ValueError('Cannot import Django settings module `{}`.'.format(os.environ['DJANGO_SETTINGS_MODULE']))
    except AttributeError:
        raise ValueError('Cannot find `SOA_SERVER_SETTINGS` in the Django settings module.')
    except KeyError:
        raise ValueError(
            "Cannot configure Django `LOGGING` setting because no setting `SOA_SERVER_SETTINGS['logging']` was found.",
        )

    if django.VERSION >= (1, 7):
        django.setup()

    if warn_about_logging:
        logging.warning(
            "Django setting `LOGGING` differs from `SOA_SERVER_SETTINGS['logging']` and has been overwritten with "
            "the value of `SOA_SERVER_SETTINGS['logging']`."
        )

    _run_server_reloader_wrapper(args, server_getter())
