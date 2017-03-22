from pysoa.test.stub_service import (
    StubTransport,
    NoopSerializer,
)

import pytest


@pytest.fixture()
def client_transport():
    return StubTransport()


@pytest.fixture()
def serializer():
    return NoopSerializer()
