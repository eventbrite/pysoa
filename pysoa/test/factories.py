import factory
import importlib

from pysoa.server import Server
from pysoa.server.settings import ServerSettings


class ServerSettingsFactory(factory.Factory):
    class Meta:
        model = ServerSettings

    data = factory.Dict({
        'transport': {
            'path': u'pysoa.common.transport.base:ServerTransport',
        },
        'serializer': {
            'path': u'pysoa.common.serializer.base:Serializer',
        },
    })

    @classmethod
    def _adjust_kwargs(cls, **kwargs):
        # Factory Boy special method used to alter custom settings dictionaries.
        # Make a copy of settings and override transport to use base transport.
        kwargs['data'] = dict(
            kwargs['data'],
            transport={
                'path': u'pysoa.common.transport.base:ServerTransport',
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
