from __future__ import (
    absolute_import,
    unicode_literals,
)


class JobError(Exception):
    def __init__(self, errors):
        self.errors = errors


class ActionError(Exception):
    def __init__(self, errors):
        self.errors = errors


class ResponseValidationError(Exception):
    """
    Raised by an Action when the response fails to validate. Not meant to
    be caught and handled by the server other than going into the error logging
    infrastructure.
    """
    def __init__(self, action, errors):
        self.action = action
        self.errors = errors

    def __str__(self):
        return '{} had an invalid response:\n\t{}'.format(
            self.action,
            '\n\t'.join('{} {}: {}'.format(error.pointer, error.code, error.message) for error in self.errors)
        )
