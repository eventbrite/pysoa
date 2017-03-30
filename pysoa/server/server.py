import argparse
import importlib
import logging
import logging.config
import os
import sys
import traceback
from signal import (
    signal,
    SIGINT,
    SIGTERM,
)

import attr

from pysoa.common.types import (
    JobResponse,
    ActionRequest,
    ActionResponse,
    Error,
)
from pysoa.common.constants import (
    ERROR_CODE_INVALID,
    ERROR_CODE_UNKNOWN,
    ERROR_CODE_SERVER_ERROR,
)
from .schemas import JobRequestSchema
from .internal.types import RequestSwitchSet
from .errors import (
    JobError,
    ActionError,
)
from .settings import ServerSettings


class Server(object):
    """
    Base class from which all SOA Service Servers inherit.

    Required Attributes for Subclasses:
        service_name: a string name of the service.
        action_class_map: a dictionary mapping action name strings
            to Action subclasses.
    """

    settings_class = ServerSettings

    service_name = None
    action_class_map = {}
    middleware_classes = []

    def __init__(self, settings):
        # Check subclassing setup
        if not self.service_name:
            raise AttributeError('Server subclass must set service_name')

        # Store settings and extract serializer and transport
        self.settings = settings
        self.transport = self.settings['transport']['object'](
            self.service_name,
            **self.settings['transport'].get('kwargs', {})
        )
        self.serializer = self.settings['serializer']['object'](
            **self.settings['serializer'].get('kwargs', {})
        )

        # Set initial state
        self.shutting_down = False

        # Instantiate middleware
        self.middleware = [
            obj(**kwargs)
            for obj, kwargs in self.settings['middleware']
        ]

        # Set up logger
        self.logger = logging.getLogger("pysoa.server")
        self.job_logger = logging.getLogger("pysoa.server.job")

    def handle_next_request(self):
        # Get the next JobRequest
        request_id, meta, request_message = self.transport.receive_request_message()
        job_request = self.serializer.blob_to_dict(request_message)
        self.job_logger.info("Job request: %s", job_request)

        # Process and run the Job
        job_response = self.process_job(job_request)

        # Send the JobResponse
        response_dict = attr.asdict(job_response)
        response_message = self.serializer.dict_to_blob(response_dict)
        self.transport.send_response_message(request_id, meta, response_message)
        self.job_logger.info("Job response: %s", response_dict)

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

            # Run process JobRequest middleware
            for middleware in self.middleware:
                middleware.process_job_request(job_request)

            # Run the Job
            job_response = self.execute_job(job_request)

            # Run process JobResponse middleware
            for middleware in self.middleware:
                middleware.process_job_response(job_response)
        except JobError as e:
            job_response = JobResponse(
                errors=e.errors,
            )
        except Exception as e:
            try:
                for middleware in self.middleware:
                    middleware.process_job_exception(job_request, e)
            except Exception as e:
                # NOTE: This effectively mutes the original exception in favor
                #       of exceptions raised by the middleware.
                pass

            # Send an error response
            # Formatting the error might itself error, so try to catch that
            try:
                error_str, traceback_str = str(e), traceback.format_exc()
            except Exception:
                error_str, traceback_str = "Error formatting error", traceback.format_exc()

            job_response = JobResponse(
                errors=[{
                    'code': ERROR_CODE_SERVER_ERROR,
                    'message': 'Internal server error: %s' % error_str,
                    'traceback': traceback_str,
                }],
            )
            self.logger.error("Unhandled error: %s", traceback_str)

        return job_response

    def execute_job(self, job_request):
        """
        Processes and runs the ActionRequests on the Job.
        """
        # Run the Job's Actions
        job_response = JobResponse()
        job_switches = RequestSwitchSet(job_request['control']['switches'])
        for i, raw_action_request in enumerate(job_request['actions']):
            action_request = ActionRequest(
                action=raw_action_request['action'],
                body=raw_action_request.get('body', None),
                switches=job_switches,
                context=job_request.get('context', {}),
                control=job_request['control'],
            )
            if action_request.action in self.action_class_map:
                # Run process ActionRequest middleware
                try:
                    for middleware in self.middleware:
                        middleware.process_action_request(action_request)

                    # Run action
                    action = self.action_class_map[action_request.action](self.settings)
                    action_response = action(action_request)

                    # Run process ActionResponse middleware
                    for middleware in self.middleware:
                        middleware.process_action_response(action_response)
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
                action_response.errors
                and not job_request['control'].get('continue_on_error', False)
            ):
                # Quit running Actions if an error occurred and continue_on_error is False
                break

        return job_response

    def handle_shutdown_signal(self, signal, sf):
        if self.shutting_down:
            self.logger.warning("Received double interrupt, forcing shutdown")
            sys.exit(1)
        else:
            self.logger.warning("Received interrupt, initiating shutdown")
            self.shutting_down = True

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
        try:
            while not self.shutting_down:
                # Get, process, and execute the next JobRequest
                self.handle_next_request()
        finally:
            self.logger.info("Server shutting down")

    @classmethod
    def main(cls):
        """
        Command-line entrypoint for running a PySOA service Server.
        """
        parser = argparse.ArgumentParser(
            description='Server for the {} SOA service'.format(cls.service_name),
        )
        parser.add_argument(
            '-d', '--daemon',
            action='store_true',
            help='run the server process as a daemon',
        )
        parser.add_argument(
            '-s', '--settings',
            help='The settings file to use',
            required=True,
        )
        cmd_options = parser.parse_args(sys.argv[1:])

        # Load settings from the given file
        try:
            settings_module = importlib.import_module(cmd_options.settings)
        except ImportError:
            raise ValueError("Cannot import settings module %s" % cmd_options.settings)
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
        signal(SIGINT, server.handle_shutdown_signal)
        signal(SIGTERM, server.handle_shutdown_signal)

        # Start server event loop
        server.run()
