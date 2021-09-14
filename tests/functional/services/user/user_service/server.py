from pysoa.server.server import Server as BaseServer


from typing import (
    Mapping
)

import six

from pysoa.server.types import (
    ActionType
)


class Server(BaseServer):
    service_name = 'user'
    use_django = True
    action_class_map = {}  # type: Mapping[six.text_type, ActionType]
