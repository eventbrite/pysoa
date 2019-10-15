from __future__ import (
    absolute_import,
    unicode_literals,
)

import json
import time
import redis


def get_redis_client():
    return redis.StrictRedis(host='redis', port=6379, db=0)


def make_service_route_map_name(service, route_map):
    return 'route_map.' + route_map + '.apps.' + service


def make_token_route(token):
    return 'route_map.token.' + str(token)


def make_mangled_services_route_map(service_name, mangled_service_name):
    return 'route_map.mangled_services.' + service_name + '.' + mangled_service_name


def get_route_map_for_token(token):
    key = make_token_route(token)
    redisClient = get_redis_client()
    record = redisClient.get(key)
    if record:
        record = json.loads(record.decode('utf-8'))
        return record.get('route_map')
    return None


def get_route_map_server_queue(service, route_map):
    key = make_service_route_map_name(service, route_map)
    redisClient = get_redis_client()
    record = redisClient.get(key)
    if record:
        record = json.loads(record.decode('utf-8'))
        return record.get('mangled_name', None)
    return None


def set_mangled_service_data_route_map(service_name, mangled_service_name):
    key = make_mangled_services_route_map(service_name, mangled_service_name)
    redisClient = get_redis_client()
    record = redisClient.get(key)
    requests = '0'
    if record:
        stats = json.loads(record.decode('utf-8'))
        requests = int(stats.get('requests')) + 1

    data = {
        'ts': time.time(),
        'requests': requests,
        'host': '',
    }
    redisClient.set(key, json.dumps(data), ex=86400)
    return data


def make_redis_queue_name(service_name):  # type: (six.text_type) -> six.text_type
    return 'service.' + service_name
