from __future__ import (
    absolute_import,
    unicode_literals,
)

from pysoa.common.errors import PySOAError


__all__ = (
    'InvalidField',
    'InvalidMessage',
    'SerializationError',
)


class SerializationError(PySOAError):
    """
    Base exceptions for all exceptions related to serialization and deserialization.
    """


class InvalidMessage(SerializationError):
    """
    Raised when a serialized message is incapable of being deserialized.
    """


class InvalidField(SerializationError):
    """
    Raised when a field in a message is not serializable.
    """
