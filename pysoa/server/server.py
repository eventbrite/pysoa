from __future__ import absolute_import, unicode_literals

import argparse
import importlib
import logging
import logging.config
import os
import sys
import traceback
import signal

import attr
import six

from pysoa.client import Client
from pysoa.common.constants import (
    ERROR_CODE_RESPONSE_NOT_SERIALIZABLE,
    ERROR_CODE_RESPONSE_TOO_LARGE,
    ERROR_CODE_SERVER_ERROR,
    ERROR_CODE_UNKNOWN,
)
from pysoa.common.serializer.exceptions import InvalidField
from pysoa.common.transport.exceptions import (
    MessageReceiveError,
    MessageReceiveTimeout,
    MessageTooLarge,
)
from pysoa.common.types import (
    ActionResponse,
    Error,
    JobResponse,
    UnicodeKeysDict,
)
from pysoa.server.internal.types import RequestSwitchSet
from pysoa.server.errors import (
    ActionError,
    JobError,
)
from pysoa.server.logging import (
    PySOALogContextFilter,
    RecursivelyCensoredDictWrapper,
)
from pysoa.server.types import EnrichedActionRequest
from pysoa.server.schemas import JobRequestSchema
from pysoa.server.settings import PolymorphicServerSettings
import pysoa.version


