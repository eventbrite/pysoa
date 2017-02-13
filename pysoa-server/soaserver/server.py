from soaserver.schemas import JobRequestSchema


class Server(object):
    """
    Base class from which all SOA Service Servers inherit.

    Required Attributes for Subclasses:
        service_name: a string name of the service.
        action_class_map: a dictionary mapping action name strings
            to Action subclasses.
    """
    service_name = None
    action_class_map = {}

    def __init__(self):
        if not self.service_name:
            raise AttributeError('Server subclass must set service_name')

    def process_request(self):
        job_request = self.transport.receive()

        # Validate JobRequest message
        JobRequestSchema.errors(job_request)

    def run(self):
        while not self.shutting_down:
            self.process_request()
