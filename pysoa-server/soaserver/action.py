class Action(object):
    """
    Base class from which all SOA Service Actions inherit.
    """
    def run(self, action_request):
        raise NotImplemented()
