from __future__ import unicode_literals

import uuid
import re

from pysoa.common.transport.base import ClientTransport

from .utils import make_channel_name
from .core import ASGITransportCore


class ASGIClientTransport(ClientTransport):

    def __init__(self, service_name, metrics, asgi_channel_type, request_channel_capacity=10000, **kwargs):
        super(ASGIClientTransport, self).__init__(service_name, metrics)

        self.client_id = uuid.uuid4().hex
        self.send_channel_name = make_channel_name(service_name)
        self.receive_channel_name = '{}.{}!'.format(
            self.send_channel_name,
            self.client_id,
        )
        self.requests_outstanding = 0
        if request_channel_capacity:
            # Each client transport sends on only one channel, so add that to channel_capacities
            kwargs['channel_capacities'] = {
                re.compile(r'service\.' + service_name + r'$'): request_channel_capacity,
            }
        self.core = ASGITransportCore(asgi_channel_type, **kwargs)

    def send_request_message(self, request_id, meta, body):
        self.requests_outstanding += 1
        meta['reply_to'] = '{}{}'.format(
            self.receive_channel_name,
            request_id,
        )
        self.core.send_message(self.send_channel_name, request_id, meta, body)

    def receive_response_message(self):
        if self.requests_outstanding > 0:
            request_id, meta, response = self.core.receive_message(self.receive_channel_name)
            self.requests_outstanding -= 1
            return request_id, meta, response
        else:
            # This tells Client.get_all_responses to stop waiting for more
            return None, None, None
