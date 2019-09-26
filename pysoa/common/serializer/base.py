from __future__ import (
    absolute_import,
    unicode_literals,
)

import abc
from typing import (
    Dict,
    FrozenSet,
    Type,
)

import six


__all__ = (
    'Serializer',
)


class _SerializerMeta(abc.ABCMeta):
    _mime_type_to_serializer_map = {}  # type: Dict[six.text_type, Type[Serializer]]
    _all_supported_mime_types = frozenset()  # type: FrozenSet[six.text_type]

    def __new__(mcs, name, bases, body):
        # Don't allow multiple inheritance as it mucks up mime-type collection
        if len(bases) != 1:
            raise ValueError('You cannot use multiple inheritance with Serializers')

        cls = super(_SerializerMeta, mcs).__new__(mcs, name, bases, body)

        if bases and bases[0] is not object:
            if not issubclass(cls, Serializer):
                raise TypeError('The internal _SerializerMeta is only valid on Serializers')

            if not cls.mime_type or not cls.mime_type.strip():
                raise ValueError('All serializers must have a non-null, non-blank MIME type')

            if cls.mime_type in mcs._all_supported_mime_types:
                raise ValueError('Another serializer {cls} already supports mime type {mime_type}'.format(
                    cls=mcs._mime_type_to_serializer_map[cls.mime_type],
                    mime_type=cls.mime_type,
                ))

            mcs._mime_type_to_serializer_map[cls.mime_type] = cls
            mcs._all_supported_mime_types = frozenset(mcs._mime_type_to_serializer_map.keys())

        return cls

    @property
    def all_supported_mime_types(cls):  # type: () -> FrozenSet[six.text_type]
        """
        Return all mime types supported by all implementations of `Serializer`.

        :return: A frozen set of mime types.
        """
        return cls._all_supported_mime_types


@six.add_metaclass(_SerializerMeta)
class Serializer(object):

    """
    The mime type that this serializer supports.
    """
    mime_type = None  # type: six.text_type

    @classmethod
    def resolve_serializer(cls, mime_type):  # type: (six.text_type) -> Serializer
        """
        Given the requested mime type, return an initialized `Serializer` that understands that mime type.

        :param mime_type: The mime type for which to get a compatible `Serializer`

        :return: A compatible `Serializer`.

        :raises: ValueError if there is no `Serializer` that understands this mime type.
        """
        if mime_type not in cls.all_supported_mime_types:
            raise ValueError('Mime type {} is not supported'.format(mime_type))
        return cls._mime_type_to_serializer_map[mime_type]()

    @abc.abstractmethod
    def dict_to_blob(self, message_dict):  # type: (Dict) -> six.binary_type
        """
        Take a message in the form of a dict and return a serialized message in the form of bytes (string).

        :param message_dict: The message to serialize into a blob.

        :return: The serialized blob.
        """

    @abc.abstractmethod
    def blob_to_dict(self, blob):  # type: (six.binary_type) -> Dict
        """
        Take a serialized message in the form of bytes (string) and return a dict.

        :param blob: The blob to deserialize into a message

        :return: The deserialized message.
        """
