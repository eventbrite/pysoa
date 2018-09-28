from __future__ import absolute_import

import attr

from pysoa.common.types import ActionRequest
from pysoa.server.internal.types import RequestSwitchSet


@attr.s
class EnrichedActionRequest(ActionRequest):
    """
    The action request object that the Server passes to each Action class that it calls.

    Contains all the information from ActionRequest, plus some extra information from the
    JobRequest.
    """
    switches = attr.ib(
        default=attr.Factory(RequestSwitchSet),
        converter=lambda l: l if isinstance(l, RequestSwitchSet) else RequestSwitchSet(l),
    )
    context = attr.ib(default=attr.Factory(dict))
    control = attr.ib(default=attr.Factory(dict))
    client = attr.ib(default=None)
    async_event_loop = attr.ib(default=None)
