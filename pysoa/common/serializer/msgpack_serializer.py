import currint
import datetime
import six
import struct

from pysoa.common.serializer.base import Serializer as BaseSerializer
from pysoa.common.serializer.exceptions import (
    InvalidMessage,
    InvalidField,
)

import msgpack


class MsgpackSerializer(BaseSerializer):
    """
    Serializes messages to/from MessagePack.

    Types supported: int, str, dict, list, tuple, bytes
    (Note that on Python 2, str->unicode and bytes->str)

    Note that this serializer makes no distinction between tuples
    and lists, and will always deserialize either type as a list.

    It implements these custom ext types:
        1: Datetimes with second precision.
           Encoded as an 8-byte big-endian signed integer of the number of microseconds
           since the epoch.
        2: Currint amount and currency
           Encoded as a 3-byte ASCII string of the uppercased currency code concatenated with
           a 8-byte big-endian signed integer of the minor value.
    """

    mime_type = u'application/msgpack'

    EXT_DATETIME = 1
    EXT_DATE = 3
    EXT_TIME = 4
    EXT_CURRINT = 2

    STRUCT_DATETIME = struct.Struct('!q')
    STRUCT_DATE = struct.Struct('!HBB')
    STRUCT_TIME = struct.Struct('!3BL')
    STRUCT_CURRINT = struct.Struct('!3sq')

    def dict_to_blob(self, data_dict):
        assert isinstance(data_dict, dict), u'Input must be a dict'
        try:
            return msgpack.packb(data_dict, default=self.default, use_bin_type=True)
        except TypeError as e:
            raise InvalidField(*e.args)

    def blob_to_dict(self, blob):
        try:
            return msgpack.unpackb(blob, encoding='utf-8', ext_hook=self.ext_hook)
        except (TypeError, msgpack.UnpackValueError, msgpack.ExtraData) as e:
            raise InvalidMessage(*e.args)

    def default(self, obj):
        """
        Encodes unknown object types (we use it to make extended types)
        """
        if isinstance(obj, datetime.datetime):
            # Serialize date-time objects. Make sure they're naive.
            if obj.tzinfo is not None:
                raise TypeError(u'Cannot encode timezone-aware datetimes to msgpack')
            # Then, work out the timestamp in seconds.
            seconds = (obj - datetime.datetime(1970, 1, 1)).total_seconds()
            microseconds = int(seconds * 1000000)
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
            raise TypeError(u'Cannot encode value to msgpack: %r' % (obj,))

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
        elif code == self.EXT_CURRINT:
            # Unpack Amount object into (code, minor) from a 3-char ASCII string and a signed 64-bit integer.
            code, minor_value = self.STRUCT_CURRINT.unpack(data)
            return currint.Amount.from_code_and_minor(code.decode('ascii'), minor_value)
        else:
            raise TypeError(u'Cannot decode unknown extension type %i' % code)
