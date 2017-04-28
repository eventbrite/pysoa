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

    mime_type = 'application/msgpack'

    EXT_DATETIME = 1
    EXT_CURRINT = 2

    STRUCT_DATETIME = struct.Struct('!q')
    STRUCT_CURRINT = struct.Struct('!3sq')

    def dict_to_blob(self, data_dict):
        assert isinstance(data_dict, dict), 'Input must be a dict'
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
            # Datetimes. Make sure it's naive.
            if obj.tzinfo is not None:
                raise TypeError("Cannot encode timezone-aware datetimes to msgpack")
            # Then, work out the timestamp in seconds
            seconds = (obj - datetime.datetime(1970, 1, 1)).total_seconds()
            microseconds = int(seconds * 1000000)
            # Then pack it into a big-endian signed 64-bit integer
            return msgpack.ExtType(self.EXT_DATETIME, self.STRUCT_DATETIME.pack(microseconds))
        elif isinstance(obj, currint.Amount):
            # Currint. Start with the lowercased currency code as bytes
            code = obj.currency.code.upper()
            if isinstance(code, six.text_type):
                code = code.encode("ascii")
            # Then pack it in with the minor value
            return msgpack.ExtType(self.EXT_CURRINT, self.STRUCT_CURRINT.pack(code, obj.value))
        else:
            # Wuh-woh
            raise TypeError("Cannot encode value to msgpack: %r" % (obj,))

    def ext_hook(self, code, data):
        """
        Decodes our custom extension types
        """
        if code == self.EXT_DATETIME:
            # Unpack datetime from a big-endian signed 64-bit integer
            microseconds = self.STRUCT_DATETIME.unpack(data)[0]
            return datetime.datetime.utcfromtimestamp(microseconds / 1000000.0)
        elif code == self.EXT_CURRINT:
            # Unpack currint into (code, minor)
            code, minor_value = self.STRUCT_CURRINT.unpack(data)
            return currint.Amount.from_code_and_minor(code.decode("ascii"), minor_value)
        else:
            raise TypeError("Cannot decode unknown extension type %i" % code)
