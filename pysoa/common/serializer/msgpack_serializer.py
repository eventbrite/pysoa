# do not import unicode_literals in this file
from __future__ import (
    absolute_import,
    division,
)

import datetime
import decimal
import struct

import currint
import msgpack
import six

from pysoa.common.serializer.base import Serializer as BaseSerializer
from pysoa.common.serializer.exceptions import (
    InvalidField,
    InvalidMessage,
)


class MsgpackSerializer(BaseSerializer):
    """
    Serializes messages to/from MessagePack.

    Types supported: int, str, dict, list, tuple, bytes, currint.Amount, datetime.date, datetime.datetime,
    datetime.time, and decimal.Decimal (note that, on Python 2, str means unicode and bytes means str)

    Note that this serializer makes no distinction between tuples and lists, and will always deserialize either type as
    a list.

    It implements these custom ext types:

    1. Date-times with microsecond precision (must not be time zone-aware)

       Encoded as an 8-byte big-endian signed integer (long long) of the number of microseconds since midnight on
       January 1, 1970 (the Unix epoch).

    2. Simple dates

       Encoded big-endian as 2-byte unsigned integer year followed by 1-byte unsigned integers (chars) month and day.

    3. Simple times with microsecond precision

       Encoded big-endian as 1-byte unsigned integers (chars) hour, minute, and second followed by 4-byte unsigned
       integer (long) microseconds.

    4. decimal.Decimal objects

       Encoded big-endian as a 2-byte unsigned integer indicating the decimal string length in bytes followed by an
       ASCII string of that many bytes (as such, all decimals will be truncated to 65,535 total digits/bytes
       including the optional sign and decimal point characters).

    5. Currint amount and currency

       Encoded as a 3-byte ASCII string of the uppercased currency code concatenated with a 8-byte big-endian signed
       integer of the minor value.
    """

    mime_type = u'application/msgpack'

    EXT_CURRINT = 2
    EXT_DATE = 3
    EXT_DATETIME = 1
    EXT_DECIMAL = 5
    EXT_TIME = 4

    STRUCT_CURRINT = struct.Struct('!3sq')
    STRUCT_DATE = struct.Struct('!HBB')
    STRUCT_DATETIME = struct.Struct('!q')
    STRUCT_DECIMAL_LENGTH = struct.Struct('!H')
    STRUCT_TIME = struct.Struct('!3BL')

    def dict_to_blob(self, data_dict):
        assert isinstance(data_dict, dict), u'Input must be a dict'
        try:
            return msgpack.packb(data_dict, default=self.default, use_bin_type=True)
        except TypeError as e:
            raise InvalidField(*e.args)

    def blob_to_dict(self, blob):
        try:
            return msgpack.unpackb(blob, raw=False, ext_hook=self.ext_hook)
        except (TypeError, msgpack.UnpackValueError, msgpack.ExtraData) as e:
            raise InvalidMessage(*e.args)

    def default(self, obj):
        """
        Encodes unknown object types (we use it to make extended types)
        """
        if isinstance(obj, datetime.datetime):
            # Serialize date-time objects. Make sure they're naive.
            if obj.tzinfo is not None:
                raise TypeError(u'Cannot encode time zone-aware date-times to MessagePack')
            # Then, work out the timestamp in seconds.
            seconds = (obj - datetime.datetime(1970, 1, 1)).total_seconds()
            microseconds = int(seconds * 1000000.0)
            # Then pack it into a big-endian signed 64-bit integer.
            return msgpack.ExtType(
                self.EXT_DATETIME,
                self.STRUCT_DATETIME.pack(microseconds),
            )
        elif isinstance(obj, datetime.date):
            # Serialize local-date objects by packing to a big-endian unsigned short and two big-endian unsigned chars.
            return msgpack.ExtType(
                self.EXT_DATE,
                self.STRUCT_DATE.pack(obj.year, obj.month, obj.day),
            )
        elif isinstance(obj, datetime.time):
            # Serialize dateless-time objects by packing to three big-endian unsigned chars and a big-endian unsigned
            # 32-bit integer.
            return msgpack.ExtType(
                self.EXT_TIME,
                self.STRUCT_TIME.pack(obj.hour, obj.minute, obj.second, obj.microsecond),
            )
        elif isinstance(obj, decimal.Decimal):
            obj_str = six.text_type(obj)[:65535].encode('utf-8')
            obj_len = len(obj_str)
            obj_encoder = struct.Struct('!H{}s'.format(obj_len))
            return msgpack.ExtType(
                self.EXT_DECIMAL,
                obj_encoder.pack(obj_len, obj_str),
            )
        elif isinstance(obj, currint.Amount):
            # Serialize Amount objects. Start with the lowercased currency code as bytes.
            code = obj.currency.code.upper()
            if isinstance(code, six.text_type):
                code = code.encode('ascii')
            # Then pack it in with the minor value.
            return msgpack.ExtType(
                self.EXT_CURRINT,
                self.STRUCT_CURRINT.pack(code, obj.value),
            )
        else:
            # Wuh-woh
            raise TypeError(u'Cannot encode value of type {} to MessagePack: {}'.format(type(obj).__name__, obj))

    def ext_hook(self, code, data):
        """
        Decodes our custom extension types
        """
        if code == self.EXT_DATETIME:
            # Unpack datetime object from a big-endian signed 64-bit integer.
            microseconds = self.STRUCT_DATETIME.unpack(data)[0]
            return datetime.datetime.utcfromtimestamp(microseconds / 1000000.0)
        elif code == self.EXT_DATE:
            # Unpack local-date object from a big-endian unsigned short and two big-endian unsigned chars
            return datetime.date(*self.STRUCT_DATE.unpack(data))
        elif code == self.EXT_TIME:
            # Unpack a dateless-time object from three big-endian unsigned chars and a big-endian unsigned
            # 32-bit integer.
            return datetime.time(*self.STRUCT_TIME.unpack(data))
        elif code == self.EXT_DECIMAL:
            obj_len = self.STRUCT_DECIMAL_LENGTH.unpack(data[:2])[0]
            obj_decoder = struct.Struct('!{}s'.format(obj_len))
            return decimal.Decimal(obj_decoder.unpack(data[2:])[0].decode('utf-8'))
        elif code == self.EXT_CURRINT:
            # Unpack Amount object into (code, minor) from a 3-char ASCII string and a signed 64-bit integer.
            code, minor_value = self.STRUCT_CURRINT.unpack(data)
            return currint.Amount.from_code_and_minor(code.decode('ascii'), minor_value)
        else:
            raise TypeError(u'Cannot decode unknown extension type {} from MessagePack'.format(code))
