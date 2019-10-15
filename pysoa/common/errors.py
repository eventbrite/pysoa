from __future__ import (
    absolute_import,
    unicode_literals,
)

from typing import (
    Any,
    Dict,
    List,
    Optional,
)

import attr
import six


__all__ = (
    'Error',
    'PySOAError',
)


@attr.s(frozen=True)
class Error(object):
    """
    Represents an error that occurred, in the format transmitted over the transport between client and service.

    :param code: The machine-readable error code.
    :param message: The human-readable error message.
    :param field: If the error is the result of validation of a job attribute or action request field, this contains
                  the name of that attribute or field. It will be `None` otherwise.
    :param traceback: If the error is the result of an exception with valuable traceback information, this contains
                      that traceback. It will be `None` otherwise.
    :param variables: If there are any variables pertinent to this error, this dictionary will contain the names and
                      values of those variables. It will be `None` otherwise. New in version 0.9.0.
    :param denied_permissions: If this error is the result of insufficient privileges to perform the requested
                               operation, this attribute will be a list containing the necessary permissions that
                               were denied, if the service supports reporting this information.  It will be `None`
                               otherwise. New in version 0.44.0.
    :param is_caller_error: Indicates whether this error is the result of the caller doing something wrong (`True`),
                            such as an invalid job request or an action request body that fails to validate, or the
                            result of a server or service problem or bug (`False`). New in version 0.70.0.
    """

    code = attr.ib()  # type: six.text_type
    message = attr.ib()  # type: six.text_type
    field = attr.ib(default=None)  # type: Optional[six.text_type]
    traceback = attr.ib(default=None)  # type: Optional[six.text_type]
    variables = attr.ib(default=None)  # type: Optional[Dict[six.text_type, Any]]
    denied_permissions = attr.ib(default=None)  # type: Optional[List[six.text_type]]
    is_caller_error = attr.ib(default=False, metadata={'added_in_version': (0, 70, 0)})  # type: bool


class PySOAError(Exception):
    """
    Base exception for all PySOA errors.
    """
