from __future__ import unicode_literals

from .settings import (
    ClientSettings,
    ASGIClientSettings,
)


class ClientRouter(object):
    """
    Manages creating clients per service.

    Pass in a dictionary mapping service names to settings dicts for those services.

    You may also pass in a `context` dictionary to pre-populate clients with it.
    """

    settings_class = ClientSettings

    class ImproperlyConfigured(Exception):
        pass

    def __init__(self, config, settings_class=None, context=None):
        if settings_class:
            self.settings_class = settings_class
        self.cached_clients = {}
        self.settings = {}
        self.context = context
        # We load the settings now, but do not make clients until requested
        for service_name, service_settings in config.items():
            self.settings[service_name] = self.settings_class(service_settings)

    def get_client(self, service_name, **kwargs):
        if service_name not in self.settings:
            raise self.ImproperlyConfigured('Unrecognized service name {}'.format(service_name))
        if not self.settings[service_name]['cacheable']:
            return self._make_client(service_name, **kwargs)
        if service_name not in self.cached_clients:
            self.cached_clients[service_name] = self._make_client(service_name, **kwargs)
        return self.cached_clients[service_name]

    def _make_client(self, service_name, **kwargs):
        """Make a new client instance."""
        settings = self.settings[service_name]
        client_class = settings['client']['object']
        client_kwargs = settings['client'].get('kwargs', {})
        client_kwargs.update(kwargs)
        transport_class = settings['transport']['object']
        serializer_class = settings['serializer']['object']
        return client_class(
            service_name,
            # Instantiate the transport and serializer classes with the kwargs
            # they had defined in the settings.
            transport=transport_class(service_name, **settings['transport'].get('kwargs', {})),
            serializer=serializer_class(**settings['serializer'].get('kwargs', {})),
            middleware=[middleware_class(**middleware_kwargs)
                        for middleware_class, middleware_kwargs in settings['middleware']],
            context=self.context,
            **client_kwargs
        )


class ASGIClientRouter(ClientRouter):
    """Router class that returns ASGI clients."""

    settings_class = ASGIClientSettings
