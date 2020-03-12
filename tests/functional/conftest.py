from __future__ import (
    absolute_import,
    unicode_literals,
)

import copy
from typing import Dict

from conformity.settings import SettingsData
import pytest

from pysoa.client.client import Client
from pysoa.common.transport.redis_gateway.constants import (
    REDIS_BACKEND_TYPE_SENTINEL,
    REDIS_BACKEND_TYPE_STANDARD,
    ProtocolVersion,
)


_base_config = {
    'echo': {
        'transport': {
            'path': 'pysoa.common.transport.redis_gateway.client:RedisClientTransport',
            'kwargs': {
                'backend_layer_kwargs': {
                    'hosts': [
                        ('standalone.redis5.pysoa', 6379),
                        ('standalone.redis6.pysoa', 6379),
                    ],
                },
                'backend_type': REDIS_BACKEND_TYPE_STANDARD,
            },
        },
    },
    'meta': {
        'transport': {
            'path': 'pysoa.common.transport.redis_gateway.client:RedisClientTransport',
            'kwargs': {
                'backend_layer_kwargs': {
                    'hosts': [
                        ('sentinel1.redis5.pysoa', 26379),
                        ('sentinel2.redis5.pysoa', 26379),
                        ('sentinel3.redis5.pysoa', 26379),
                    ],
                    'sentinel_failover_retries': 7,
                },
                'backend_type': REDIS_BACKEND_TYPE_SENTINEL,
            },
        },
    },
    'user': {
        'transport': {
            'path': 'pysoa.common.transport.redis_gateway.client:RedisClientTransport',
            'kwargs': {
                'backend_layer_kwargs': {
                    'hosts': [
                        ('sentinel1.redis6.pysoa', 56379),
                        ('sentinel2.redis6.pysoa', 56379),
                        ('sentinel3.redis6.pysoa', 56379),
                    ],
                    'connection_kwargs': {
                        'username': 'user_service_client',
                        'password': 'VfPF3YQ4BLwhAWF7tjvntn76dwxJsJzK',
                        'ssl': True,
                        'ssl_ca_certs': '/srv/run/tls/ca.crt',
                        'ssl_certfile': '/srv/run/tls/redis.crt',
                        'ssl_keyfile': '/srv/run/tls/redis.key',
                    },
                    'sentinel_failover_retries': 7,
                    'sentinel_kwargs': {
                        'ssl': True,
                        'ssl_ca_certs': '/srv/run/tls/ca.crt',
                        'ssl_certfile': '/srv/run/tls/redis.crt',
                        'ssl_keyfile': '/srv/run/tls/redis.key',
                    },
                },
                'backend_type': REDIS_BACKEND_TYPE_SENTINEL,
            },
        },
    },
}  # type: Dict[str, SettingsData]

_expansion_config = {
    # TODO
}  # type: SettingsData

_json_serializer = {'path': 'pysoa.common.serializer:JSONSerializer'}  # type: Dict[str, str]


@pytest.fixture(scope='package')
def pysoa_client():  # type: () -> Client
    return Client(
        config=_base_config,
        expansion_config=_expansion_config,
    )


@pytest.fixture(scope='package')
def pysoa_client_protocol_v2():  # type: () -> Client
    config = copy.deepcopy(_base_config)
    config['echo']['transport']['kwargs']['protocol_version'] = ProtocolVersion.VERSION_2
    config['meta']['transport']['kwargs']['protocol_version'] = ProtocolVersion.VERSION_2
    config['user']['transport']['kwargs']['protocol_version'] = ProtocolVersion.VERSION_2

    return Client(
        config=config,
        expansion_config=_expansion_config,
    )


@pytest.fixture(scope='package')
def pysoa_client_json():  # type: () -> Client
    config = copy.deepcopy(_base_config)
    config['echo']['transport']['kwargs']['default_serializer_config'] = _json_serializer
    config['meta']['transport']['kwargs']['default_serializer_config'] = _json_serializer
    config['user']['transport']['kwargs']['default_serializer_config'] = _json_serializer

    return Client(
        config=config,
        expansion_config=_expansion_config,
    )
