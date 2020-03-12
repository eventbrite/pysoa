from pysoa.common.transport.redis_gateway.constants import REDIS_BACKEND_TYPE_STANDARD

SOA_SERVER_SETTINGS = {
    'heartbeat_file': '/srv/echo_service-{{fid}}.heartbeat',
    'middleware': [],  # TODO
    'transport': {
        'path': 'pysoa.common.transport.redis_gateway.server:RedisServerTransport',
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
    'harakiri': {
        'timeout': 7,
        'shutdown_grace': 3,
    },
}
