from __future__ import unicode_literals

import six


def make_channel_name(service_name):
    channel_name = 'service.' + service_name
    if six.PY2:
        channel_name = unicode(channel_name)
    return channel_name
