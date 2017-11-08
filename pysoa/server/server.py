from __future__ import unicode_literals

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
from pysoa.common.transport.exceptions import MessageReceiveTimeout
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
from pysoa.server.types import EnrichedActionRequest
from pysoa.server.schemas import JobRequestSchema
from pysoa.server.settings import PolymorphicServerSettings


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

        # Store settings and extract serializer and transport
        self.settings = settings
        self.metrics = self.settings['metrics']['object'](**self.settings['metrics'].get('kwargs', {}))
        self.transport = self.settings['transport']['object'](
            self.service_name,
            self.metrics,
            **self.settings['transport'].get('kwargs', {})
        )
        self.serializer = self.settings['serializer']['object'](
            **self.settings['serializer'].get('kwargs', {})
        )

        # Set initial state
        self.shutting_down = False

        # Instantiate middleware
        self.middleware = [
            m['object'](**m.get('kwargs', {}))
            for m in self.settings['middleware']
        ]

        # Set up logger
        self.logger = logging.getLogger("pysoa.server")
        self.job_logger = logging.getLogger("pysoa.server.job")

    def handle_next_request(self):
        # Get the next JobRequest
        try:
            request_id, meta, request_message = self.transport.receive_request_message()
        except MessageReceiveTimeout:
            # no new message, nothing to do
            return
        job_request = self.serializer.blob_to_dict(request_message)
        self.job_logger.info("Job request: %s", job_request)

        # Process and run the Job
        job_response = self.process_job(job_request)

        # Send the JobResponse
        response_dict = {}
        try:
            response_dict = attr.asdict(job_response, dict_factory=UnicodeKeysDict)
            response_message = self.serializer.dict_to_blob(response_dict)
        except Exception as e:
            self.metrics.counter('server.error.serialization_failure').increment()
            job_response = self.handle_error(e, variables={'job_response': response_dict})
            response_dict = attr.asdict(job_response, dict_factory=UnicodeKeysDict)
            response_message = self.serializer.dict_to_blob(response_dict)
        self.transport.send_response_message(request_id, meta, response_message)
        self.job_logger.info("Job response: %s", response_dict)

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
            error_str, traceback_str = "Error formatting error", traceback.format_exc()
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
            if action_request.action in self.action_class_map:
                # Get action to run
                action = self.action_class_map[action_request.action](self.settings)
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
            self.logger.warning("Received double interrupt, forcing shutdown")
            sys.exit(1)
        else:
            self.logger.warning("Received interrupt, initiating shutdown")
            self.shutting_down = True

    def harakiri(self, *_):
        if self.shutting_down:
            self.logger.warning("Graceful shutdown failed after {}s. Exiting now!".format(
                self.settings["harakiri"]["shutdown_grace"]
            ))
            sys.exit(1)
        else:
            self.logger.warning("No activity during {}s, triggering harakiri with grace {}s".format(
                self.settings["harakiri"]["timeout"],
                self.settings["harakiri"]["shutdown_grace"],
            ))
            self.shutting_down = True
            signal.alarm(self.settings["harakiri"]["shutdown_grace"])

    def setup(self):
        """
        Runs just before the server starts, if you need to do one-time loads or
        cache warming.
        """
        pass

    def run(self):
        """
        Start the SOA Server run loop.
        """

        self.logger.info("Server starting up, listening on %s", self.transport)
        self.setup()

        signal.signal(signal.SIGINT, self.handle_shutdown_signal)
        signal.signal(signal.SIGTERM, self.handle_shutdown_signal)
        signal.signal(signal.SIGALRM, self.harakiri)

        try:
            while not self.shutting_down:
                # reset harakiri timeout
                signal.alarm(self.settings["harakiri"]["timeout"])
                # Get, process, and execute the next JobRequest
                self.handle_next_request()
                self.metrics.commit()
        except Exception:
            self.metrics.counter('server.error.unknown').increment()
            self.logger.exception("Unhandled server error")
        finally:
            self.metrics.commit()
            self.logger.info("Server shutting down")

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
        cmd_options = parser.parse_args(sys.argv[1:])

        # Load settings from the given file (or use Django and grab from its settings)
        if cls.use_django:
            # noinspection PyUnresolvedReferences
            from django.conf import settings as django_settings
            try:
                settings = cls.settings_class(django_settings.SOA_SERVER_SETTINGS)
            except AttributeError:
                raise ValueError("Cannot find SOA_SERVER_SETTINGS in the Django settings")
        else:
            try:
                settings_module = importlib.import_module(cmd_options.settings)
            except ImportError as e:
                raise ValueError("Cannot import settings module %s: %s" % (cmd_options.settings, e))
            try:
                settings_dict = getattr(settings_module, "settings")
            except AttributeError:
                raise ValueError("Cannot find settings variable in settings module %s" % cmd_options.settings)
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
