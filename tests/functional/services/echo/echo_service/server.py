from pysoa.server.server import Server as BaseServer


class Server(BaseServer):
    service_name = 'echo'
    action_class_map = {}
