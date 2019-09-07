from __future__ import (
    absolute_import,
    unicode_literals,
)


__all__ = (
    'InvalidField',
    'InvalidMessage',
)


class InvalidMessage(Exception):
    pass


class InvalidField(Exception):
    pass
