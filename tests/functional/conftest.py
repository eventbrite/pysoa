from __future__ import (
    absolute_import,
    unicode_literals,
)

import copy

import pytest

from pysoa.client.client import Client
from pysoa.common.transport.redis_gateway.constants import (
    REDIS_BACKEND_TYPE_SENTINEL,
    REDIS_BACKEND_TYPE_STANDARD,
    ProtocolVersion,
)


_standard = {
    'backend_layer_kwargs': {'hosts': [('redis.pysoa', 6379)]},
    'backend_type': REDIS_BACKEND_TYPE_STANDARD,
}

_sentinel = {
    'backend_layer_kwargs': {'hosts': [('redis-sentinel.pysoa', 26379)]},
    'backend_type': REDIS_BACKEND_TYPE_SENTINEL,
}

_base_config = {
    'echo': {
        'transport': {
            'path': 'pysoa.common.transport.redis_gateway.client:RedisClientTransport',
            'kwargs': _standard,
        },
    },
    'meta': {
        'transport': {
            'path': 'pysoa.common.transport.redis_gateway.client:RedisClientTransport',
            'kwargs': _standard,
        },
    },
    'user': {
        'transport': {
            'path': 'pysoa.common.transport.redis_gateway.client:RedisClientTransport',
            'kwargs': _sentinel,
        },
    },
}

_expansion_config = {
    # TODO
}

_json_serializer = {'path': 'pysoa.common.serializer:JSONSerializer'}


@pytest.fixture(scope='package')
def pysoa_client():
    return Client(
        config=_base_config,
        expansion_config=_expansion_config,
    )


@pytest.fixture(scope='package')
def pysoa_client_protocol_v3():
    config = copy.deepcopy(_base_config)
    config['echo']['transport']['kwargs']['protocol_version'] = ProtocolVersion.VERSION_3
    config['meta']['transport']['kwargs']['protocol_version'] = ProtocolVersion.VERSION_3
    config['user']['transport']['kwargs']['protocol_version'] = ProtocolVersion.VERSION_3

    return Client(
        config=config,
        expansion_config=_expansion_config,
    )


@pytest.fixture(scope='package')
def pysoa_client_json():
    config = copy.deepcopy(_base_config)
    config['echo']['transport']['kwargs']['default_serializer_config'] = _json_serializer
    config['echo']['transport']['kwargs']['protocol_version'] = ProtocolVersion.VERSION_3
    config['meta']['transport']['kwargs']['default_serializer_config'] = _json_serializer
    config['meta']['transport']['kwargs']['protocol_version'] = ProtocolVersion.VERSION_3
    config['user']['transport']['kwargs']['default_serializer_config'] = _json_serializer
    config['user']['transport']['kwargs']['protocol_version'] = ProtocolVersion.VERSION_3

    return Client(
        config=config,
        expansion_config=_expansion_config,
    )
