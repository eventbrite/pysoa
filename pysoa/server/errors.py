from __future__ import (
    absolute_import,
    unicode_literals,
)

from typing import (
    Iterable,
    List,
    Optional,
)

from conformity.error import Error as ConformityError
import six

from pysoa.common.errors import (
    Error,
    PySOAError,
)


def _replace_errors_if_necessary(errors, is_caller_error):
    # type: (Iterable[Error], bool) -> List[Error]
    new_errors = []
    for e in errors:
        if e.is_caller_error == is_caller_error:
            new_errors.append(e)
        else:
            # Error is immutable, so return a new one
            new_errors.append(Error(
                code=e.code,
                message=e.message,
                field=e.field,
                traceback=e.traceback,
                variables=e.variables,
                denied_permissions=e.denied_permissions,
                is_caller_error=is_caller_error,
            ))
    return new_errors


class PySOAServerError(PySOAError):
    """
    Base exception for all server-side errors other than transport errors.
    """


class JobError(PySOAServerError):
    """
    Raised by middleware or the server class as a flow control mechanism for returning a
    :class:`pysoa.common.types.JobResponse` with at least one :class:`Error` in it.
    """

    def __init__(self, errors, set_is_caller_error_to=False):
        # type: (List[Error], Optional[bool]) -> None
        """
        Constructs a new job error.

        :param errors: The list of :class:`Error` objects associated with this job error.
        :param set_is_caller_error_to: If non-`None`, all of the `Error` objects in `errors` will have their
                                       `is_caller_error` attribute set to this value. Defaults to `False`, so you
                                       should set this to `None` if you do not desire the input errors to be modified.
        """
        self.errors = (
            errors if set_is_caller_error_to is None else _replace_errors_if_necessary(errors, set_is_caller_error_to)
        )
        self._set_is_caller_error_to = set_is_caller_error_to


class ActionError(PySOAServerError):
    """
    Raised by action code, middleware, or the server class as a flow control mechanism for returning an
    :class:`pysoa.common.types.ActionResponse` with at least one :class:`Error` in it.
    """

    def __init__(self, errors, set_is_caller_error_to=True):
        # type: (List[Error], Optional[bool]) -> None
        """
        Constructs a new action error.

        :param errors: The list of :class:`Error` objects associated with this action error.
        :param set_is_caller_error_to: If non-`None`, all of the `Error` objects in `errors` will have their
                                       `is_caller_error` attribute set to this value. Defaults to `True`, so you should
                                       set this to `None` if you do not desire the input errors to be modified.
        """
        self.errors = (
            errors if set_is_caller_error_to is None else _replace_errors_if_necessary(errors, set_is_caller_error_to)
        )
        self._set_is_caller_error_to = set_is_caller_error_to


class ResponseValidationError(PySOAServerError):
    """
    Raised by an action when the response fails to validate against the defined response schema for that action.
    Indicates a server-side programming error that must be corrected.
    """

    def __init__(self, action, errors):  # type: (six.text_type, List[ConformityError]) -> None
        self.action = action
        self.errors = errors

    def __str__(self):
        return '{} had an invalid response:\n\t{}'.format(
            self.action,
            '\n\t'.join('{} {}: {}'.format(error.pointer, error.code, error.message) for error in self.errors)
        )
