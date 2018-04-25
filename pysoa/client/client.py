from __future__ import unicode_literals

import collections
import random
import time
import uuid

import attr
import six

from pysoa.client.expander import ExpansionConverter
from pysoa.client.settings import PolymorphicClientSettings
from pysoa.common.metrics import TimerResolution
from pysoa.common.transport.exceptions import (
    ConnectionError,
    InvalidMessageError,
    MessageReceiveError,
    MessageReceiveTimeout,
    MessageSendError,
    MessageSendTimeout,
    MessageTooLarge,
)
from pysoa.common.types import (
    ActionRequest,
    JobRequest,
    JobResponse,
    UnicodeKeysDict,
)
from pysoa.utils import dict_to_hashable


class ServiceHandler(object):
    """Does the basic work of communicating with an individual service."""
    _transport_cache = {}

    def __init__(self, service_name, settings):
        self.metrics = settings['metrics']['object'](**settings['metrics'].get('kwargs', {}))

        transport_cache_time_in_seconds = 0
        if 'transport_cache_time_in_seconds' in settings:
            transport_cache_time_in_seconds = settings['transport_cache_time_in_seconds']
            if transport_cache_time_in_seconds < 0:
                raise ValueError('transport_cache_time_in_seconds must be >= 0')
        if transport_cache_time_in_seconds:
            self.transport = self._get_cached_transport(
                service_name,
                self.metrics,
                settings['transport'],
                transport_cache_time_in_seconds,
            )
            # If the transport is constructed anew, these will already be the same object and the below is a no-op.
            # If the transport is retrieved from the cache, we need to use the cached transport's metrics recorder to
            # ensure that we are publishing/committing all metrics in send_request and get_all_responses below.
            self.metrics = self.transport.metrics
        else:
            self.transport = self._construct_transport(service_name, self.metrics, settings['transport'])

        with self.metrics.timer('client.middleware.initialize', resolution=TimerResolution.MICROSECONDS):
            self.middleware = [
                m['object'](**m.get('kwargs', {}))
                for m in settings['middleware']
            ]

        # Make sure the request counter starts at a random location to avoid clashing with other clients
        # sharing the same connection
        self.request_counter = random.randint(1, 1000000)

    @staticmethod
    def _construct_transport(service_name, metrics, settings, metrics_key='client.transport.initialize'):
        with metrics.timer(metrics_key):
            return settings['object'](service_name, metrics, **settings.get('kwargs', {}))

    @classmethod
    def _get_cached_transport(cls, service_name, metrics, settings, cache_time_in_seconds):
        """
            Caches configured transports for up to cache_time_in_seconds to prevent the bottleneck.
            """
        cache_key = (service_name, dict_to_hashable(settings))
        if cache_key not in cls._transport_cache or cls._transport_cache[cache_key][0] < time.time():
            cls._transport_cache[cache_key] = (
                time.time() + cache_time_in_seconds,
                cls._construct_transport(service_name, metrics, settings, 'client.transport.initialize_cache'),
            )
        return cls._transport_cache[cache_key][1]

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

    def _base_send_request(self, request_id, meta, job_request, message_expiry_in_seconds=None):
        with self.metrics.timer('client.send.excluding_middleware', resolution=TimerResolution.MICROSECONDS):
            if isinstance(job_request, JobRequest):
                job_request = attr.asdict(job_request, dict_factory=UnicodeKeysDict)
            meta['__request_serialized__'] = False
            self.transport.send_request_message(request_id, meta, job_request, message_expiry_in_seconds)

    def send_request(self, job_request, message_expiry_in_seconds=None):
        """
        Send a JobRequest, and return a request ID.

        The context and control_extra arguments may be used to include extra values in the
        context and control headers, respectively.

        :param job_request: The job request object to send
        :type job_request: JobRequest
        :param message_expiry_in_seconds: How soon the message will expire if not received by a server (defaults to
                                          sixty seconds unless the settings are otherwise)
        :type message_expiry_in_seconds: int

        :return: The request ID
        :rtype: int

        :raise: ConnectionError, InvalidField, MessageSendError, MessageSendTimeout, MessageTooLarge
        """
        request_id = self.request_counter
        self.request_counter += 1
        meta = {}
        wrapper = self._make_middleware_stack(
            [m.request for m in self.middleware],
            self._base_send_request,
        )
        try:
            with self.metrics.timer('client.send.including_middleware', resolution=TimerResolution.MICROSECONDS):
                wrapper(request_id, meta, job_request, message_expiry_in_seconds)
            return request_id
        finally:
            self.metrics.commit()

    def _get_response(self, receive_timeout_in_seconds=None):
        with self.metrics.timer('client.receive.excluding_middleware', resolution=TimerResolution.MICROSECONDS):
            request_id, meta, message = self.transport.receive_response_message(receive_timeout_in_seconds)
            if message is None:
                return None, None
            else:
                return request_id, JobResponse(**message)

    def get_all_responses(self, receive_timeout_in_seconds=None):
        """
        Receive all available responses from the transport as a generator.

        :param receive_timeout_in_seconds: How long to block without receiving a message before raising
                                           `MessageReceiveTimeout` (defaults to five seconds unless the settings are
                                           otherwise).
        :type receive_timeout_in_seconds: int

        :return: A generator that yields (request ID, job response)
        :rtype: generator

        :raise: ConnectionError, MessageReceiveError, MessageReceiveTimeout, InvalidMessage, StopIteration
        """

        wrapper = self._make_middleware_stack(
            [m.response for m in self.middleware],
            self._get_response,
        )
        try:
            while True:
                with self.metrics.timer('client.receive.including_middleware', resolution=TimerResolution.MICROSECONDS):
                    request_id, response = wrapper(receive_timeout_in_seconds)
                if response is None:
                    break
                yield request_id, response
        finally:
            self.metrics.commit()


