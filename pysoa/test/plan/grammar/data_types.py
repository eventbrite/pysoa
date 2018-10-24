from __future__ import (
    absolute_import,
    unicode_literals,
)

import base64
import datetime
import decimal
import re

from pyparsing import oneOf
import pytz
import six

from pysoa.test.plan.errors import DataTypeConversionError
from pysoa.test.plan.grammar.tools import (
    ENSURE_ACTION_SUBSTITUTION_DEFAULT_INDEX_RE,
    VARIABLE_SUBSTITUTION_RE,
)


data_type_descriptions = {
    'int': 'An integer, equivalent to a Python 3 ``int`` in either Python 2 or 3',
    'float': 'A floating-point decimal',
    'decimal': 'A ``decimal.Decimal`` object',
    'bool': 'A boolean',
    'bytes': 'A byte array, equivalent to ``bytes`` in Python 3 and ``str`` in Python 3',
    'base64_bytes': 'Same as ``bytes``, except the value in the fixture directive is base64-encoded and should be '
                    'decoded before use',
    'str': 'A unicode string, equivalent to ``str`` in Python 3 and ``unicode`` in Python 2',
    'encoded_ascii': 'A should-be-unicode string, except the value in the fixture directive has ASCII escape '
                     'sequences that should be decoded before use',
    'encoded_unicode': 'A unicode string, except the value in the fixture directive has Unicode escape sequences that '
                       'should be decoded before use',
    'emptystr': 'A zero-length unicode string',
    'emptylist': 'A zero-length list (``[]``)',
    'emptydict': 'A zero-length dict (``{}``)',
    'datetime': 'A ``datetime.datetime`` object',
    'date': 'A ``datetime.date`` object',
    'time': 'A ``datetime.time`` object',
    'none': '``None``',
    'None': '``None``',
    'regex': 'Used for expectations only, the string value must match this regular expression',
    'not regex': 'Used for expectations only, the string value must *not* match this regular expression',
}


def get_all_data_type_names():
    return sorted(six.iterkeys(data_type_descriptions), key=six.text_type.lower)


DataTypeGrammar = oneOf(get_all_data_type_names())('data_type')


class AnyValue(object):
    def __init__(self, data_type, permit_none=False):
        self.data_type = data_type
        self.permit_none = permit_none

    def __eq__(self, other):
        if other is None:
            return self.permit_none

        if isinstance(other, AnyValue):
            return self.data_type == other.data_type

        if self.data_type == 'str':
            # For Python 2 compatibility, a "unicode" is considered a string
            return isinstance(other, six.text_type)

        if self.data_type == 'bytes':
            # For Python 3 compatibility, a "str" is considered a bytes
            return isinstance(other, six.binary_type)

        if self.data_type == 'int':
            # For Python 2+3 compatibility, any int OR long value is permitted to satisfy an int AnyValue
            return isinstance(other, six.integer_types)

        if self.data_type == type(other).__name__:
            return True

        return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return 'any {} type value{}'.format(self.data_type, ' or None' if self.permit_none else '')

    def __copy__(self):
        return self

    def __deepcopy__(self, *_):
        return self


class RegexValue(object):
    def __init__(self, pattern, negate=False):
        self.re = re.compile(pattern)
        self.pattern = pattern
        self.negate = negate

    def __eq__(self, other):
        if isinstance(other, RegexValue):
            return self.pattern == other.pattern and self.negate == other.negate

        if not isinstance(other, six.text_type):
            return False

        match = self.re.match(other)
        return (self.negate and match is None) or (not self.negate and match is not None)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return 'regex{not_q} {pattern}'.format(not_q=' not' if self.negate else '', pattern=self.pattern)

    def __copy__(self):
        return self

    def __deepcopy__(self, *_):
        return self


def _parse_datetime_args(v):
    return list(map(int, v.split(',')))


def _parse_timedelta_args(v):
    argument_keys = ['days', 'hours', 'minutes', 'seconds', 'microseconds']
    kwargs = {}
    for i, v in enumerate(map(int, v.split(','))):
        if i > 4:
            break
        kwargs[argument_keys[i]] = v
    return kwargs


