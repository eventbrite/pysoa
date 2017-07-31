import attr

from pysoa.common.types import ActionRequest


@attr.s
class EnrichedActionRequest(ActionRequest):
    """
    The action request object that the Server passes to each Action class that it calls.

    Contains all the information from ActionRequest, plus some extra information from the
    JobRequest.
    """
    switches = attr.ib(default=attr.Factory(list))
    context = attr.ib(default=attr.Factory(dict))
    control = attr.ib(default=attr.Factory(dict))
    client = attr.ib(default=None)

    @property
    def expansions(self):
        self.context.get('expansions')
