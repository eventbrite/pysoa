class Action(object):
    """
    Base class from which all SOA Service Actions inherit.
    """
    def __init__(self, settings=None):
        self.settings = settings

    def run(self, action_request):
        raise NotImplemented()

    def __call__(self, action_request):
        return self.run(action_request)
