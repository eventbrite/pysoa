from __future__ import (
    absolute_import,
    unicode_literals,
)

import subprocess
from typing import List  # noqa: F401 TODO Python 3

import six  # noqa: F401 TODO Python 3

from pysoa.client.client import Client
from pysoa.common.transport.redis_gateway.constants import (
    REDIS_BACKEND_TYPE_SENTINEL,
    REDIS_BACKEND_TYPE_STANDARD,
)


COMPOSE_FILE = 'tests/functional/docker/docker-compose.yaml'


_standard = {
    'backend_layer_kwargs': {'hosts': [('redis.pysoa', 6379)]},
    'backend_type': REDIS_BACKEND_TYPE_STANDARD,
}

_sentinel = {
    'backend_layer_kwargs': {'hosts': [('redis-sentinel.pysoa', 26379)]},
    'backend_type': REDIS_BACKEND_TYPE_SENTINEL,
}


pysoa_client = Client(
    config={
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
    },
    expansion_config={},  # TODO
)


def call_command_in_container(container, command):  # type: (six.text_type, List[six.text_type]) -> six.text_type
    full_command = ['docker-compose', '-f', COMPOSE_FILE, 'exec', '-T', container]
    full_command.extend(command)
    try:
        return subprocess.check_output(full_command, stderr=subprocess.STDOUT).strip().decode('utf-8')
    except subprocess.CalledProcessError as e:
        raise AssertionError(
            'Call to docker-compose failed with exit code {}, stdout: {}'.format(e.returncode, e.output),
        )


def read_file_from_container(container, file_path):  # type: (six.text_type, six.text_type) -> six.text_type
    return call_command_in_container(container, ['cat', file_path])


def write_file_to_container(container, file_path, contents):
    # type: (six.text_type, six.text_type, six.text_type) -> six.text_type
    return call_command_in_container(container, ['simple_write.sh', file_path, contents])


def get_container_process_list(container):  # type: (six.text_type) -> six.text_type
    return call_command_in_container(container, ['ps', 'ax'])
