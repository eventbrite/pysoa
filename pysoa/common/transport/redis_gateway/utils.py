from __future__ import (
    absolute_import,
    unicode_literals,
)

import six


def make_redis_queue_name(service_name):  # type: (six.text_type) -> six.text_type
    return 'service.' + service_name
