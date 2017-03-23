from pysoa.common.constants import ERROR_CODE_INVALID
from pysoa.common.types import ActionResponse, Error
from pysoa.server.errors import ActionError, ResponseValidationError


class Action(object):
    """
    Base class from which all SOA Service Actions inherit.

    Contains the basic framework for implementing an Action:
     - Subclass and override run() with the body of your code
     - Optionally provide a request_schema and response_schema. These should
       be Conformity fields
     - Optionally provide a validate() method to do custom validation on the
       request.
    """

    request_schema = None
    response_schema = None

    def __init__(self, settings=None):
        self.settings = settings

    def run(self, request):
        """
        Override this to perform your business logic, and either return a dict
        or raise an ActionError.
        """
        raise NotImplementedError()

    def validate(self, request):
        """
        Override this to perform custom validation logic before the run()
        method is run. Raise ActionError if you find issues, otherwise return
        (the return value is ignored)
        """
        pass

    def __call__(self, action_request):
        """
        Main entrypoint for Actions from the Server (or potentially from tests)
        """
        # Validate the request
        if self.request_schema:
            errors = [
                Error(
                    code=ERROR_CODE_INVALID,
                    message=error.message,
                    field=error.pointer,
                )
                for error in (self.request_schema.errors(action_request.body) or [])
            ]
            if errors:
                raise ActionError(errors=errors)
        # Run any custom validation
        self.validate(action_request)
        # Run the body of the action
        response_body = self.run(action_request)
        # Validate the response body. Errors in a response are the problem of
        # the service, and so we just raise a Python exception and let error
        # middleware catch it. The server will return a SERVER_ERROR response.
        if self.response_schema:
            errors = self.response_schema.errors(response_body)
            if errors:
                raise ResponseValidationError(action=action_request.action, errors=errors)
        # Make an ActionResponse and return it
        if response_body is not None:
            return ActionResponse(
                action=action_request.action,
                body=response_body,
            )
        else:
            return ActionResponse(action=action_request.action)
