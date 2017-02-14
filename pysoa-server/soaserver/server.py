import attr

from soaserver.constants import (
    ERROR_CODE_INVALID,
    ERROR_CODE_UNKNOWN,
)
from soaserver.schemas import JobRequestSchema
from soaserver.types import (
    JobResponse,
    ActionResponse,
    Error,
)
from soaserver.errors import (
    JobError,
    ActionError,
)


class Server(object):
    """
    Base class from which all SOA Service Servers inherit.

    Required Attributes for Subclasses:
        service_name: a string name of the service.
        action_class_map: a dictionary mapping action name strings
            to Action subclasses.
    """
    service_name = None
    action_class_map = {}
    middleware_classes = []

    def __init__(self):
        if not self.service_name:
            raise AttributeError('Server subclass must set service_name')

        self.shutting_down = False

        # Instantiate middleware
        self.middleware = [
            middleware_class() for middleware_class in self.middleware_classes
        ]

    def process_request(self, job_request):
        """
        Validates the JobRequest and run Job's Actions.
        """
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

        # Run the Job's Actions
        job_response = JobResponse()
        for i, action_request in enumerate(job_request['actions']):
            action_name = action_request['action']
            if action_name in self.action_class_map:
                # Run process ActionRequest middleware
                try:
                    for middleware in self.middleware:
                        middleware.process_action_request(action_request)

                    # Run action
                    action_response = self.action_class_map[action_name](action_request)

                    # Run process ActionResponse middleware
                    for middleware in self.middleware:
                        middleware.process_action_response(action_response)
                except ActionError as e:
                    # Error: an error was thrown while running the Action (or Action middleware)
                    action_response = ActionResponse(
                        action=action_name,
                        errors=e.errors,
                    )
            else:
                # Error: Action not found.
                action_response = ActionResponse(
                    action=action_name,
                    errors=[Error(
                        code=ERROR_CODE_UNKNOWN,
                        message='The action "{}" was not found on this server.'.format(action_name),
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

    def run(self):
        while not self.shutting_down:
            # Get the next JobRequest
            request_id, meta, request_message = self.transport.receive_request_message()
            job_request = self.serializer.blob_to_dict(request_message)

            try:
                # Run process JobRequest middleware
                for middleware in self.middleware:
                    middleware.process_job_request(job_request)

                # Run the Job
                job_response = self.process_request(job_request)

                # Run process JobResponse middleware
                for middleware in self.middleware:
                    middleware.process_job_response(job_response)
            except JobError as e:
                job_response = JobResponse(
                    errors=e.errors,
                )

            # Send the JobResponse
            response_message = self.serializer.dict_to_blob(attr.asdict(job_response))
            self.transport.send_response_message(request_id, meta, response_message)
