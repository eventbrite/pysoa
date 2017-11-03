from __future__ import unicode_literals


def make_redis_queue_name(service_name):
    return 'service.' + service_name
