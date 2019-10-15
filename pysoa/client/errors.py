from __future__ import (
    absolute_import,
    unicode_literals,
)

from typing import (
    List,
    Optional,
)

from pysoa.common.errors import (
    Error,
    PySOAError,
)
from pysoa.common.types import ActionResponse


class PySOAClientError(PySOAError):
    """
    Base exception for all client-side errors other than transport errors.
    """


class ImproperlyConfigured(PySOAClientError):
    """
    Raised when this client is improperly configured to call the specified service.
    """


class InvalidExpansionKey(PySOAClientError):
    """
    Raised when this client is improperly configured to perform the specified expansion.
    """


class CallJobError(PySOAClientError):
    """
    Raised by `Client.call_***` methods when a job response contains one or more job errors. Stores a list of
    :class:`Error` objects and has a string representation cleanly displaying the errors.
    """

    def __init__(self, errors=None):  # type: (Optional[List[Error]]) -> None
        """
        :param errors: The list of all errors in this job, available as an `errors` property on the exception
                       instance.
        """
        self.errors = errors or []  # type: List[Error]

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        errors_string = '\n'.join([str(e) for e in self.errors])
        return 'Error executing job:\n{}'.format(errors_string)


class CallActionError(PySOAClientError):
    """
    Raised by `Client.call_***` methods when a job response contains one or more action errors. Stores a list of
    :class:`ActionResponse` objects and has a string representation cleanly displaying the actions' errors.
    """

    def __init__(self, actions=None):  # type: (Optional[List[ActionResponse]]) -> None
        """
        :param actions: The list of all actions that have errors (not actions without errors), available as an
                        `actions` property on the exception instance.
        """
        self.actions = actions or []  # type: List[ActionResponse]

    def __str__(self):
        errors_string = '\n'.join(['{a.action}: {a.errors}'.format(a=a) for a in self.actions])
        return 'Error calling action(s):\n{}'.format(errors_string)
