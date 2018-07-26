from __future__ import (
    absolute_import,
    unicode_literals,
)

import importlib

import factory

from pysoa.server import Server
from pysoa.server.action import Action
from pysoa.server.settings import ServerSettings


class ServerSettingsFactory(factory.Factory):
    class Meta:
        model = ServerSettings

    data = factory.Dict({
        'transport': {
            'path': 'pysoa.common.transport.local:LocalServerTransport',
        },
    })

    @classmethod
    def _adjust_kwargs(cls, **kwargs):
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
    def from_module(cls, module_path):
        settings_module = importlib.import_module(module_path)
        settings = getattr(settings_module, 'settings')
        return cls(settings)


class ServerFactory(factory.Factory):
    class Meta:
        model = Server

    settings = factory.SubFactory(ServerSettingsFactory)


def ActionFactory(body=None, exception=None):
    """
    Makes an action with the result or exception you specify.
    """
    class TestAction(Action):
        def run(self, request):
            if exception:
                raise exception
            return body or {}
    return TestAction
