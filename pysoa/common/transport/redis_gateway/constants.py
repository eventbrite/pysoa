from __future__ import (
    absolute_import,
    unicode_literals,
)

import enum
import re
from typing import Tuple  # noqa: F401 TODO Python 3

import six  # noqa: F401 TODO Python 3


__all__ = (
    'DEFAULT_MAXIMUM_MESSAGE_BYTES_CLIENT',
    'DEFAULT_MAXIMUM_MESSAGE_BYTES_SERVER',
    'MINIMUM_CHUNKED_MESSAGE_BYTES',
    'ProtocolFeature',
    'ProtocolVersion',
    'REDIS_BACKEND_TYPE_SENTINEL',
    'REDIS_BACKEND_TYPE_STANDARD',
    'REDIS_BACKEND_TYPES',
)


# Common Redis constants for discovery and transport classes
REDIS_BACKEND_TYPE_STANDARD = 'redis.standard'
REDIS_BACKEND_TYPE_SENTINEL = 'redis.sentinel'

REDIS_BACKEND_TYPES = (
    REDIS_BACKEND_TYPE_STANDARD,
    REDIS_BACKEND_TYPE_SENTINEL,
)

DEFAULT_MAXIMUM_MESSAGE_BYTES_CLIENT = 1024 * 100
DEFAULT_MAXIMUM_MESSAGE_BYTES_SERVER = 1024 * 250
MINIMUM_CHUNKED_MESSAGE_BYTES = 1024 * 100


PROTOCOL_VERSION_RE = re.compile(b'pysoa-redis/(?P<version>[0-9]+)//')


class ProtocolVersion(enum.IntEnum):
    VERSION_1 = 1
    VERSION_2 = 2
    VERSION_3 = 3

    @property
    def prefix(self):  # type: () -> six.binary_type
        return b'pysoa-redis/%d//' % self.value

    @staticmethod
    def extract_version(message_data):  # type: (six.binary_type) -> Tuple[ProtocolVersion, six.binary_type]
        match = PROTOCOL_VERSION_RE.match(message_data)
        if match:
            return ProtocolVersion(int(match.group('version'))), message_data[match.end():]
        if message_data.startswith(b'content-type'):
            return ProtocolVersion.VERSION_2, message_data
        return ProtocolVersion.VERSION_1, message_data


class ProtocolFeature(enum.Enum):
    CONTENT_TYPE_HEADER = (1, ProtocolVersion.VERSION_2)
    VERSION_MARKER = (2, ProtocolVersion.VERSION_3)
    CHUNKED_RESPONSES = (3, ProtocolVersion.VERSION_3)

    def supported_in(self, version):  # type: (ProtocolVersion) -> bool
        return version >= self.value[1]
