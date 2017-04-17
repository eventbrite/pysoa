from __future__ import unicode_literals

from pysoa.common.transport.base import ServerTransport
from pysoa.common.transport.exceptions import InvalidMessageError


from .utils import make_channel_name
from .core import ASGITransportCore


class ASGIServerTransport(ServerTransport):

    def __init__(self, service_name, **kwargs):
        self.service_name = service_name
        self.receive_channel_name = make_channel_name(service_name)
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
