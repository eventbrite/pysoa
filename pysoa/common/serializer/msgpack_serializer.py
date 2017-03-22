from pysoa.common.serializer.base import Serializer as BaseSerializer
from pysoa.common.serializer.exceptions import (
    InvalidMessage,
    InvalidField,
)

import msgpack


class MsgpackSerializer(BaseSerializer):
    """
    Serializes messages to/from MessagePack.

    Types supported: int, str, dict, list, tuple, bytes (py3)

    Note that this serializer makes no distinction between tuples
    and lists, and will always deserialize either type as a list.
    """
    mime_type = 'application/msgpack'

    def dict_to_blob(self, data_dict):
        assert isinstance(data_dict, dict), 'Input must be a dict'
        try:
            return msgpack.packb(data_dict)
        except TypeError as e:
            raise InvalidField(*e.args)

    def blob_to_dict(self, blob):
        try:
            return msgpack.unpackb(blob, encoding='utf-8')
        except (TypeError, msgpack.UnpackValueError, msgpack.ExtraData) as e:
            raise InvalidMessage(*e.args)
