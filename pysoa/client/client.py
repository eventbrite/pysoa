from __future__ import unicode_literals

import time
import uuid

import attr
import six

from pysoa.client.expander import ExpansionConverter
from pysoa.client.settings import PolymorphicClientSettings
from pysoa.common.types import (
    ActionRequest,
    JobRequest,
    JobResponse,
    UnicodeKeysDict,
)


_TRANSPORT_CACHE_DEFAULT_TIMEOUT = 10.000  # seconds

_transport_cache = {}


def _get_cached_transport(service_name, settings, metrics):
    """
    Caches configured transports for up to 10 seconds to prevent the bottleneck.

    NOT YET USED. WILL BE USED AFTER INITIAL METRICS ARE COLLECTED.
    """
    cache_key = hash(repr((service_name, settings)))
    if cache_key not in _transport_cache or _transport_cache[cache_key][0] < time.time():
        _transport_cache[cache_key] = (
            time.time() + _TRANSPORT_CACHE_DEFAULT_TIMEOUT,
            settings['object'](service_name, metrics, **settings.get('kwargs', {})),
        )
    return _transport_cache[cache_key][1]


class ServiceHandler(object):
    """Does the basic work of communicating with an individual service."""

    def __init__(self, service_name, settings):
        self.metrics = settings['metrics']['object'](**settings['metrics'].get('kwargs', {}))

        with self.metrics.timer('client.transport.initialize'):
            self.transport = settings['transport']['object'](
                service_name,
                self.metrics,
                **settings['transport'].get('kwargs', {})
            )

        self.serializer = settings['serializer']['object'](**settings['serializer'].get('kwargs', {}))

        with self.metrics.timer('client.middleware.initialize'):
            self.middleware = [
                m['object'](**m.get('kwargs', {}))
                for m in settings['middleware']
            ]

        self.request_counter = 0

    def _prepare_metadata(self):
        """
        Return a dict containing metadata that will be passed to
        Transport.send_request_message. Implementations should override this method to
        include any metadata required by their Transport classes.
        """
        return {'mime_type': self.serializer.mime_type}

    @staticmethod
    def _make_middleware_stack(middleware, base):
        """
        Given a list of in-order middleware callables `middleware`
        and a base function `base`, chains them together so each middleware is
        fed the function below, and returns the top level ready to call.
        """
        for ware in reversed(middleware):
            base = ware(base)
        return base

    def _base_send_request(self, request_id, meta, job_request):
        with self.metrics.timer('client.send.excluding_middleware'):
            if isinstance(job_request, JobRequest):
                job_request = attr.asdict(job_request, dict_factory=UnicodeKeysDict)
            message = self.serializer.dict_to_blob(job_request)
            self.transport.send_request_message(request_id, meta, message)

    def send_request(self, job_request):
        """
        Serialize and send a JobRequest, and return a request ID.

        The context and control_extra arguments may be used to include extra values in the
        context and control headers, respectively.

        Args:
            job_request: JobRequest object
        Returns:
            int
        Raises:
            ConnectionError, InvalidField, MessageSendError, MessageSendTimeout,
            MessageTooLarge
        """
        request_id = self.request_counter
        self.request_counter += 1
        meta = self._prepare_metadata()
        wrapper = self._make_middleware_stack(
            [m.request for m in self.middleware],
            self._base_send_request,
        )
        try:
            with self.metrics.timer('client.send.including_middleware'):
                wrapper(request_id, meta, job_request)
            return request_id
        finally:
            self.metrics.commit()

    def _get_response(self):
        with self.metrics.timer('client.receive.excluding_middleware'):
            request_id, meta, message = self.transport.receive_response_message()
            if message is None:
                return None, None
            else:
                raw_response = self.serializer.blob_to_dict(message)
                job_response = JobResponse(**raw_response)
                return request_id, job_response

    def get_all_responses(self):
        """
        Receive all available responses from the transport as a generator.

        Yields:
            (int, JobResponse)
        Raises:
            ConnectionError, MessageReceiveError, MessageReceiveTimeout, InvalidMessage,
            StopIteration
        """
        wrapper = self._make_middleware_stack(
            [m.response for m in self.middleware],
            self._get_response,
        )
        try:
            while True:
                with self.metrics.timer('client.receive.including_middleware'):
                    request_id, response = wrapper()
                if response is None:
                    break
                yield request_id, response
        finally:
            self.metrics.commit()


