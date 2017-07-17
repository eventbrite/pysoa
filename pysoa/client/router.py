from __future__ import unicode_literals

import six

from pysoa.client.expander import ExpansionConverter
from pysoa.client.settings import (
    ClientSettings,
    ASGIClientSettings,
)
from pysoa.common.types import (
    ActionRequest,
    JobRequest,
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

        if 'expansions' in config:
            self.expansion_converter = ExpansionConverter(
                type_routes=config['expansions']['type_routes'],
                type_expansions=config['expansions']['type_expansions'],
            )

        # We load the settings now, but do not make clients until requested
        if 'clients' in config:
            for service_name, service_settings in config['clients'].items():
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
            middleware=[
                m['object'](**m.get('kwargs', {}))
                for m in settings['middleware']
            ],
            context=self.context,
            **client_kwargs
        )

    def call_action(
        self,
        service_name,
        action_name,
        body=None,
        switches=None,
        expansions=None,
        continue_on_error=False,
        **kwargs
    ):
        """
        Call a PySOA action.

        This method is distinct from the method of the same name on the Client
        in that it supports calling multiple services and expansions.

        Args:
            service_name (str): name of the service to call.
            action_name (str): name of the action to call.
            body (dict): body of the ActionRequest.
            switches (list): a list of switches to enable for the job.
            expansions (dict): an expansion dictionary (see below).
            continue_on_error (bool): a boolean indicating whether or not to
                continue executing the job in the event of an error.

        Returns:
            A JobResponse containing the result of the called action.

        Expansion Dictionary Format:
        {
            "<type>": ["<expansion string>", ...],
            ...
        }

        <type> is the type of object to expand.
        <expansion string> is a string with the following format:
            <expansion string> => <expansion name>.<expansion string> |
                <expansion name>

        """
        # Call the action
        client = self.get_client(service_name)
        context = client.make_context_header(
            switches=switches,
        )
        action_request = {
            'action': action_name,
        }
        if body:
            action_request['body'] = body
        job_response = client.call_actions(
            [action_request],
            continue_on_error=continue_on_error,
            context=context,
            **kwargs
        )

        # If an expansion dictionary was provided, expand the response.
        if expansions and hasattr(self, 'expansion_converter'):
            # Initialize service client cache
            exp_services = {
                service_name: {
                    'client': client,
                    'requests': {},
                },
            }

            # Build initial list of objects to expand
            objs_to_expand = []
            for type_node in self.expansion_converter.dict_to_trees(expansions):
                exp_objects = type_node.find_objects(job_response.actions[0].body)
                objs_to_expand.extend(
                    (exp_object, type_node.expansions)
                    for exp_object in exp_objects
                )

            # Loop until we have no outstanding requests or responses
            while objs_to_expand or any(
                exp_service['requests']
                for exp_service in six.itervalues(exp_services)
            ):
                # Send pending expansion requests to services
                for obj_to_expand, expansion_nodes in objs_to_expand:
                    for expansion_node in expansion_nodes:
                        # Only expand if expansion has not already been satisfied
                        if expansion_node.dest_field not in obj_to_expand:
                            # Get the cached client and expansion identifier
                            # value
                            exp_service = exp_services.setdefault(
                                expansion_node.service,
                                {
                                    'client': self.get_client(expansion_node.service),
                                    'requests': {},
                                },
                            )
                            exp_client = exp_service['client']
                            value = obj_to_expand[expansion_node.source_field]

                            # Build the expansion JobRequest
                            exp_request = JobRequest(
                                control={
                                    'continue_on_error': False,
                                },
                                context=context,
                                actions=[ActionRequest(
                                    action=expansion_node.action,
                                    body={
                                        expansion_node.request_field: value,
                                    }
                                )]
                            )

                            # Call the action and map the request_id to the
                            # object we're expanding and the corresponding
                            # expansion node.
                            request_id = exp_client.send_request(exp_request)
                            exp_service['requests'][request_id] = {
                                'object': obj_to_expand,
                                'expansion': expansion_node,
                            }

                # We have expanded all pending objects. Empty the queue.
                objs_to_expand = []

                # Receive expansion responses from services for which we have
                # outstanding requests
                for exp_service in six.moves.filter(lambda x: x['requests'], six.itervalues(exp_services)):
                    exp_client = exp_service['client']
                    exp_requests = exp_service['requests']

                    # Receive all available responses from the service
                    for exp_request_id, exp_response in exp_client.get_all_responses():
                        # Pop the request mapping off the list of pending
                        # requests and get the value of the expansion from the
                        # response.
                        exp_request = exp_requests.pop(exp_request_id)
                        exp_object = exp_request['object']
                        expansion_node = exp_request['expansion']
                        value = exp_response.actions[0].body[expansion_node.response_field]

                        # Add the expansion value to the object and remove the
                        # source field.
                        del exp_object[expansion_node.source_field]
                        exp_object[expansion_node.dest_field] = value

                        # Potentially add additional pending expansion requests.
                        if expansion_node.expansions:
                            objs_to_expand.extend(
                                (exp_object, expansion_node.expansions)
                                for exp_object in expansion_node.find_objects(value)
                            )

        return job_response


class ASGIClientRouter(ClientRouter):
    """Router class that returns ASGI clients."""

    settings_class = ASGIClientSettings