# value is expected to be unicode data type
def get_typed_value(type_name, value):
    if isinstance(value, AnyValue):
        return value
    if isinstance(value, RegexValue):
        return value

    if isinstance(value, six.text_type) and VARIABLE_SUBSTITUTION_RE.search(value):
        # make sure 0 index is inserted into action-name-based variable substitutions
        return ENSURE_ACTION_SUBSTITUTION_DEFAULT_INDEX_RE.sub(r'[[\1.0.\2]]', value)

    if type_name in ('None', 'none', 'null'):
        return None

    try:
        if type_name == 'int':
            if not value:
                return six.integer_types[-1](0)
            return six.integer_types[-1](value)
        if type_name == 'float':
            if not value:
                return 0.0
            return float(value)
        if type_name == 'decimal':
            if not value:
                return decimal.Decimal('0.0')
            return decimal.Decimal(value)
        if type_name == 'bool':
            if not value:
                return False
            if value.lower() == 'true':
                return True
            return False

        if type_name in ('bytes', 'base64_bytes'):
            if not value:
                return b''
            if type_name == 'base64_bytes':
                if not isinstance(value, six.binary_type):
                    value = value.encode('utf-8')
                return base64.b64decode(value)
            if isinstance(value, six.binary_type):
                return value
            return value.encode('utf-8')  # All test plan files should be utf-8 encoded

        if type_name in ('str', 'encoded_ascii', 'encoded_unicode'):
            if not value:
                return ''
            if type_name == 'encoded_ascii':
                # The value, though read as a unicode string, contains ASCII escape sequences in the file itself. Encode
                # it as an ASCII byte sequence, and then decode the escape sequences back into a unicode string.
                # Example: The file contains "item\x0b name", which becomes a Python literal "item\\x0b name".
                return value.encode('ascii').decode('unicode_escape')
            if type_name == 'encoded_unicode':
                # The value, though read as a unicode string, contains unicode escape sequences in the file itself.
                # Encode it as a unicode byte sequence, and then decode the escape sequences back into a unicode string.
                # Example: The file contains "item\u000B name", which becomes a Python literal "item\\u000B name".
                return value.encode('utf-8').decode('unicode_escape')
            if isinstance(value, six.binary_type):
                return value.decode('utf-8')
            return value
    except (TypeError, ValueError, decimal.DecimalException) as e:
        raise DataTypeConversionError(e.args[0])

    if type_name == 'emptystr':
        return ''
    if type_name == 'emptylist':
        return []
    if type_name == 'emptydict':
        return {}

    if type_name == 'datetime':
        if not value:
            raise DataTypeConversionError('Attempt to convert false-y value to datetime value')

        if isinstance(value, six.string_types):
            if value.startswith(('now', 'utc_now', 'midnight', 'utc_midnight')):
                try:
                    datetime_value, timedelta_value = value.strip().split(' ', 1)
                except ValueError:
                    datetime_value = value.strip()[:]
                    timedelta_value = None

                if datetime_value == 'now':
                    datetime_value = datetime.datetime.now()
                elif datetime_value == 'utc_now':
                    datetime_value = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
                elif datetime_value == 'midnight':
                    datetime_value = datetime.datetime.combine(datetime.date.today(), datetime.time())
                else:
                    datetime_value = datetime.datetime.combine(
                        datetime.datetime.utcnow().date(),
                        datetime.time(),
                    ).replace(tzinfo=pytz.utc)

                assert isinstance(datetime_value, datetime.datetime), 'Parse error, value is not a `datetime`'

                datetime_value = datetime_value.replace(microsecond=0)

                if timedelta_value:
                    datetime_value = datetime_value + datetime.timedelta(**_parse_timedelta_args(timedelta_value))

                return datetime_value

            return datetime.datetime(*_parse_datetime_args(value))

        raise DataTypeConversionError(
            'Attempt to convert unknown type {} to datetime value'.format(type(value).__name__),
        )

    if type_name == 'date':
        if not value:
            raise DataTypeConversionError('Attempt to convert false-y value to date value')

        if isinstance(value, six.string_types):
            if value == 'today':
                return datetime.date.today()
            elif value == 'utc_today':
                return datetime.datetime.utcnow().date()

            return datetime.date(*_parse_datetime_args(value))

        raise DataTypeConversionError('Attempt to convert unknown type {} to date value'.format(type(value).__name__))

    if type_name == 'time':
        if not value:
            raise DataTypeConversionError('Attempt to convert false-y value to time value')

        if isinstance(value, six.string_types):
            if value.startswith(('now', 'utc_now', 'midnight')):
                try:
                    time_value, timedelta_value = value.strip().split(' ', 1)
                except ValueError:
                    time_value = value.strip()[:]
                    timedelta_value = None

                if time_value == 'now':
                    datetime_value = datetime.datetime.now()
                elif time_value == 'utc_now':
                    datetime_value = datetime.datetime.utcnow()
                else:
                    datetime_value = datetime.datetime(2000, 1, 1, 0, 0, 0, 0)

                if timedelta_value:
                    datetime_value = datetime_value + datetime.timedelta(**_parse_timedelta_args(timedelta_value))

                return datetime_value.replace(microsecond=0).time()

            return datetime.time(*_parse_datetime_args(value))

        raise DataTypeConversionError('Attempt to convert unknown type {} to time value'.format(type(value).__name__))

    raise DataTypeConversionError('Unknown type: {}'.format(type_name))


def get_parsed_data_type_value(parse_result, value):
    if getattr(parse_result, 'any') == 'any':
        return AnyValue(parse_result.data_type or 'str')
    elif parse_result.data_type == 'regex':
        return RegexValue(value)
    elif parse_result.data_type == 'not regex':
        return RegexValue(value, True)
    else:
        return get_typed_value(parse_result.data_type or 'str', value)
