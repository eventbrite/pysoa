from __future__ import (
    absolute_import,
    unicode_literals,
)

import importlib
from typing import (
    Any,
    Dict,
    Optional,
    Type,
)

import factory
import six

from pysoa.server.action import Action
from pysoa.server.server import Server
from pysoa.server.settings import ServerSettings
from pysoa.server.types import EnrichedActionRequest


class ServerSettingsFactory(factory.Factory):
    class Meta:
        model = ServerSettings

    data = factory.Dict({
        'transport': {
            'path': 'pysoa.common.transport.local:LocalServerTransport',
        },
    })

    @classmethod
    def _adjust_kwargs(cls, **kwargs):  # type: (**Any) -> Dict[six.text_type, Any]
        # Factory Boy special method used to alter custom settings dictionaries.
        # Make a copy of settings and override transport to use base transport.
        kwargs['data'] = dict(
            kwargs['data'],
            transport={
                'path': 'pysoa.common.transport.local:LocalServerTransport',
            },
        )
        return kwargs

    @classmethod
    def from_module(cls, module_path):  # type: (six.text_type) -> ServerSettingsFactory
        settings_module = importlib.import_module(module_path)
        settings = getattr(settings_module, 'settings')
        return cls(settings)


class ServerFactory(factory.Factory):
    class Meta:
        model = Server

    settings = factory.SubFactory(ServerSettingsFactory)


# noinspection PyPep8Naming
def ActionFactory(body=None, exception=None):
    # type: (Optional[Dict[six.text_type, Any]], Optional[Exception]) -> Type[Action]
    """
    Makes an action class with the result or exception you specify.
    """
    class TestAction(Action):
        def run(self, request):  # type: (EnrichedActionRequest) -> Dict[six.text_type, Any]
            if exception:
                raise exception
            return body or {}
    return TestAction
