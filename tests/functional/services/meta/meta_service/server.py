from pysoa.server.server import Server as BaseServer
from pysoa.server.action.base import Action


class VeryLargeResponseAction(Action):
    def run(self, request):
        return {'key-{}'.format(i): 'value-{}'.format(i) for i in range(10000, 47000)}


class Server(BaseServer):
    service_name = 'meta'
    action_class_map = {
        'very_large_response': VeryLargeResponseAction,
    }
