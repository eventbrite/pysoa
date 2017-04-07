from pysoa.test.stub_service import (
    StubClientTransport,
    NoopSerializer,
)

import pytest


@pytest.fixture()
def client_transport():
    return StubClientTransport()


@pytest.fixture()
def serializer():
    return NoopSerializer()
