from __future__ import (
    absolute_import,
    unicode_literals,
)

from typing import List  # noqa: F401 TODO Python 3

from conformity.error import Error as ConformityError  # noqa: F401 TODO Python 3
import six  # noqa: F401 TODO Python 3

from pysoa.common.types import Error  # noqa: F401 TODO Python 3


class JobError(Exception):
    def __init__(self, errors):  # type: (List[Error]) -> None
        self.errors = errors


class ActionError(Exception):
    def __init__(self, errors):  # type: (List[Error]) -> None
        self.errors = errors


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
