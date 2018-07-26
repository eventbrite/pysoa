from __future__ import (
    absolute_import,
    unicode_literals,
)

import abc

import six

from pysoa.common.types import (
    ActionResponse,
    Error,
)
from pysoa.server.errors import (
    ActionError,
    ResponseValidationError,
)


@six.add_metaclass(abc.ABCMeta)
class Action(object):
    """
    Base class from which all SOA service actions inherit.

    Contains the basic framework for implementing an action:

    - Subclass and override `run()` with the body of your code
    - Optionally provide a `description` attribute, which should be a unicode string and is used to display
      introspection for the action.
    - Optionally provide `request_schema` and/or `response_schema` attributes. These should be Conformity fields.
    - Optionally provide a `validate()` method to do custom validation on the request.
    """

    request_schema = None
    response_schema = None

    def __init__(self, settings=None):
        """
        Construct a new action. Concrete classes can override this and define a different interface, but they must
        still pass the server settings to this base constructor by calling `super`.

        :param settings: The server settings object
        :type settings: dict
        """
        self.settings = settings

    @abc.abstractmethod
    def run(self, request):
        """
        Override this to perform your business logic, and either return a value abiding by the `response_schema` or
        raise an `ActionError`.

        :param request: The request object
        :type request: EnrichedActionRequest

        :return: The response
        :rtype: dict

        :raise: ActionError
        """
        raise NotImplementedError()

    def validate(self, request):
        """
        Override this to perform custom validation logic before the `run()` method is run. Raise `ActionError` if you
        find issues, otherwise return (the return value is ignored). If this method raises an error, `run()` will not
        be called. You do not have to override this method if you don't want to perform custom validation or prefer to
        perform it in `run()`.

        :param request: The request object
        :type request: EnrichedActionRequest

        :raise: ActionError
        """
        pass

    def __call__(self, action_request):
        """
        Main entry point for actions from the `Server` (or potentially from tests). Validates that the request matches
        the `request_schema`, then calls `validate()`, then calls `run()` if `validate()` raised no errors, and then
        validates that the return value from `run()` matches the `response_schema` before returning it in an
        `ActionResponse`.

        :param action_request: The request object
        :type action_request: EnrichedActionRequest

        :return: The response object
        :rtype: ActionResponse

        :raise: ActionError, ResponseValidationError
        """
        # Validate the request
        if self.request_schema:
            errors = [
                Error(
                    code=error.code,
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
