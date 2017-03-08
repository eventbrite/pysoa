from .settings import ClientSettings
from .client import Client


class ClientRouter(object):
    """
    Manages creating clients per service.

    Pass in a dictionary mapping service names to settings dicts for those services.
    """

    client_class = Client

    def __init__(self, config):
        self.cached_clients = {}
        self.settings = {}
        # We load the settings now, but do not make clients until requested
        for service_name, service_settings in config.items():
            self.settings[service_name] = ClientSettings(service_settings)

    def get_client(self, service_name):
        if not self.settings[service_name]['cacheable']:
            return self._make_client(service_name)
        if service_name not in self.cached_clients:
            self.cached_clients[service_name] = self._make_client(service_name)
        return self.cached_clients[service_name]

    def _make_client(self, service_name):
        """Make a new client instance."""
        settings = self.settings[service_name]
        transport_class = settings['transport']['object']
        serializer_class = settings['serializer']['object']
        return self.client_class(
            service_name,
            # Instantiate the transport and serializer classes with the kwargs
            # they had defined in the settings.
            transport_class(service_name, **settings['transport'].get('kwargs', {})),
            serializer_class(**settings['serializer'].get('kwargs', {})),
            middleware=[middleware_class(**middleware_kwargs)
                        for middleware_class, middleware_kwargs in settings['middleware']]
        )
