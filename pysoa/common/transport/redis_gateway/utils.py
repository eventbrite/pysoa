from __future__ import (
    absolute_import,
    unicode_literals,
)

import six  # noqa: F401 TODO Python 3


def make_redis_queue_name(service_name):  # type: (six.text_type) -> six.text_type
    return 'service.' + service_name
