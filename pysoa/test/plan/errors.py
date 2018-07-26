from __future__ import (
    absolute_import,
    unicode_literals,
)

import codecs

import six


__all__ = (
    'DataTypeConversionError',
    'DirectiveError',
    'FixtureLoadError',
    'FixtureSyntaxError',
    'StatusError',
)


class DataTypeConversionError(Exception):
    """
    Raised when an error occurs converting a string value in a test case input or expectation directive into the
    directive-specified non-string type.
    """


class DirectiveError(Exception):
    """
    Raised when the test plan code encounters an internal error using a registered directive class.
    """


class FixtureLoadError(Exception):
    """
    Raised when the test plan is unable to load fixtures from a file for any reason.
    """


class FixtureSyntaxError(SyntaxError):
    """
    Raised when a fixture test file contains invalid syntax.
    """
    def __init__(self, message, file_name, line_number=0, offset=0, line_text=''):
        if file_name and line_number and (not offset or not line_text):
            if not line_text:
                line_text = self._get_line_at_number(file_name, line_number)
            if not offset:
                offset = len(line_text)
        super(FixtureSyntaxError, self).__init__(message, (file_name, line_number, offset, line_text))

    @classmethod
    def _get_line_at_number(cls, file_name, line_number):
        try:
            i = 1
            with codecs.open(file_name, mode='rb', encoding='utf-8') as file_input:
                for line in file_input:
                    if i == line_number:
                        return line.strip()
                    i += 1
            return cls._UnknownLine('[unknown]')
        except IOError:
            return cls._UnknownLine('[io error]')

    class _UnknownLine(six.text_type):
        def __len__(self):
            return 0


class StatusError(Exception):
    """
    Raised when some unexpected condition arises while running a test plan.
    """