class Client(object):
    """The Client provides a simple interface for calling actions on Servers."""

    settings_class = PolymorphicClientSettings
    handler_class = ServiceHandler

    def __init__(self, config, expansion_config=None, settings_class=None, context=None):
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
        self.config = config or {}
        for service_name, service_config in self.config.items():
            self.settings[service_name] = self.settings_class(service_config)

        if expansion_config:
            self.expansion_converter = ExpansionConverter(
                type_routes=expansion_config['type_routes'],
                type_expansions=expansion_config['type_expansions'],
            )

    # Exceptions

    class ImproperlyConfigured(Exception):
        pass

    class InvalidExpansionKey(Exception):
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

        Returns the action response or raises an exception if the action response is an error (unless
        `raise_action_errors` is passed as `False`) or if the job response is an error (unless `raise_job_errors` is
        passed as `False`).

        :param service_name: The name of the service to call
        :type service_name: union[str, unicode]
        :param action: The name of the action to call
        :type action: union[str, unicode]
        :param body: The action request body
        :type body: dict
        :param expansions: A dictionary representing the expansions to perform
        :type expansions: dict
        :param raise_job_errors: Whether to raise a JobError if the job response contains errors (defaults to `True`)
        :type raise_job_errors: bool
        :param raise_action_errors: Whether to raise a CallActionError if any action responses contain errors (defaults
                                    to `True`)
        :type raise_action_errors: bool
        :param timeout: If provided, this will override the default transport timeout values to; requests will expire
                        after this number of seconds plus some buffer defined by the transport, and the client will not
                        block waiting for a response for longer than this amount of time.
        :type timeout: int
        :param switches: A list of switch value integers
        :type switches: list
        :param correlation_id: The request correlation ID
        :type correlation_id: union[str, unicode]
        :param continue_on_error: Whether to continue executing further actions once one action has returned errors
        :type continue_on_error: bool
        :param context: A dictionary of extra values to include in the context header
        :type context: dict
        :param control_extra: A dictionary of extra values to include in the control header
        :type control_extra: dict

        :return: The action response
        :rtype: ActionResponse

        :raise: ConnectionError, InvalidField, MessageSendError, MessageSendTimeout, MessageTooLarge,
                MessageReceiveError, MessageReceiveTimeout, InvalidMessage, JobError, CallActionError
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

    def call_actions(
        self,
        service_name,
        actions,
        expansions=None,
        raise_job_errors=True,
        raise_action_errors=True,
        timeout=None,
        **kwargs
    ):
        """
        Build and send a single job request with one or more actions.

        Returns a list of action responses, one for each action in the same order as provided, or raises an exception
        if any action response is an error (unless `raise_action_errors` is passed as `False`) or if the job response
        is an error (unless `raise_job_errors` is passed as `False`).

        This method performs expansions if the Client is configured with an expansion converter.

        :param service_name: The name of the service to call
        :type service_name: union[str, unicode]
        :param actions: A list of `ActionRequest` objects and/or dicts that can be converted to `ActionRequest` objects
        :type actions: iterable[union[ActionRequest, dict]]
        :param expansions: A dictionary representing the expansions to perform
        :type expansions: dict
        :param raise_job_errors: Whether to raise a JobError if the job response contains errors (defaults to `True`)
        :type raise_job_errors: bool
        :param raise_action_errors: Whether to raise a CallActionError if any action responses contain errors (defaults
                                    to `True`)
        :type raise_action_errors: bool
        :param timeout: If provided, this will override the default transport timeout values to; requests will expire
                        after this number of seconds plus some buffer defined by the transport, and the client will not
                        block waiting for a response for longer than this amount of time.
        :type timeout: int
        :param switches: A list of switch value integers
        :type switches: list
        :param correlation_id: The request correlation ID
        :type correlation_id: union[str, unicode]
        :param continue_on_error: Whether to continue executing further actions once one action has returned errors
        :type continue_on_error: bool
        :param context: A dictionary of extra values to include in the context header
        :type context: dict
        :param control_extra: A dictionary of extra values to include in the control header
        :type control_extra: dict

        :return: The job response
        :rtype: JobResponse

        :raise: ConnectionError, InvalidField, MessageSendError, MessageSendTimeout, MessageTooLarge,
                MessageReceiveError, MessageReceiveTimeout, InvalidMessage, JobError, CallActionError
        """
        if timeout:
            kwargs['message_expiry_in_seconds'] = timeout

        expected_request_id = self.send_request(service_name, actions, **kwargs)

        # Get all responses
        responses = list(self.get_all_responses(service_name, receive_timeout_in_seconds=timeout))

        # Try to find the expected response
        found = False
        response = None
        for request_id, response in responses:
            if request_id == expected_request_id:
                found = True
                break
        if not found:
            # This error should be impossible if `get_all_responses` is behaving correctly, but let's raise a
            # meaningful error just in case.
            raise Exception(
                'Got unexpected response(s) with ID(s) {} for request with ID {}'.format(
                    [r[0] for r in responses],
                    expected_request_id,
                )
            )

        # Process errors at the Job and Action level
        if response.errors and raise_job_errors:
            raise self.JobError(response.errors)
        if raise_action_errors:
            error_actions = [action for action in response.actions if action.errors]
            if error_actions:
                raise self.CallActionError(error_actions)

        if expansions:
            kwargs.pop('continue_on_error', None)
            self._perform_expansion(response.actions, expansions, **kwargs)

        return response

    def call_actions_parallel(self, service_name, actions, **kwargs):
        """
        Build and send multiple job requests to one service, each job with one action, to be executed in parallel, and
        return once all responses have been received.

        Returns a list of action responses, one for each action in the same order as provided, or raises an exception
        if any action response is an error (unless `raise_action_errors` is passed as `False`) or if any job response
        is an error (unless `raise_job_errors` is passed as `False`).

        This method performs expansions if the Client is configured with an expansion converter.

        :param service_name: The name of the service to call
        :type service_name: union[str, unicode]
        :param actions: A list of `ActionRequest` objects and/or dicts that can be converted to `ActionRequest` objects
        :type actions: iterable[union[ActionRequest, dict]]
        :param expansions: A dictionary representing the expansions to perform
        :type expansions: dict
        :param raise_job_errors: Whether to raise a JobError if any job responses contain errors (defaults to `True`)
        :type raise_job_errors: bool
        :param raise_action_errors: Whether to raise a CallActionError if any action responses contain errors (defaults
                                    to `True`)
        :type raise_action_errors: bool
        :param timeout: If provided, this will override the default transport timeout values to; requests will expire
                        after this number of seconds plus some buffer defined by the transport, and the client will not
                        block waiting for a response for longer than this amount of time.
        :type timeout: int
        :param switches: A list of switch value integers
        :type switches: list
        :param correlation_id: The request correlation ID
        :type correlation_id: union[str, unicode]
        :param continue_on_error: Whether to continue executing further actions once one action has returned errors
        :type continue_on_error: bool
        :param context: A dictionary of extra values to include in the context header
        :type context: dict
        :param control_extra: A dictionary of extra values to include in the control header
        :type control_extra: dict

        :return: A generator of action responses
        :rtype: generator[ActionResponse]

        :raise: ConnectionError, InvalidField, MessageSendError, MessageSendTimeout, MessageTooLarge,
                MessageReceiveError, MessageReceiveTimeout, InvalidMessage, JobError, CallActionError
        """
        if 'raise_job_errors' in kwargs:
            raise TypeError("call_actions_parallel() got a prohibited keyword argument 'raise_job_errors")
        if 'catch_transport_errors' in kwargs:
            raise TypeError("call_actions_parallel() got a prohibited keyword argument 'catch_transport_errors")

        job_responses = self.call_jobs_parallel(
            jobs=({'service_name': service_name, 'actions': [action]} for action in actions),
            **kwargs
        )

        return (job.actions[0] for job in job_responses)

    def call_jobs_parallel(
        self,
        jobs,
        expansions=None,
        raise_job_errors=True,
        raise_action_errors=True,
        catch_transport_errors=False,
        timeout=None,
        **kwargs
    ):
        """
        Build and send multiple job requests to one or more services, each with one or more actions, to be executed in
        parallel, and return once all responses have been received.

        Returns a list of job responses, one for each job in the same order as provided, or raises an exception if any
        job response is an error (unless `raise_job_errors` is passed as `False`) or if any action response is an
        error (unless `raise_action_errors` is passed as `False`).

        This method performs expansions if the Client is configured with an expansion converter.

        :param jobs: A list of job request dicts, each containing `service_name` and `actions`, where `actions` is a
                     list of `ActionRequest` objects and/or dicts that can be converted to `ActionRequest` objects
        :type jobs: iterable[dict(service_name=union[str, unicode], actions=list[union[ActionRequest, dict]])]
        :param expansions: A dictionary representing the expansions to perform
        :type expansions: dict
        :param raise_job_errors: Whether to raise a JobError if any job responses contain errors (defaults to `True`)
        :type raise_job_errors: bool
        :param raise_action_errors: Whether to raise a CallActionError if any action responses contain errors (defaults
                                    to `True`)
        :type raise_action_errors: bool
        :param catch_transport_errors: Whether to catch transport errors and return them instead of letting them
                                       propagate. By default (`False`), the errors `ConnectionError`,
                                       `InvalidMessageError`, `MessageReceiveError`, `MessageReceiveTimeout`,
                                       `MessageSendError`, `MessageSendTimeout`, and `MessageTooLarge`, when raised by
                                       the transport, cause the entire process to terminate, potentially losing
                                       responses. If this argument is set to `True`, those errors are, instead, caught,
                                       and they are returned in place of their corresponding responses in the returned
                                       list of job responses.
        :type catch_transport_errors: bool
        :param timeout: If provided, this will override the default transport timeout values to; requests will expire
                        after this number of seconds plus some buffer defined by the transport, and the client will not
                        block waiting for a response for longer than this amount of time.
        :type timeout: int
        :param switches: A list of switch value integers
        :type switches: list
        :param correlation_id: The request correlation ID
        :type correlation_id: union[str, unicode]
        :param continue_on_error: Whether to continue executing further actions once one action has returned errors
        :type continue_on_error: bool
        :param context: A dictionary of extra values to include in the context header
        :type context: dict
        :param control_extra: A dictionary of extra values to include in the control header
        :type control_extra: dict

        :return: The job response
        :rtype: list[union(JobResponse, Exception)]

        :raise: ConnectionError, InvalidField, MessageSendError, MessageSendTimeout, MessageTooLarge,
                MessageReceiveError, MessageReceiveTimeout, InvalidMessage, JobError, CallActionError
        """
        if timeout:
            kwargs['message_expiry_in_seconds'] = timeout

        error_key = 0
        transport_errors = {}

        response_reassembly_keys = []
        service_request_ids = {}
        for job in jobs:
            try:
                request_id = self.send_request(job['service_name'], job['actions'], **kwargs)
                service_request_ids.setdefault(job['service_name'], set()).add(request_id)
            except (ConnectionError, InvalidMessageError, MessageSendError, MessageSendTimeout, MessageTooLarge) as e:
                if not catch_transport_errors:
                    raise
                request_id = error_key = error_key - 1
                transport_errors[(job['service_name'], request_id)] = e

            response_reassembly_keys.append((job['service_name'], request_id))

        service_responses = {}
        for service_name, request_ids in six.iteritems(service_request_ids):
            try:
                for request_id, response in self.get_all_responses(service_name, receive_timeout_in_seconds=timeout):
                    if request_id not in request_ids:
                        raise Exception(
                            'Got response ID {}, not in set of expected IDs {}'.format(request_id, request_ids)
                        )
                    service_responses[(service_name, request_id)] = response
                    if catch_transport_errors:
                        # We don't need the set to be reduced unless we're catching errors
                        request_ids.remove(request_id)
            except (ConnectionError, InvalidMessageError, MessageReceiveError, MessageReceiveTimeout) as e:
                if not catch_transport_errors:
                    raise
                for request_id in request_ids:
                    transport_errors[(service_name, request_id)] = e

        responses = []
        actions_to_expand = []
        for service_name, request_id in response_reassembly_keys:
            if request_id < 0:
                # A transport error occurred during send, and we are catching errors, so add it to the responses
                responses.append(transport_errors[(service_name, request_id)])
                continue

            if (service_name, request_id) not in service_responses:
                if (service_name, request_id) in transport_errors:
                    # A transport error occurred during receive, and we are catching errors, so add it to the responses
                    responses.append(transport_errors[(service_name, request_id)])
                    continue

                # It shouldn't be possible for this to happen unless the code has a bug, but let's raise a meaningful
                # exception just in case a bug exists, because KeyError will not be helpful.
                raise Exception('There was no response for service {}, request {}'.format(service_name, request_id))

            response = service_responses[(service_name, request_id)]
            if raise_job_errors and response.errors:
                raise self.JobError(response.errors)
            if raise_action_errors:
                error_actions = [action for action in response.actions if action.errors]
                if error_actions:
                    raise self.CallActionError(error_actions)
            if expansions:
                actions_to_expand.extend(response.actions)

            responses.append(response)

        if expansions:
            kwargs.pop('continue_on_error', None)
            self._perform_expansion(actions_to_expand, expansions, **kwargs)

        return responses

    def _perform_expansion(self, actions, expansions, **kwargs):
        # Perform expansions
        if expansions and hasattr(self, 'expansion_converter'):
            try:
                objects_to_expand = self._extract_candidate_objects(actions, expansions)
            except KeyError as e:
                raise self.InvalidExpansionKey('Invalid key in expansion request: {}'.format(e.args[0]))
            else:
                self._expand_objects(objects_to_expand, **kwargs)

    def _extract_candidate_objects(self, actions, expansions):
        # Build initial list of objects to expand
        objects_to_expand = []
        for type_node in self.expansion_converter.dict_to_trees(expansions):
            for action in actions:
                expansion_objects = type_node.find_objects(action.body)
                objects_to_expand.extend(
                    (expansion_object, type_node.expansions)
                    for expansion_object in expansion_objects
                )
        return objects_to_expand

    def _expand_objects(self, objects_to_expand, **kwargs):
        # Keep track of expansion action errors that need to be raised
        expansion_errors_to_raise = []
        # Loop until we have no outstanding objects to expand
        while objects_to_expand:
            # Form a collection of optimized bulk requests that need to be made, a map of service name to a map of
            # action names to a dict instructing how to call the action and with what parameters
            pending_expansion_requests = collections.defaultdict(lambda: collections.defaultdict(dict))

            # Initialize mapping of service request IDs to expansion objects
            expansion_service_requests = collections.defaultdict(dict)

            # Formulate pending expansion requests to services
            for object_to_expand, expansion_nodes in objects_to_expand:
                for expansion_node in expansion_nodes:
                    # Only expand if expansion has not already been satisfied and object contains truth-y source field
                    if (
                        expansion_node.destination_field not in object_to_expand and
                        object_to_expand.get(expansion_node.source_field)
                    ):
                        # Get the expansion identifier value
                        value = object_to_expand[expansion_node.source_field]
                        # Call the action and map the request_id to the object we're expanding and the corresponding
                        # expansion node.
                        request_instruction = pending_expansion_requests[expansion_node.service][expansion_node.action]
                        request_instruction.setdefault('field', expansion_node.request_field)
                        request_instruction.setdefault('values', set()).add(value)
                        request_instruction.setdefault('object_nodes', []).append({
                            'object': object_to_expand,
                            'expansion': expansion_node,
                        })

            # Make expansion requests
            for service_name, actions in six.iteritems(pending_expansion_requests):
                for action_name, instructions in six.iteritems(actions):
                    request_id = self.send_request(
                        service_name,
                        actions=[
                            {'action': action_name, 'body': {instructions['field']: list(instructions['values'])}},
                        ],
                        **kwargs
                    )
                    expansion_service_requests[service_name][request_id] = instructions['object_nodes']

            # We have queued up requests for all expansions. Empty the queue, but we may add more to it.
            objects_to_expand = []

            # Receive expansion responses from services for which we have outstanding requests
            for service_name, request_ids_to_objects in expansion_service_requests.items():
                if request_ids_to_objects:
                    # Receive all available responses from the service
                    for request_id, response in self.get_all_responses(service_name):
                        # Pop the request mapping off the list of pending requests and get the value of the expansion
                        # from the response.
                        for object_node in request_ids_to_objects.pop(request_id):
                            object_to_expand = object_node['object']
                            expansion_node = object_node['expansion']

                            action_response = response.actions[0]
                            if action_response.errors and expansion_node.raise_action_errors:
                                expansion_errors_to_raise.append(action_response)

                            # If everything is okay, replace the expansion object with the response value
                            if action_response.body:
                                values = action_response.body[expansion_node.response_field]
                                response_key = object_to_expand[expansion_node.source_field]
                                if response_key in values:
                                    # It's okay if there isn't a matching value for this expansion; just means no match
                                    object_to_expand[expansion_node.destination_field] = values[response_key]

                                # Potentially add additional pending expansion requests.
                                if expansion_node.expansions:
                                    objects_to_expand.extend(
                                        (exp_object, expansion_node.expansions)
                                        for exp_object in expansion_node.find_objects(values)
                                    )

            if expansion_errors_to_raise:
                raise self.CallActionError(expansion_errors_to_raise)

    # Asynchronous request and response methods

    def _get_handler(self, service_name):
        if not isinstance(service_name, six.text_type):
            raise ValueError('Called service name "{}" must be unicode'.format(service_name))

        # Lazy-load a handler for the named service
        if service_name not in self.handlers:
            if service_name not in self.settings:
                raise self.ImproperlyConfigured('Unrecognized service name "{}"'.format(service_name))
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
        message_expiry_in_seconds=None,
    ):
        """
        Build and send a JobRequest, and return a request ID.

        The context and control_extra arguments may be used to include extra values in the
        context and control headers, respectively.

        :param service_name: The name of the service from which to receive responses
        :type service_name: union[str, unicode]
        :param actions: A list of `ActionRequest` objects
        :type actions: list
        :param switches: A list of switch value integers
        :type switches: union[list, set]
        :param correlation_id: The request correlation ID
        :type correlation_id: union[str, unicode]
        :param continue_on_error: Whether to continue executing further actions once one action has returned errors
        :type continue_on_error: bool
        :param context: A dictionary of extra values to include in the context header
        :type context: dict
        :param control_extra: A dictionary of extra values to include in the control header
        :type control_extra: dict
        :param message_expiry_in_seconds: How soon the message will expire if not received by a server (defaults to
                                          sixty seconds unless the settings are otherwise)
        :type message_expiry_in_seconds: int

        :return: The request ID
        :rtype: int

        :raise: ConnectionError, InvalidField, MessageSendError, MessageSendTimeout, MessageTooLarge
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
        return handler.send_request(job_request, message_expiry_in_seconds)

    def get_all_responses(self, service_name, receive_timeout_in_seconds=None):
        """
        Receive all available responses from the service as a generator.

        :param service_name: The name of the service from which to receive responses
        :type service_name: union[str, unicode]
        :param receive_timeout_in_seconds: How long to block without receiving a message before raising
                                           `MessageReceiveTimeout` (defaults to five seconds unless the settings are
                                           otherwise).
        :type receive_timeout_in_seconds: int

        :return: A generator that yields (request ID, job response)
        :rtype: generator

        :raise: ConnectionError, MessageReceiveError, MessageReceiveTimeout, InvalidMessage, StopIteration
        """

        handler = self._get_handler(service_name)
        return handler.get_all_responses(receive_timeout_in_seconds)
