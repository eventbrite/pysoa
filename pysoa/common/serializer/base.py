from __future__ import absolute_import

import abc

import six


__all__ = (
    'Serializer',
)


class _SerializerMeta(abc.ABCMeta):
    _mime_type_to_serializer_map = {}
    _all_supported_mime_types = frozenset()

    def __new__(mcs, name, bases, body):
        # Don't allow multiple inheritance as it mucks up mime-type collection
        if len(bases) != 1:
            raise ValueError('You cannot use multiple inheritance with Serializers')
        # Make the new class
        cls = super(_SerializerMeta, mcs).__new__(mcs, name, bases, body)

        if bases[0] is not object:
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
    def all_supported_mime_types(cls):
        return cls._all_supported_mime_types


@six.add_metaclass(_SerializerMeta)
class Serializer(object):

    mime_type = None

    @classmethod
    def resolve_serializer(cls, mime_type):
        if mime_type not in cls.all_supported_mime_types:
            raise ValueError('Mime type {} is not supported'.format(mime_type))
        return cls._mime_type_to_serializer_map[mime_type]()

    @abc.abstractmethod
    def dict_to_blob(self, message_dict):
        """
        Take a message in the form of a dict and return a serialized message in the form of bytes (string).

        Returns:
            string
        Raises:
            InvalidField
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def blob_to_dict(self, blob):
        """
        Take a serialized message in the form of bytes (string) and return a dict.

        Returns:
            dict
        Raises:
            InvalidMessage
        """
        raise NotImplementedError()
