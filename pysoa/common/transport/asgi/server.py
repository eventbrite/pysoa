from __future__ import unicode_literals

import re

from pysoa.common.transport.base import ServerTransport
from pysoa.common.transport.exceptions import InvalidMessageError


from .utils import make_channel_name
from .core import ASGITransportCore


class ASGIServerTransport(ServerTransport):

    def __init__(self, service_name, metrics, response_channel_capacities=None, **kwargs):
        super(ASGIServerTransport, self).__init__(service_name, metrics)

        self.receive_channel_name = make_channel_name(service_name)
        if response_channel_capacities:
            # If response channel capacities are specified, add them to channel_capacities
            # If not specified, they will default to the asgi_redis channel layer default,
            # which is 100.
            kwargs['channel_capacities'] = {
                re.compile(r'^service\.' + svc + r'\.[a-z0-9]{32}!$'): cap
                for svc, cap in response_channel_capacities.items()
            }
        self.core = ASGITransportCore(**kwargs)

    def receive_request_message(self):
        request_id, meta, body = self.core.receive_message(self.receive_channel_name)
        if meta.get('reply_to') is None:
            meta['reply_to'] = self.receive_channel_name
        return (request_id, meta, body)

    def send_response_message(self, request_id, meta, body):
        try:
            channel = meta['reply_to']
        except KeyError:
            raise InvalidMessageError('Missing reply channel')
        self.core.send_message(channel, request_id, meta, body)
