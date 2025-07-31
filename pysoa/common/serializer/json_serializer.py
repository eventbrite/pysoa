from __future__ import (
    absolute_import,
    unicode_literals,
)

import json
from typing import Dict, Any

from conformity import fields
import six

from pysoa.common.serializer.base import Serializer as BaseSerializer
from pysoa.common.serializer.errors import (
    InvalidField,
    InvalidMessage,
)


__all__ = (
    'JSONSerializer',
)


@fields.ClassConfigurationSchema.provider(
    fields.Dictionary({}, description='The JSON serializer has no constructor args'),
)
class JSONSerializer(BaseSerializer):
    """
    Serializes messages to/from JSON.

    Types supported: int, str, dict, list, tuple

    Note that this serializer makes no distinction between tuples
    and lists, and will always deserialize either type as a list.
    """
    mime_type = 'application/json'

    def dict_to_blob(self, data_dict):  # type: (Dict) -> six.binary_type
        if not isinstance(data_dict, dict):
            raise ValueError('Input must be a dict')
        try:
            return json.dumps(data_dict).encode('utf-8')
        except TypeError as e:
            raise InvalidField(
                "Can't serialize message due to {}: {}".format(str(type(e).__name__), str(e)),
                *e.args
            )

    def blob_to_dict(self, blob: bytes) -> dict:
        try:
            if six.PY3 and isinstance(blob, six.binary_type):
                result = json.loads(blob.decode('utf-8'))
            else:
                result = json.loads(blob)
            if not isinstance(result, dict):
                raise InvalidMessage('Deserialized blob is not a dict')
            return result
        except (ValueError, TypeError) as e:
            raise InvalidMessage(
                "Can't deserialize message due to {}: {}".format(str(type(e).__name__), str(e)),
                *e.args
            )
