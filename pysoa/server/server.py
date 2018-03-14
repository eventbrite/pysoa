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
from pysoa.client import Client
from pysoa.common.constants import (
    ERROR_CODE_INVALID,
    ERROR_CODE_SERVER_ERROR,
    ERROR_CODE_UNKNOWN,
)
from pysoa.common.transport.exceptions import (
    MessageReceiveError,
    MessageReceiveTimeout,
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
    Base class from which all SOA Service Servers inherit.

    Required Attributes for Subclasses:
        service_name: a string name of the service.
        action_class_map: a dictionary mapping action name strings
            to Action subclasses.
    """

    settings_class = PolymorphicServerSettings

    use_django = False
    service_name = None
    action_class_map = {}

    def __init__(self, settings):
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

    def handle_next_request(self):
        # Get the next JobRequest
        try:
            request_id, meta, job_request = self.transport.receive_request_message()
        except MessageReceiveTimeout:
            # no new message, nothing to do
            self.perform_idle_actions()
            return
        PySOALogContextFilter.set_logging_request_context(request_id=request_id, **job_request['context'])

        request_for_logging = RecursivelyCensoredDictWrapper(job_request)
        self.job_logger.log(self.request_log_success_level, 'Job request: %s', request_for_logging)

        try:
            self.perform_pre_request_actions()

            # Process and run the Job
            job_response = self.process_job(job_request)

            # Send the JobResponse
            try:
                response_message = attr.asdict(job_response, dict_factory=UnicodeKeysDict)
            except Exception as e:
                self.metrics.counter('server.error.response_conversion_failure').increment()
                job_response = self.handle_error(e, variables={'job_response': job_response})
                response_message = attr.asdict(job_response, dict_factory=UnicodeKeysDict)
            self.transport.send_response_message(request_id, meta, response_message)

            response_for_logging = RecursivelyCensoredDictWrapper(response_message)

            if job_response.errors or any(a.errors for a in job_response.actions):
                if (
                    self.request_log_error_level > self.request_log_success_level and
                    self.job_logger.getEffectiveLevel() > self.request_log_success_level
                ):
                    # When we originally logged the request, it may have been hidden because the effective logging level
                    # threshold was greater than the level at which we logged the request. So re-log the request at the
                    # error level, if set higher.
                    self.job_logger.log(self.request_log_error_level, 'Job request: %s', request_for_logging)
                self.job_logger.log(self.request_log_error_level, 'Job response: %s', response_for_logging)
            else:
                self.job_logger.log(self.request_log_success_level, 'Job response: %s', response_for_logging)
        finally:
            PySOALogContextFilter.clear_logging_request_context()
            self.perform_post_request_actions()

    def make_client(self, context):
        """
        Gets a client router to pass down to middleware or Actions that will
        propagate the passed `context`.
        """
        return Client(self.settings['client_routing'], context=context)

    @staticmethod
    def make_middleware_stack(middleware, base):
        """
        Given a list of in-order middleware callables `middleware`
        and a base function `base`, chains them together so each middleware is
        fed the function below, and returns the top level ready to call.
        """
        for ware in reversed(middleware):
            base = ware(base)
        return base

    def process_job(self, job_request):
        """
        Validate, execute, and run Job-level middleware for JobRequests.

        Args:
            job_request: a JobRequest dictionary.
        Returns:
            A JobResponse instance.
        """

        try:
            # Validate JobRequest message
            validation_errors = [
                Error(
                    code=ERROR_CODE_INVALID,
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
            return self.handle_error(e)

        return job_response

    def handle_error(self, error, variables=None):
        """
        Makes a last-ditch error response
        """
        # Get the error and traceback if we can
        try:
            error_str, traceback_str = str(error), traceback.format_exc()
        except Exception:
            self.metrics.counter('server.error.error_formatting_failure').increment()
            error_str, traceback_str = 'Error formatting error', traceback.format_exc()
        # Log what happened
        self.logger.exception(error)
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
        job_response = JobResponse(errors=[error_dict])
        return job_response

    def execute_job(self, job_request):
        """
        Processes and runs the ActionRequests on the Job.
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
        if self.shutting_down:
            self.logger.warning('Received double interrupt, forcing shutdown')
            sys.exit(1)
        else:
            self.logger.warning('Received interrupt, initiating shutdown')
            self.shutting_down = True

    def harakiri(self, *_):
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
        you override.
        """
        pass

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
        Be sure your purpose for overriding isn't better met with middleware.
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
        sure your purpose for overriding isn't better met with middleware.
        """
        self._close_old_django_connections()

    def perform_idle_actions(self):
        """
        Runs periodically when the server is idle, if it has been too long since it last received a request. Call
        super().perform_idle_actions() if you override.
        """
        self._close_old_django_connections()

    def run(self):
        """
        Start the SOA Server run loop.
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

    @classmethod
    def main(cls):
        """
        Command-line entry point for running a PySOA service Server.
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
            # If Django mode is turned on, we use the Django settings framework
            # to get our settings, so the caller needs to set DJANGO_SETTINGS_MODULE.
            parser.add_argument(
                '-s', '--settings',
                help='The settings file to use',
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

        # Set up logging
        logging.config.dictConfig(settings['logging'])

        # Optionally daemonize
        if cmd_options.daemon:
            pid = os.fork()
            if pid > 0:
                print('PID={}'.format(pid))
                sys.exit()

        # Set up server and signal handling
        server = cls(settings)

        # Start server event loop
        server.run()
