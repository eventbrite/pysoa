from pysoa.common.serializer.base import Serializer as BaseSerializer
from pysoa.common.serializer.exceptions import (
    InvalidMessage,
    InvalidField,
)

import json
import six


class JSONSerializer(BaseSerializer):
    """
    Serializes messages to/from JSON.

    Types supported: int, str, dict, list, tuple

    Note that this serializer makes no distinction between tuples
    and lists, and will always deserialize either type as a list.
    """
    mime_type = 'application/json'

    def dict_to_blob(self, data_dict):
        assert isinstance(data_dict, dict), 'Input must be a dict'
        try:
            return json.dumps(data_dict)
        except TypeError as e:
            raise InvalidField(*e.args)

    def blob_to_dict(self, blob):
        try:
            if six.PY3 and isinstance(blob, six.binary_type):
                blob = blob.decode('utf-8')
            return json.loads(blob)
        except (ValueError, UnicodeDecodeError) as e:
            raise InvalidMessage(*e.args)
