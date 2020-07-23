from __future__ import (
    absolute_import,
    unicode_literals,
)

import base64
import copy
import datetime
import decimal
import unittest

import freezegun
import pytz
import six

from pysoa.test.plan.errors import DataTypeConversionError
from pysoa.test.plan.grammar import data_types


class TestAnyValue(unittest.TestCase):
    def test_any_none_value(self):
        self.assertEqual(data_types.AnyValue('str', permit_none=True), None)
        self.assertNotEqual(data_types.AnyValue('str'), None)

    def test_string(self):
        self.assertEqual(data_types.AnyValue('str'), 'Hello')
        self.assertNotEqual(data_types.AnyValue('str'), b'Hello')
        self.assertNotEqual(data_types.AnyValue('str'), 15)

    def test_bytes(self):
        self.assertEqual(data_types.AnyValue('bytes'), b'Hello')
        self.assertNotEqual(data_types.AnyValue('bytes'), 'Hello')
        self.assertNotEqual(data_types.AnyValue('bytes'), 15)

    def test_int(self):
        self.assertEqual(data_types.AnyValue('int'), 1095)
        self.assertEqual(data_types.AnyValue('int'), 1837382923847829375723723623632748582372718294943727237328349492)
        self.assertNotEqual(data_types.AnyValue('int'), 5.43)
        self.assertNotEqual(data_types.AnyValue('int'), decimal.Decimal('5.43'))

    def test_any_value(self):
        self.assertEqual(data_types.AnyValue('int'), data_types.AnyValue('int'))
        self.assertNotEqual(data_types.AnyValue('int'), data_types.AnyValue('str'))

    def test_copy(self):
        self.assertEqual(copy.copy(data_types.AnyValue('str')), 'Hello')
        self.assertEqual(copy.deepcopy(data_types.AnyValue('str')), 'Hello')

    def test_datetime(self):
        self.assertEqual(data_types.AnyValue('datetime'), '2018-09-01T00:00:00Z')
        self.assertNotEqual(data_types.AnyValue('datetime'), 'Hello')
        self.assertNotEqual(data_types.AnyValue('datetime'), 15)

    def test_date(self):
        self.assertEqual(data_types.AnyValue('date'), '2018-09-01')
        self.assertNotEqual(data_types.AnyValue('date'), 'Bye')
        self.assertNotEqual(data_types.AnyValue('date'), 51)


class TestRegexValue(unittest.TestCase):
    def test_not_string(self):
        self.assertNotEqual(data_types.RegexValue(r'^Sing(le)?$'), b'Single')
        self.assertNotEqual(data_types.RegexValue(r'^Sing(le)?$'), 15)
        self.assertNotEqual(data_types.RegexValue(r'^Sing(le)?$'), 7.81)
        self.assertNotEqual(data_types.RegexValue(r'^Sing(le)?$'), True)
        self.assertNotEqual(data_types.RegexValue(r'^Sing(le)?$'), None)

    def test_string(self):
        self.assertEqual(data_types.RegexValue(r'^Sing(le)?$'), 'Single')
        self.assertNotEqual(data_types.RegexValue(r'^Sing(le)?$', True), 'Single')
        self.assertEqual(data_types.RegexValue(r'^Sing(le)?$'), 'Sing')
        self.assertNotEqual(data_types.RegexValue(r'^Sing(le)?$', True), 'Sing')
        self.assertEqual(data_types.RegexValue(r'^Tang(le)?$'), 'Tangle')
        self.assertNotEqual(data_types.RegexValue(r'^Tang(le)?$', True), 'Tangle')
        self.assertEqual(data_types.RegexValue(r'^Tang(le)?$'), 'Tang')
        self.assertNotEqual(data_types.RegexValue(r'^Tang(le)?$', True), 'Tang')

    def test_regex_value(self):
        self.assertEqual(data_types.RegexValue(r'^Sing(le)?$'), data_types.RegexValue(r'^Sing(le)?$'))
        self.assertEqual(data_types.RegexValue(r'^Sing(le)?$', True), data_types.RegexValue(r'^Sing(le)?$', True))
        self.assertNotEqual(data_types.RegexValue(r'^Sing(le)?$'), data_types.RegexValue(r'^Sing(le)?$', True))
        self.assertNotEqual(data_types.RegexValue(r'^Sing(le)?$'), data_types.RegexValue(r'^Sing$'))

    def test_copy(self):
        self.assertEqual(copy.copy(data_types.RegexValue(r'^Sing(le)?$')), 'Single')
        self.assertEqual(copy.deepcopy(data_types.RegexValue(r'^Sing(le)?$')), 'Sing')


