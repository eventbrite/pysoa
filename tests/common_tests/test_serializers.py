from __future__ import unicode_literals

import datetime

import currint
import pytest

from pysoa.common.serializer import (
    JSONSerializer,
    MsgpackSerializer,
)
from pysoa.common.serializer.exceptions import (
    InvalidMessage,
    InvalidField,
)


serializer_classes = [JSONSerializer, MsgpackSerializer]


@pytest.fixture(params=serializer_classes)
def serializer(request):
    return request.param()


class TestSerializers():
    """Tests that apply to all serializers."""

    @pytest.mark.parametrize('data', [
        {'int_key': 1},
        {'str_key': 'string'},
        {'unicode_key': '\U0001f37a'},
        {'list_key': [1, 'two']},
        {'dict_key': {'one': 1, 'two': 'foo'}},
    ])
    def test_serialize_deserialize_supported_types(self, data, serializer):
        """
        These types are (de)serializable by all serializers. Some serializers (e.g. msgpack)
        will be able to serialize other types, but this is the minimum set.
        """
        message = serializer.dict_to_blob(data)
        deserialized_message = serializer.blob_to_dict(message)
        for key, val in data.items():
            assert (deserialized_message[key] == val), '{} != {} for {}'.format(
                deserialized_message[key], val, serializer
            )

    @pytest.mark.parametrize('invalid_input', [
        'invalid',
        ['invalid'],
        ('invalid'),
        {'invalid'},
        0,
        False,
    ])
    def test_input_must_be_dict(self, serializer, invalid_input):
        with pytest.raises(Exception):
            serializer.dict_to_blob(invalid_input)

    def test_serialze_custom_type_fails(self, serializer):
        """Custom classes will always fail to serialize."""
        class Unserializable:
            pass

        with pytest.raises(InvalidField):
            serializer.dict_to_blob({'unserializable': Unserializable()})

    def test_deserialize_invalid_message(self, serializer):
        invalid_message = 'this is an invalid message! for shame!'

        with pytest.raises(InvalidMessage):
            serializer.blob_to_dict(invalid_message)

    def test_serialize_set_fails(self, serializer):
        with pytest.raises(InvalidField):
            serializer.dict_to_blob({'unserializable': {'foo', 'bar'}})

    def test_serialize_tuple(self, serializer):
        """
        Test that the returned iterable has the same values in the same order as the input tuple. The type
        of the returned iterable is NOT guaranteed (it may be a list (in fact, it will be a list)).
        """
        input_tuple = (1, 'two')
        input_dict = {'tuple_key': input_tuple}
        result_dict = serializer.blob_to_dict(serializer.dict_to_blob(input_dict))
        result_tuple = result_dict['tuple_key']
        assert len(result_tuple) == len(input_tuple)
        assert all(result_tuple[i] == input_tuple[i] for i in range(len(result_tuple)))


class TestMsgpackSerializer():
    """
    Tests specifically for the MessagePack serializer.
    """

    def test_bytes_preservation(self):
        """
        Tests that bytestrings and unicode strings' types are preserved.
        """
        data = {
            b'bytes_key': b'this is a byte array',
            'unicode_key': 'unicode string!',
        }
        serializer = MsgpackSerializer()
        output = serializer.blob_to_dict(serializer.dict_to_blob(data))
        assert b'bytes_key' in output
        assert 'unicode_key' in output
        assert output[b'bytes_key'] == b'this is a byte array'
        assert output['unicode_key'] == 'unicode string!'

    @pytest.mark.parametrize('value', [
        datetime.datetime(2011, 1, 24),
        datetime.datetime(1970, 1, 1),
        datetime.datetime(2017, 4, 28, 14, 30, 21, 231),
        datetime.datetime(3, 1, 1, 5, 30),
        datetime.datetime(9998, 3, 27, 1, 45),
    ])
    def test_datetime(self, value):
        serializer = MsgpackSerializer()
        assert serializer.blob_to_dict(serializer.dict_to_blob({'v': value}))['v'] == value

    @pytest.mark.parametrize('value', [
        currint.Amount.from_code_and_minor('EUR', 453),
        currint.Amount.from_code_and_minor('JPY', 10000),
        currint.Amount.from_code_and_minor('USD', -98329048),
    ])
    def test_currint(self, value):
        serializer = MsgpackSerializer()
        assert serializer.blob_to_dict(serializer.dict_to_blob({'v': value}))['v'] == value
