from __future__ import unicode_literals


# Common Redis constants for discovery and transport classes
REDIS_BACKEND_TYPE_STANDARD = 'redis.standard'
REDIS_BACKEND_TYPE_SENTINEL = 'redis.sentinel'

REDIS_BACKEND_TYPES = (
    REDIS_BACKEND_TYPE_STANDARD,
    REDIS_BACKEND_TYPE_SENTINEL,
)