class TestGetTypedValue(unittest.TestCase):
    def test_special_cases(self):
        self.assertEqual(data_types.AnyValue('str'), data_types.get_typed_value(None, data_types.AnyValue('str')))
        self.assertEqual(
            data_types.RegexValue(r'^Sing(le)?$'),
            data_types.get_typed_value('does not matter', data_types.RegexValue(r'^Sing(le)?$')),
        )
        self.assertIsNone(data_types.get_typed_value('None', 'does not matter'))
        self.assertIsNone(data_types.get_typed_value('none', 'does not matter'))
        self.assertIsNone(data_types.get_typed_value('null', 'does not matter'))
        self.assertEqual('[[some.substitution]]', data_types.get_typed_value(None, '[[some.substitution]]'))
        self.assertEqual(
            '[[another.1.substitution]]',
            data_types.get_typed_value('does not matter', '[[another.1.substitution]]'),
        )
        self.assertEqual(
            '[[ACTION_NAME.0.response.body.path]]',
            data_types.get_typed_value(None, '[[ACTION_NAME.response.body.path]]'),
        )
        self.assertEqual(
            '[[ANOTHER.2.response.body.path]]',
            data_types.get_typed_value(None, '[[ANOTHER.2.response.body.path]]'),
        )
        self.assertEqual(
            '[[{ESCAPED}.response.body.path]]',
            data_types.get_typed_value(None, '[[{ESCAPED}.response.body.path]]'),
        )
        self.assertEqual(
            'complex [[some.substitution]] expression [[another.1.substitution]] with '
            '[[ACTION_NAME.0.response.body.path]] many [[ANOTHER.2.response.body.path]] substitutions '
            '[[{ESCAPED}.response.body.path]]',
            data_types.get_typed_value(
                None,
                'complex [[some.substitution]] expression [[another.1.substitution]] with '
                '[[ACTION_NAME.response.body.path]] many [[ANOTHER.2.response.body.path]] substitutions '
                '[[{ESCAPED}.response.body.path]]',
            )
        )

    def test_int(self):
        self.assertEqual(six.integer_types[-1](827), data_types.get_typed_value('int', '827'))
        self.assertEqual(
            827284953472372388372372384573592394184838723482384,
            data_types.get_typed_value('int', '827284953472372388372372384573592394184838723482384'),
        )
        self.assertEqual(six.integer_types[-1](0), data_types.get_typed_value('int', ''))
        self.assertEqual(six.integer_types[-1](0), data_types.get_typed_value('int', None))

        with self.assertRaises(DataTypeConversionError):
            data_types.get_typed_value('int', '1.23')

    def test_float(self):
        self.assertEqual(827.15, data_types.get_typed_value('float', '827.15'))
        self.assertEqual(0.0, data_types.get_typed_value('float', ''))
        self.assertEqual(0.0, data_types.get_typed_value('float', None))

        with self.assertRaises(DataTypeConversionError):
            data_types.get_typed_value('float', 'abc123')

    def test_decimal(self):
        self.assertEqual(decimal.Decimal('827.15'), data_types.get_typed_value('decimal', '827.15'))
        self.assertEqual(decimal.Decimal('0.0'), data_types.get_typed_value('decimal', ''))
        self.assertEqual(decimal.Decimal('0.0'), data_types.get_typed_value('decimal', None))

        with self.assertRaises(DataTypeConversionError):
            data_types.get_typed_value('decimal', 'abc123')

    def test_bool(self):
        self.assertTrue(data_types.get_typed_value('bool', 'TRUE'))
        self.assertTrue(data_types.get_typed_value('bool', 'TRUe'))
        self.assertTrue(data_types.get_typed_value('bool', 'TRue'))
        self.assertTrue(data_types.get_typed_value('bool', 'True'))
        self.assertTrue(data_types.get_typed_value('bool', 'TrUE'))
        self.assertTrue(data_types.get_typed_value('bool', 'TrUe'))
        self.assertTrue(data_types.get_typed_value('bool', 'TruE'))
        self.assertTrue(data_types.get_typed_value('bool', 'tRUE'))
        self.assertTrue(data_types.get_typed_value('bool', 'trUE'))
        self.assertTrue(data_types.get_typed_value('bool', 'truE'))
        self.assertFalse(data_types.get_typed_value('bool', None))
        self.assertFalse(data_types.get_typed_value('bool', ''))
        self.assertFalse(data_types.get_typed_value('bool', 'NaN'))
        self.assertFalse(data_types.get_typed_value('bool', 'false'))
        self.assertFalse(data_types.get_typed_value('bool', 'FALSE'))
        self.assertFalse(data_types.get_typed_value('bool', 'Anything, really'))

    def test_bytes(self):
        self.assertEqual(b'Hello', data_types.get_typed_value('bytes', 'Hello'))
        self.assertEqual(b'Goodbye', data_types.get_typed_value('bytes', b'Goodbye'))
        self.assertEqual(b'Cool! \xf0\x9f\x98\x9c', data_types.get_typed_value('bytes', 'Cool! \U0001f61c'))
        self.assertEqual(
            b'It works!',
            data_types.get_typed_value('base64_bytes', base64.b64encode(b'It works!')),
        )
        self.assertEqual(
            b'It still works!',
            data_types.get_typed_value('base64_bytes', base64.b64encode(b'It still works!').decode('utf-8')),
        )
        self.assertEqual(b'', data_types.get_typed_value('bytes', ''))
        self.assertEqual(b'', data_types.get_typed_value('bytes', None))
        self.assertEqual(b'', data_types.get_typed_value('base64_bytes', ''))
        self.assertEqual(b'', data_types.get_typed_value('base64_bytes', None))

    def test_string(self):
        self.assertEqual('Hello', data_types.get_typed_value('str', 'Hello'))
        self.assertEqual('Cool! \U0001f61c', data_types.get_typed_value('str', 'Cool! \U0001f61c'))
        self.assertEqual(
            'Still works \u000B yo',
            data_types.get_typed_value('encoded_ascii', 'Still works \\x0b yo'),
        )
        self.assertEqual(six.text_type, type(data_types.get_typed_value('encoded_ascii', 'Still works \\x0b yo')))
        self.assertEqual(
            'And another one works \U0001f61c',
            data_types.get_typed_value('encoded_unicode', 'And another one works \\U0001f61c'),
        )
        self.assertEqual(
            six.text_type,
            type(data_types.get_typed_value('encoded_unicode', 'And another one works \\U0001f61c')),
        )
        self.assertEqual('Yes, it works \u000B yo', data_types.get_typed_value('str', b'Yes, it works \x0b yo'))
        self.assertEqual(six.text_type, type(data_types.get_typed_value('str', b'Yes, it works \x0b yo')))
        self.assertEqual('', data_types.get_typed_value('str', b''))
        self.assertEqual('', data_types.get_typed_value('str', ''))
        self.assertEqual('', data_types.get_typed_value('str', None))

    def test_empty_types(self):
        self.assertEqual([], data_types.get_typed_value('emptylist', 'does not matter'))
        self.assertEqual({}, data_types.get_typed_value('emptydict', 'does not matter'))
        self.assertEqual('', data_types.get_typed_value('emptystr', 'does not matter'))

    def test_datetime(self):
        with self.assertRaises(DataTypeConversionError):
            data_types.get_typed_value('datetime', '')

        with self.assertRaises(DataTypeConversionError):
            # noinspection PyTypeChecker
            data_types.get_typed_value('datetime', 123)  # type: ignore

        self.assertEqual(
            datetime.datetime(2014, 11, 6, 5, 37, 51, 172938),
            data_types.get_typed_value('datetime', '2014,11,6,5,37,51,172938'),
        )
        self.assertEqual(
            datetime.datetime(2019, 6, 6, 17, 0, 0, 0),
            data_types.get_typed_value('datetime', '2019,6,6,17'),
        )

        with freezegun.freeze_time(datetime.datetime(2018, 4, 1, 12, 17, 43, 192837)):
            self.assertEqual(
                datetime.datetime(2018, 4, 1, 12, 17, 43),
                data_types.get_typed_value('datetime', 'now')
            )
            self.assertEqual(
                datetime.datetime(2018, 5, 1, 12, 17, 43),
                data_types.get_typed_value('datetime', 'now +30')
            )
            self.assertEqual(
                datetime.datetime(2018, 4, 1, 18, 47, 53, 150),
                data_types.get_typed_value('datetime', 'now 0,6,30,10,150')
            )

            self.assertEqual(
                datetime.datetime(2018, 4, 1, 0, 0, 0),
                data_types.get_typed_value('datetime', 'midnight')
            )
            self.assertEqual(
                datetime.datetime(2018, 5, 1, 0, 0, 0),
                data_types.get_typed_value('datetime', 'midnight +30')
            )
            self.assertEqual(
                datetime.datetime(2018, 4, 1, 6, 30, 10, 150),
                data_types.get_typed_value('datetime', 'midnight 0,6,30,10,150')
            )

            self.assertEqual(
                datetime.datetime.utcnow().replace(microsecond=0, tzinfo=pytz.utc),
                data_types.get_typed_value('datetime', 'utc_now'),
            )

            utc_now = datetime.datetime.utcnow()
            self.assertEqual(
                datetime.datetime(utc_now.year, utc_now.month, utc_now.day, 0, 0, 0).replace(tzinfo=pytz.utc),
                data_types.get_typed_value('datetime', 'utc_midnight'),
            )

    def test_date(self):
        with self.assertRaises(DataTypeConversionError):
            data_types.get_typed_value('date', '')

        with self.assertRaises(DataTypeConversionError):
            # noinspection PyTypeChecker
            data_types.get_typed_value('date', 123)  # type: ignore

        self.assertEqual(datetime.date(1986, 11, 5), data_types.get_typed_value('date', '1986,11,5'))
        self.assertEqual(datetime.date(2000, 1, 1), data_types.get_typed_value('date', '2000,1,1'))
        self.assertEqual(datetime.date.today(), data_types.get_typed_value('date', 'today'))
        self.assertEqual(datetime.datetime.utcnow().date(), data_types.get_typed_value('date', 'utc_today'))

    def test_time(self):
        with self.assertRaises(DataTypeConversionError):
            data_types.get_typed_value('time', '')

        with self.assertRaises(DataTypeConversionError):
            # noinspection PyTypeChecker
            data_types.get_typed_value('time', 123)  # type: ignore

        self.assertEqual(datetime.time(13, 11, 5), data_types.get_typed_value('time', '13,11,5'))
        self.assertEqual(datetime.time(3, 14, 16), data_types.get_typed_value('time', '3,14,16'))
        self.assertEqual(datetime.time(0, 0, 0), data_types.get_typed_value('time', 'midnight'))
        self.assertEqual(datetime.time(2, 32, 47), data_types.get_typed_value('time', 'midnight +0,26,32,47'))
        self.assertEqual(datetime.time(0, 30, 0), data_types.get_typed_value('time', 'midnight 0,0,30'))

        with freezegun.freeze_time(datetime.datetime(2018, 4, 1, 12, 17, 43, 192837)):
            self.assertEqual(datetime.time(12, 17, 43), data_types.get_typed_value('time', 'now'))
            self.assertEqual(datetime.time(18, 17, 43), data_types.get_typed_value('time', 'now +0,6'))
            self.assertEqual(
                datetime.datetime.utcnow().replace(microsecond=0).time(),
                data_types.get_typed_value('time', 'utc_now'),
            )

    def test_unknown(self):
        with self.assertRaises(DataTypeConversionError):
            data_types.get_typed_value('unknown type', 'does not matter')
