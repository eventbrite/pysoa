import math

from pysoa.server.server import (
    HarakiriInterrupt,
    Server as BaseServer,
)


def harakiri_loop_graceful(*_, **__):
    def action(*___):
        i = 0
        while True:
            i += math.factorial(10)

    return action


def harakiri_loop_forceful(*_, **__):
    def action(*___):
        i = 0
        while True:
            try:
                while True:
                    i += math.factorial(10)
            except HarakiriInterrupt:
                pass  # muuuuaaaaaaahahaha I won't let go!

    return action


class Server(BaseServer):
    service_name = 'echo'
    action_class_map = {
        'harakiri_loop_graceful': harakiri_loop_graceful,
        'harakiri_loop_forceful': harakiri_loop_forceful,
    }