class Server(object):
    """
    The base class from which all PySOA service servers inherit, and contains the code that does all of the heavy
    lifting for receiving and handling requests, passing those requests off to the relevant actions, and sending
    the actions' responses back to the caller.

    Required attributes that all concrete subclasses must provide:

    - `service_name`: A (unicode) string name of the service.
    - `action_class_map`: An object supporting `__contains__` and `__getitem__` (typically a `dict`) whose keys are
      action names and whose values are callable objects that return a callable action when called (such as subclasses
      of `Action` which, when "called" [constructed], yield a callable object [instance of the subclass])
    """

    settings_class = PolymorphicServerSettings

    use_django = False
    service_name = None
    action_class_map = {}

    def __init__(self, settings):
        """
        :param settings: The settings object, which must be an instance of `ServerSettings` or one of its subclasses
        :type settings: ServerSettings
        """
        # Check subclassing setup
        if not self.service_name:
            raise AttributeError('Server subclass must set service_name')

        # Store settings and extract transport
        self.settings = settings
        self.metrics = self.settings['metrics']['object'](**self.settings['metrics'].get('kwargs', {}))
        self.transport = self.settings['transport']['object'](
            self.service_name,
            self.metrics,
            **self.settings['transport'].get('kwargs', {})
        )

        # Set initial state
        self.shutting_down = False

        # Instantiate middleware
        self.middleware = [
            m['object'](**m.get('kwargs', {}))
            for m in self.settings['middleware']
        ]

        # Set up logger
        self.logger = logging.getLogger('pysoa.server')
        self.job_logger = logging.getLogger('pysoa.server.job')

        # Set these as the integer equivalents of the level names
        self.request_log_success_level = logging.getLevelName(self.settings['request_log_success_level'])
        self.request_log_error_level = logging.getLevelName(self.settings['request_log_error_level'])

        self._default_status_action_class = None

        self._idle_timer = None

    def handle_next_request(self):
        """
        Retrieves the next request from the transport, or returns if it times out (no request has been made), and then
        processes that request, sends its response, and returns when done.
        """
        if not self._idle_timer:
            # This method may be called multiple times before receiving a request, so we only create and start a timer
            # if it's the first call or if the idle timer was stopped on the last call.
            self._idle_timer = self.metrics.timer('server.idle_time')
            self._idle_timer.start()

        # Get the next JobRequest
        try:
            request_id, meta, job_request = self.transport.receive_request_message()
        except MessageReceiveTimeout:
            # no new message, nothing to do
            self.perform_idle_actions()
            return

        # We are no longer idle, so stop the timer and reset for the next idle period
        self._idle_timer.stop()
        self._idle_timer = None

        PySOALogContextFilter.set_logging_request_context(request_id=request_id, **job_request['context'])

        request_for_logging = RecursivelyCensoredDictWrapper(job_request)
        self.job_logger.log(self.request_log_success_level, 'Job request: %s', request_for_logging)

        try:
            self.perform_pre_request_actions()

            # Process and run the Job
            job_response = self.process_job(job_request)

            # Prepare the JobResponse for sending by converting it to a message dict
            try:
                response_message = attr.asdict(job_response, dict_factory=UnicodeKeysDict)
            except Exception as e:
                self.metrics.counter('server.error.response_conversion_failure').increment()
                job_response = self.handle_job_exception(e, variables={'job_response': job_response})
                response_message = attr.asdict(job_response, dict_factory=UnicodeKeysDict)

            response_for_logging = RecursivelyCensoredDictWrapper(response_message)

            # Send the response message
            try:
                self.transport.send_response_message(request_id, meta, response_message)
            except MessageTooLarge:
                self.metrics.counter('server.error.response_too_large').increment()
                job_response = self.handle_job_error_code(
                    ERROR_CODE_RESPONSE_TOO_LARGE,
                    'Could not send the response because it was too large',
                    request_for_logging,
                    response_for_logging,
                )
                self.transport.send_response_message(
                    request_id,
                    meta,
                    attr.asdict(job_response, dict_factory=UnicodeKeysDict),
                )
            except InvalidField:
                self.metrics.counter('server.error.response_not_serializable').increment()
                job_response = self.handle_job_error_code(
                    ERROR_CODE_RESPONSE_NOT_SERIALIZABLE,
                    'Could not send the response because it failed to serialize',
                    request_for_logging,
                    response_for_logging,
                )
                self.transport.send_response_message(
                    request_id,
                    meta,
                    attr.asdict(job_response, dict_factory=UnicodeKeysDict),
                )
            finally:
                if job_response.errors or any(a.errors for a in job_response.actions):
                    if (
                        self.request_log_error_level > self.request_log_success_level and
                        self.job_logger.getEffectiveLevel() > self.request_log_success_level
                    ):
                        # When we originally logged the request, it may have been hidden because the effective logging
                        # level threshold was greater than the level at which we logged the request. So re-log the
                        # request at the error level, if set higher.
                        self.job_logger.log(self.request_log_error_level, 'Job request: %s', request_for_logging)
                    self.job_logger.log(self.request_log_error_level, 'Job response: %s', response_for_logging)
                else:
                    self.job_logger.log(self.request_log_success_level, 'Job response: %s', response_for_logging)
        finally:
            PySOALogContextFilter.clear_logging_request_context()
            self.perform_post_request_actions()

    def make_client(self, context):
        """
        Gets a `Client` that will propagate the passed `context` in order to to pass it down to middleware or Actions.

        :return: A client configured with this server's `client_routing` settings
        :rtype: Client
        """
        return Client(self.settings['client_routing'], context=context)

    @staticmethod
    def make_middleware_stack(middleware, base):
        """
        Given a list of in-order middleware callable objects `middleware` and a base function `base`, chains them
        together so each middleware is fed the function below, and returns the top level ready to call.

        :param middleware: The middleware stack
        :type middleware: iterable[callable]
        :param base: The base callable that the lowest-order middleware wraps
        :type base: callable

        :return: The topmost middleware, which calls the next middleware ... which calls the lowest-order middleware,
                 which calls the `base` callable.
        :rtype: callable
        """
        for ware in reversed(middleware):
            base = ware(base)
        return base

    def process_job(self, job_request):
        """
        Validate, execute, and run the job request, wrapping it with any applicable job middleware.

        :param job_request: The job request
        :type job_request: dict

        :return: A `JobResponse` object
        :rtype: JobResponse

        :raise: JobError
        """

        try:
            # Validate JobRequest message
            validation_errors = [
                Error(
                    code=error.code,
                    message=error.message,
                    field=error.pointer,
                )
                for error in (JobRequestSchema.errors(job_request) or [])
            ]
            if validation_errors:
                raise JobError(errors=validation_errors)

            # Add a client router in case a middleware wishes to use it
            job_request['client'] = self.make_client(job_request['context'])

            # Build set of middleware + job handler, then run job
            wrapper = self.make_middleware_stack(
                [m.job for m in self.middleware],
                self.execute_job,
            )
            job_response = wrapper(job_request)
        except JobError as e:
            self.metrics.counter('server.error.job_error').increment()
            job_response = JobResponse(
                errors=e.errors,
            )
        except Exception as e:
            # Send an error response if no middleware caught this.
            # Formatting the error might itself error, so try to catch that
            self.metrics.counter('server.error.unhandled_error').increment()
            return self.handle_job_exception(e)

        return job_response

    def handle_job_exception(self, exception, variables=None):
        """
        Makes and returns a last-ditch error response.

        :param exception: The exception that happened
        :type exception: Exception
        :param variables: A dictionary of context-relevant variables to include in the error response
        :type variables: dict

        :return: A `JobResponse` object
        :rtype: JobResponse
        """
        # Get the error and traceback if we can
        try:
            error_str, traceback_str = six.text_type(exception), traceback.format_exc()
        except Exception:
            self.metrics.counter('server.error.error_formatting_failure').increment()
            error_str, traceback_str = 'Error formatting error', traceback.format_exc()
        # Log what happened
        self.logger.exception(exception)
        if not isinstance(traceback_str, six.text_type):
            try:
                # Try to
                traceback_str = traceback_str.decode('utf-8')
            except UnicodeDecodeError:
                traceback_str = 'UnicodeDecodeError: Traceback could not be decoded'
        # Make a bare bones job response
        error_dict = {
            'code': ERROR_CODE_SERVER_ERROR,
            'message': 'Internal server error: %s' % error_str,
            'traceback': traceback_str,
        }

        if variables is not None:
            try:
                error_dict['variables'] = {key: repr(value) for key, value in variables.items()}
            except Exception:
                self.metrics.counter('server.error.variable_formatting_failure').increment()
                error_dict['variables'] = 'Error formatting variables'

        return JobResponse(errors=[error_dict])

    def handle_job_error_code(self, code, message, request_for_logging, response_for_logging):
        self.logger.error(
            message,
            exc_info=True,
            extra={'data': {'request': request_for_logging, 'response': response_for_logging}},
        )
        return JobResponse(errors=[Error(code=code, message=message)])

    def execute_job(self, job_request):
        """
        Processes and runs the action requests contained in the job and returns a `JobResponse`.

        :param job_request: The job request
        :type job_request: dict

        :return: A `JobResponse` object
        :rtype: JobResponse
        """
        # Run the Job's Actions
        job_response = JobResponse()
        job_switches = RequestSwitchSet(job_request['context']['switches'])
        for i, raw_action_request in enumerate(job_request['actions']):
            action_request = EnrichedActionRequest(
                action=raw_action_request['action'],
                body=raw_action_request.get('body', None),
                switches=job_switches,
                context=job_request['context'],
                control=job_request['control'],
                client=job_request['client'],
            )
            action_in_class_map = action_request.action in self.action_class_map
            if action_in_class_map or action_request.action in ('status', 'introspect'):
                # Get action to run
                if action_in_class_map:
                    action = self.action_class_map[action_request.action](self.settings)
                elif action_request.action == 'introspect':
                    from pysoa.server.action.introspection import IntrospectionAction
                    action = IntrospectionAction(server=self)
                else:
                    if not self._default_status_action_class:
                        from pysoa.server.action.status import make_default_status_action_class
                        self._default_status_action_class = make_default_status_action_class(self.__class__)
                    action = self._default_status_action_class(self.settings)
                # Wrap it in middleware
                wrapper = self.make_middleware_stack(
                    [m.action for m in self.middleware],
                    action,
                )
                # Execute the middleware stack
                try:
                    action_response = wrapper(action_request)
                except ActionError as e:
                    # Error: an error was thrown while running the Action (or Action middleware)
                    action_response = ActionResponse(
                        action=action_request.action,
                        errors=e.errors,
                    )
            else:
                # Error: Action not found.
                action_response = ActionResponse(
                    action=action_request.action,
                    errors=[Error(
                        code=ERROR_CODE_UNKNOWN,
                        message='The action "{}" was not found on this server.'.format(action_request.action),
                        field='action',
                    )],
                )

            job_response.actions.append(action_response)
            if (
                action_response.errors and
                not job_request['control'].get('continue_on_error', False)
            ):
                # Quit running Actions if an error occurred and continue_on_error is False
                break

        return job_response

    def handle_shutdown_signal(self, *_):
        """
        Handles the reception of a shutdown signal.
        """
        if self.shutting_down:
            self.logger.warning('Received double interrupt, forcing shutdown')
            sys.exit(1)
        else:
            self.logger.warning('Received interrupt, initiating shutdown')
            self.shutting_down = True

    def harakiri(self, *_):
        """
        Handles the reception of a timeout signal indicating that a request has been processing for too long, as
        defined by the Harakiri settings.
        """
        if self.shutting_down:
            self.logger.warning('Graceful shutdown failed after {}s. Exiting now!'.format(
                self.settings['harakiri']['shutdown_grace']
            ))
            sys.exit(1)
        else:
            self.logger.warning('No activity during {}s, triggering harakiri with grace {}s'.format(
                self.settings['harakiri']['timeout'],
                self.settings['harakiri']['shutdown_grace'],
            ))
            self.shutting_down = True
            signal.alarm(self.settings['harakiri']['shutdown_grace'])

    def setup(self):
        """
        Runs just before the server starts, if you need to do one-time loads or cache warming. Call super().setup() if
        you override. See the documentation for `Server.main` for full details on the chain of `Server` method calls.
        """

    def _close_old_django_connections(self):
        if self.use_django:
            from django.conf import settings
            if not getattr(settings, 'DATABASES'):
                # No database connections are configured, so we have nothing to do
                return

            from django.db import transaction
            try:
                if transaction.get_autocommit():
                    from django.db import close_old_connections
                    self.logger.debug('Cleaning Django connections')
                    close_old_connections()
            except BaseException as e:
                # `get_autocommit` fails under PyTest without `pytest.mark.django_db`, so ignore that specific error.
                try:
                    from _pytest.outcomes import Failed
                    if not isinstance(e, Failed):
                        raise e
                except ImportError:
                    raise e

    def perform_pre_request_actions(self):
        """
        Runs just before the server accepts a new request. Call super().perform_pre_request_actions() if you override.
        Be sure your purpose for overriding isn't better met with middleware. See the documentation for `Server.main`
        for full details on the chain of `Server` method calls.
        """
        if self.use_django:
            from django.conf import settings
            if getattr(settings, 'DATABASES'):
                from django.db import reset_queries
                self.logger.debug('Resetting Django query log')
                reset_queries()

        self._close_old_django_connections()

    def perform_post_request_actions(self):
        """
        Runs just after the server processes a request. Call super().perform_post_request_actions() if you override. Be
        sure your purpose for overriding isn't better met with middleware. See the documentation for `Server.main` for
        full details on the chain of `Server` method calls.
        """
        self._close_old_django_connections()

    def perform_idle_actions(self):
        """
        Runs periodically when the server is idle, if it has been too long since it last received a request. Call
        super().perform_idle_actions() if you override. See the documentation for `Server.main` for full details on the
        chain of `Server` method calls.
        """
        self._close_old_django_connections()

    def run(self):
        """
        Starts the server run loop and returns after the server shuts down due to a shutdown-request, Harakiri signal,
        or unhandled exception. See the documentation for `Server.main` for full details on the chain of `Server`
        method calls.
        """

        self.logger.info(
            'Service "{service}" server starting up, pysoa version {pysoa}, listening on transport {transport}.'.format(
                service=self.service_name,
                pysoa=pysoa.version.__version__,
                transport=self.transport,
            )
        )
        self.setup()
        self.metrics.commit()

        signal.signal(signal.SIGINT, self.handle_shutdown_signal)
        signal.signal(signal.SIGTERM, self.handle_shutdown_signal)
        signal.signal(signal.SIGALRM, self.harakiri)

        try:
            while not self.shutting_down:
                # reset harakiri timeout
                signal.alarm(self.settings['harakiri']['timeout'])
                # Get, process, and execute the next JobRequest
                self.handle_next_request()
                self.metrics.commit()
        except MessageReceiveError:
            self.logger.exception('Error receiving message from transport; shutting down')
        except Exception:
            self.metrics.counter('server.error.unknown').increment()
            self.logger.exception('Unhandled server error; shutting down')
        finally:
            self.metrics.commit()
            self.logger.info('Server shutting down')

    # noinspection PyUnusedLocal
    @classmethod
    def initialize(cls, settings):
        """
        Called just before the `Server` class is instantiated, and passed the settings dict. Can be used to perform
        settings manipulation, server class patching (such as for performance tracing operations), and more. Use with
        great care and caution. Overriding methods must call `super` and return `cls` or a new/modified `cls`, which
        will be used to instantiate the server. See the documentation for `Server.main` for full details on the chain
        of `Server` method calls.

        :return: The server class or a new/modified server class
        :rtype: type
        """
        return cls

    @classmethod
    def main(cls):
        """
        Command-line entry point for running a PySOA server. The chain of method calls is as follows::

            cls.main
              |
              -> cls.initialize => new_cls
              -> new_cls.__init__ => self
              -> self.run
                  |
                  -> self.setup
                  -> loop: self.handle_next_request while not self.shutting_down
                            |
                            -> transport.receive_request_message
                            -> self.perform_idle_actions (if no request)
                            -> self.perform_pre_request_actions
                            -> self.process_job
                                |
                                -> middleware(self.execute_job)
                            -> transport.send_response_message
                            -> self.perform_post_request_actions
        """
        parser = argparse.ArgumentParser(
            description='Server for the {} SOA service'.format(cls.service_name),
        )
        parser.add_argument(
            '-d', '--daemon',
            action='store_true',
            help='run the server process as a daemon',
        )
        if not cls.use_django:
            # If Django mode is turned on, we use the Django settings framework to get our settings, so the caller
            # needs to set DJANGO_SETTINGS_MODULE. Otherwise, the caller must pass in the -s/--settings argument.
            parser.add_argument(
                '-s', '--settings',
                help='The settings module to use',
                required=True,
            )
        cmd_options, _ = parser.parse_known_args(sys.argv[1:])

        # Load settings from the given file (or use Django and grab from its settings)
        if cls.use_django:
            # noinspection PyUnresolvedReferences
            from django.conf import settings as django_settings
            try:
                settings = cls.settings_class(django_settings.SOA_SERVER_SETTINGS)
            except AttributeError:
                raise ValueError('Cannot find SOA_SERVER_SETTINGS in the Django settings')
        else:
            try:
                settings_module = importlib.import_module(cmd_options.settings)
            except ImportError as e:
                raise ValueError('Cannot import settings module %s: %s' % (cmd_options.settings, e))
            try:
                settings_dict = getattr(settings_module, 'SOA_SERVER_SETTINGS')
            except AttributeError:
                try:
                    settings_dict = getattr(settings_module, 'settings')
                except AttributeError:
                    raise ValueError(
                        "Cannot find 'SOA_SERVER_SETTINGS' or 'settings' variable in settings module {}.".format(
                            cmd_options.settings,
                        )
                    )
            settings = cls.settings_class(settings_dict)

        PySOALogContextFilter.set_service_name(cls.service_name)

        # Set up logging
        logging.config.dictConfig(settings['logging'])

        # Optionally daemonize
        if cmd_options.daemon:
            pid = os.fork()
            if pid > 0:
                print('PID={}'.format(pid))
                sys.exit()

        # Set up server and signal handling
        server = cls.initialize(settings)(settings)

        # Start server event loop
        server.run()
