from __future__ import absolute_import

import abc

import six


@six.add_metaclass(abc.ABCMeta)
class Serializer(object):

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
