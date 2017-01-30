class Server(object):
    """
    Base class from which all SOA Service Servers inherit
    """
    service_name = None
    action_class_map = {}

    def __init__(self):
        if not self.service_name:
            raise AttributeError('Server subclass must set service_name')

    def process_request(self):
        pass

    def run(self):
        while not self.shutting_down:
            self.process_request()
