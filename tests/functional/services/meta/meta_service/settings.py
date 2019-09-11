from pysoa.common.transport.redis_gateway.constants import REDIS_BACKEND_TYPE_STANDARD

SOA_SERVER_SETTINGS = {
    'heartbeat_file': '/srv/meta_service-{{fid}}.heartbeat',
    'middleware': [],  # TODO
    'transport': {
        'path': 'pysoa.common.transport.redis_gateway.server:RedisServerTransport',
        'kwargs': {
            'backend_layer_kwargs': {'hosts': [('redis.pysoa', 6379)]},
            'backend_type': REDIS_BACKEND_TYPE_STANDARD,
            'chunk_messages_larger_than_bytes': 102400,
            'maximum_message_size_in_bytes': 1048576,
            'log_messages_larger_than_bytes': 800000,
        },
    },
}
