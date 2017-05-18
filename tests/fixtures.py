from pysoa.test.stub_service import StubClientTransport
from pysoa.common.serializer.msgpack_serializer import MsgpackSerializer

import pytest


@pytest.fixture()
def client_transport():
    return StubClientTransport()


@pytest.fixture()
def serializer():
    return MsgpackSerializer()
