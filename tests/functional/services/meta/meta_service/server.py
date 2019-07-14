from pysoa.server.server import Server as BaseServer


class Server(BaseServer):
    service_name = 'meta'
    action_class_map = {}
