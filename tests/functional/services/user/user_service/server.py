from pysoa.server.server import Server as BaseServer


class Server(BaseServer):
    service_name = 'user'
    use_django = True
    action_class_map = {}