class Client(object):
    """The Client provides a simple interface for calling actions on Servers."""

    settings_class = PolymorphicClientSettings
    handler_class = ServiceHandler

    def __init__(self, config, expansions=None, settings_class=None, context=None):
        """
        Args:
            config: dict of {service_name: service_settings}
            expansions: dict of {service_name: service_expansions}
            settings_class: Settings subclass
            context: dict
        """
        if settings_class:
            self.settings_class = settings_class
        self.context = context or {}

        self.handlers = {}
        self.settings = {}
        config = config or {}
        for service_name, service_config in config.items():
            self.settings[service_name] = self.settings_class(service_config)

        if expansions:
            self.expansion_converter = ExpansionConverter(
                type_routes=expansions['type_routes'],
                type_expansions=expansions['type_expansions'],
            )

    # Exceptions

    class ImproperlyConfigured(Exception):
        pass

    class JobError(Exception):
        """
        Raised by Client.call_action(s) when a job response contains one or more job errors.

        Args:
            job: JobResponse
        """
        def __init__(self, errors=None):
            self.errors = errors or []

        def __repr__(self):
            return self.__str__()

        def __str__(self):
            errors_string = '\n'.join([str(e) for e in self.errors])
            return 'Error executing job:\n{}'.format(errors_string)

    class CallActionError(Exception):
        """
        Raised by Client.call_action(s) when a job response contains one or more action errors.

        Stores a list of ActionResponse objects, and pretty-prints their errors.

        Args:
            actions: list(ActionResponse)
        """
        def __init__(self, actions=None):
            self.actions = actions or []

        def __str__(self):
            errors_string = '\n'.join(['{a.action}: {a.errors}'.format(a=a) for a in self.actions])
            return 'Error calling action(s):\n{}'.format(errors_string)

    # Synchronous request methods

    def call_action(
        self,
        service_name,
        action,
        body=None,
        **kwargs
    ):
        """
        Build and send a single job request with one action.

        Returns the action response or raises an exception if the action response is an error.

        Args:
            service_name: string
            action: string
            body: dict
            switches: list of ints
            context: dict
            correlation_id: string
        Returns:
            ActionResponse
        """
        action_request = ActionRequest(
            action=action,
            body=body or {},
        )
        return self.call_actions(
            service_name,
            [action_request],
            **kwargs
        ).actions[0]

    def call_actions(self, service_name, actions, expansions=None, raise_action_errors=True, **kwargs):
        """
        Build and send a single job request with one or more actions.

        Returns a list of action responses, one for each action, or raises an exception if any action response is an
        error.

        This method performs expansions if the Client is configured with an expansion converter.

        Args:
            service_name: string
            actions: list of ActionRequest or dict
            switches: list
            context: dict
            correlation_id: string
            continue_on_error: bool
            control_extra: dict
            raise_action_errors (bool): Fail if the response contains action error responses.
        Returns:
            JobResponse
        """
        request_id = self.send_request(service_name, actions, **kwargs)
        # Dump everything from the generator. There should only be one response.
        responses = list(self.get_all_responses(service_name))
        response_id, response = responses[0]
        if response_id != request_id:
            raise Exception('Got response with ID {} for request with ID {}'.format(response_id, request_id))
        # Process errors at the Job and Action level
        if response.errors:
            raise self.JobError(response.errors)
        if raise_action_errors:
            error_actions = [action for action in response.actions if action.errors]
            if error_actions:
                raise self.CallActionError(error_actions)

        # Keep track of expansion action errors that need to be raised
        expansion_errors = []
        # Perform expansions
        if expansions and hasattr(self, 'expansion_converter'):
            # Initialize service request cache
            exp_service_requests = {service_name: {}}

            # Build initial list of objects to expand
            objs_to_expand = []
            for type_node in self.expansion_converter.dict_to_trees(expansions):
                for action in response.actions:
                    exp_objects = type_node.find_objects(action.body)
                    objs_to_expand.extend(
                        (exp_object, type_node.expansions)
                        for exp_object in exp_objects
                    )

            # Loop until we have no outstanding requests or responses
            while objs_to_expand or any(exp_service_requests.values()):
                # Send pending expansion requests to services
                for obj_to_expand, expansion_nodes in objs_to_expand:
                    for expansion_node in expansion_nodes:
                        # Only expand if expansion has not already been satisfied
                        if expansion_node.dest_field not in obj_to_expand:
                            # Get the cached expansion identifier value
                            value = obj_to_expand[expansion_node.source_field]
                            # Call the action and map the request_id to the
                            # object we're expanding and the corresponding
                            # expansion node.
                            request_id = self.send_request(
                                expansion_node.service,
                                actions=[ActionRequest(
                                    action=expansion_node.action,
                                    body={expansion_node.request_field: value}
                                )],
                                continue_on_error=False,
                            )
                            exp_service_requests.setdefault(expansion_node.service, {})[request_id] = {
                                'object': obj_to_expand,
                                'expansion': expansion_node,
                            }

                # We have expanded all pending objects. Empty the queue.
                objs_to_expand = []

                # Receive expansion responses from services for which we have
                # outstanding requests
                for exp_service, exp_requests in exp_service_requests.items():
                    if exp_requests:
                        # Receive all available responses from the service
                        for exp_request_id, exp_response in self.get_all_responses(exp_service):
                            # Pop the request mapping off the list of pending
                            # requests and get the value of the expansion from the
                            # response.
                            exp_request = exp_requests.pop(exp_request_id)
                            exp_object = exp_request['object']
                            expansion_node = exp_request['expansion']
                            exp_action_response = exp_response.actions[0]
                            if exp_action_response.errors and expansion_node.raise_action_errors:
                                expansion_errors.append(exp_action_response)
                            # If everything is okay, replace the expansion object with the response value
                            if exp_action_response.body:
                                value = exp_action_response.body[expansion_node.response_field]
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
            if expansion_errors:
                raise self.CallActionError(expansion_errors)

        return response

    # Asynchronous request and response methods

    def _get_handler(self, service_name):
        # Lazy-load a handler for the named service
        if service_name not in self.handlers:
            if service_name not in self.settings:
                raise self.ImproperlyConfigured('Unrecognized service name {}'.format(service_name))
            settings = self.settings[service_name]
            self.handlers[service_name] = self.handler_class(service_name, settings)
        return self.handlers[service_name]

    @staticmethod
    def _make_control_header(continue_on_error=False, control_extra=None):
        control = {
            'continue_on_error': continue_on_error,
        }
        if control_extra:
            control.update(control_extra)
        return control

    def _make_context_header(
        self,
        switches=None,
        correlation_id=None,
        context_extra=None,
    ):
        # Copy the underlying context object, if it was provided
        context = dict(self.context.items()) if self.context else {}
        # Either add on, reuse or generate a correlation ID
        if correlation_id is not None:
            context['correlation_id'] = correlation_id
        elif 'correlation_id' not in context:
            context['correlation_id'] = six.u(uuid.uuid1().hex)
        # Switches can come from three different places, so merge them
        # and ensure that they are unique
        switches = set(switches or [])
        if context_extra:
            switches |= set(context_extra.pop('switches', []))
        context['switches'] = list(set(context.get('switches', [])) | switches)
        # Add any extra stuff
        if context_extra:
            context.update(context_extra)
        return context

    def send_request(
        self,
        service_name,
        actions,
        switches=None,
        correlation_id=None,
        continue_on_error=False,
        context=None,
        control_extra=None,
    ):
        """
        Build and send a JobRequest, and return a request ID.

        The context and control_extra arguments may be used to include extra values in the
        context and control headers, respectively.

        Args:
            service_name: string
            actions: list of ActionRequest
            switches: list of int
            correlation_id: string
            continue_on_error: bool
            context: dict of extra values to include in the context header
            control_extra: dict of extra values to include in the control header
        Returns:
            int
        Raises:
            ConnectionError, InvalidField, MessageSendError, MessageSendTimeout,
            MessageTooLarge
        """
        handler = self._get_handler(service_name)
        control = self._make_control_header(
            continue_on_error=continue_on_error,
            control_extra=control_extra,
        )
        context = self._make_context_header(
            switches=switches,
            correlation_id=correlation_id,
            context_extra=context,
        )
        job_request = JobRequest(actions=actions, control=control, context=context or {})
        return handler.send_request(job_request)

    def get_all_responses(self, service_name):
        """
        Receive all available responses from the service as a generator.

        Yields:
            (int, JobResponse)
        Raises:
            ConnectionError, MessageReceiveError, MessageReceiveTimeout, InvalidMessage,
            StopIteration
        """
        handler = self._get_handler(service_name)
        return handler.get_all_responses()
