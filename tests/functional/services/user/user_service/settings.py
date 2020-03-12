from pysoa.common.transport.redis_gateway.constants import REDIS_BACKEND_TYPE_SENTINEL

SECRET_KEY = 'aou8a1ud34pa8ofe4c8tce6geo78hu8o89hu8'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'HOST': 'mysql.pysoa',
        'USER': 'root',
        'PASSWORD': 'functionalTestPassword',
        'NAME': 'user_service',
        'OPTIONS': {
            'charset': 'utf8mb4',
        },
        'CONN_MAX_AGE': 2,
    },
}

CACHES = {
    'request': {
        'BACKEND': 'pysoa.server.django.cache.PySOARequestScopedMemoryCache',
        'LOCATION': 'cerberus-request',
    },
    'process': {
        'BACKEND': 'pysoa.server.django.cache.PySOAProcessScopedMemoryCache',
        'LOCATION': 'cerberus-process',
    },
    'persistent': {
        'BACKEND': 'pysoa.server.django.cache.PySOAProcessScopedMemoryCache',
        'LOCATION': 'cerberus-persistent',
    },
}
CACHES['default'] = CACHES['request']

SOA_SERVER_SETTINGS = {
    'heartbeat_file': '/srv/user_service-{{fid}}.heartbeat',
    'middleware': [],  # TODO
    'transport': {
        'path': 'pysoa.common.transport.redis_gateway.server:RedisServerTransport',
        'kwargs': {
            'backend_layer_kwargs': {
                'hosts': [
                    ('sentinel1.redis6.pysoa', 26379),
                    ('sentinel2.redis6.pysoa', 26379),
                    ('sentinel3.redis6.pysoa', 26379),
                ],
                'connection_kwargs': {
                    'username': 'user_service',
                    'password': 'rnE8W86nr8y362pQF2nc7RKS4UkBL8Yt',
                    'ssl_ca_certs': '/srv/run/tls/ca.crt',
                    'ssl_certfile': '/srv/run/tls/redis.crt',
                    'ssl_keyfile': '/srv/run/tls/redis.key',
                },
            },
            'backend_type': REDIS_BACKEND_TYPE_SENTINEL,
        },
    },
}
