from __future__ import (
    absolute_import,
    unicode_literals,
)

from typing import (  # noqa: F401 TODO Python 3
    Generator,
    Iterable,
    List,
    Optional,
)

from conformity.error import Error as ConformityError  # noqa: F401 TODO Python 3
import six  # noqa: F401 TODO Python 3

from pysoa.common.types import Error  # noqa: F401 TODO Python 3


def _replace_error_if_necessary(errors, is_caller_error):
    # type: (Iterable[Error], bool) -> Generator[Error, None, None]
    for e in errors:
        if e.is_caller_error == is_caller_error:
            yield e
        else:
            # Error is immutable, so return a new one
            yield Error(
                code=e.code,
                message=e.message,
                field=e.field,
                traceback=e.traceback,
                variables=e.variables,
                denied_permissions=e.denied_permissions,
                is_caller_error=is_caller_error,
            )


class JobError(Exception):
    def __init__(self, errors, is_caller_error=False):  # type: (List[Error], Optional[bool]) -> None
        """
        Constructs a new job error.

        :param errors: The list of :class:`Error` objects associated with this job error.
        :param is_caller_error: If non-`None`, all of the `Error` objects in `errors` will have their `is_caller_error`
                                attribute set to this value. Defaults to `False`, so you should set this to `None`, if
                                you do not desire the input errors to be modified.
        """
        self.errors = errors if is_caller_error is None else list(_replace_error_if_necessary(errors, is_caller_error))
        self.is_caller_error = is_caller_error


class ActionError(Exception):
    def __init__(self, errors, is_caller_error=True):  # type: (List[Error], Optional[bool]) -> None
        """
        Constructs a new action error.

        :param errors: The list of :class:`Error` objects associated with this action error.
        :param is_caller_error: If non-`None`, all of the `Error` objects in `errors` will have their `is_caller_error`
                                attribute set to this value. Defaults to `True`, so you should set this to `None`, if
                                you do not desire the input errors to be modified.
        """
        self.errors = errors if is_caller_error is None else list(_replace_error_if_necessary(errors, is_caller_error))
        self.is_caller_error = is_caller_error


class ResponseValidationError(Exception):
    """
    Raised by an Action when the response fails to validate. Not meant to
    be caught and handled by the server other than going into the error logging
    infrastructure.
    """
    def __init__(self, action, errors):  # type: (six.text_type, List[ConformityError]) -> None
        self.action = action
        self.errors = errors

    def __str__(self):
        return '{} had an invalid response:\n\t{}'.format(
            self.action,
            '\n\t'.join('{} {}: {}'.format(error.pointer, error.code, error.message) for error in self.errors)
        )
