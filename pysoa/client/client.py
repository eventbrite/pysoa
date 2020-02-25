from __future__ import (
    absolute_import,
    unicode_literals,
)

import collections
import logging
import random
import sys
from types import TracebackType
from typing import (
    AbstractSet,
    Any,
    Callable,
    Dict,
    Generator,
    Generic,
    Iterable,
    List,
    Mapping,
    NamedTuple,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
)
import uuid

import attr
from conformity.settings import SettingsData
from pymetrics.instruments import TimerResolution
from pymetrics.recorders.base import MetricsRecorder
import six

from pysoa.client.errors import (
    CallActionError,
    CallJobError,
    ImproperlyConfigured,
    InvalidExpansionKey,
)
from pysoa.client.expander import (
    ExpansionConverter,
    ExpansionNode,
    Expansions,
    ExpansionSettings,
    TypeExpansions,
    TypeNode,
    TypeRoutes,
)
from pysoa.client.middleware import (
    ClientMiddleware,
    ClientRequestMiddlewareTask,
    ClientResponseMiddlewareTask,
)
from pysoa.client.settings import ClientSettings
from pysoa.common.errors import Error
from pysoa.common.transport.base import ClientTransport
from pysoa.common.transport.errors import (
    MessageReceiveTimeout,
    PySOATransportError,
)
from pysoa.common.types import (
    ActionRequest,
    ActionResponse,
    Body,
    Context,
    Control,
    JobRequest,
    JobResponse,
    UnicodeKeysDict,
)
from pysoa.version import __version_info__


__all__ = (
    'Client',
    'ServiceHandler',
)


_MT = TypeVar('_MT', ClientRequestMiddlewareTask, ClientResponseMiddlewareTask)

_logger = logging.getLogger(__name__)


class ServiceHandler(object):
    """Does the low-level work of communicating with an individual service through its configured transport."""

    _client_version = list(__version_info__)

    def __init__(self, service_name, settings):  # type: (six.text_type, ClientSettings) -> None
        """
        :param service_name: The name of the service which this handler calls
        :param settings: The client settings object for this service (and only this service)
        """
        self.service_name = service_name
        self.metrics = settings['metrics']['object'](**settings['metrics'].get('kwargs', {}))  # type: MetricsRecorder

        with self.metrics.timer('client.transport.initialize', resolution=TimerResolution.MICROSECONDS):
            self.transport = settings['transport']['object'](
                service_name,
                self.metrics,
                **settings['transport'].get('kwargs', {})
            )  # type: ClientTransport

        with self.metrics.timer('client.middleware.initialize', resolution=TimerResolution.MICROSECONDS):
            self._middleware = [
                m['object'](**m.get('kwargs', {}))
                for m in settings['middleware']
            ]  # type: List[ClientMiddleware]
            self._middleware_send_request_wrapper = self._make_middleware_stack(
                [m.request for m in self._middleware],
                self._base_send_request,
            )
            self._middleware_get_response_wrapper = self._make_middleware_stack(
                [m.response for m in self._middleware],
                self._base_get_response,
            )

        # Make sure the request counter starts at a random location to avoid clashing with other clients
        # sharing the same connection
        self.request_counter = random.randint(1, 1000000)  # type: int

    @staticmethod
    def _make_middleware_stack(middleware, base):  # type: (List[Callable[[_MT], _MT]], _MT) -> _MT
        """
        Given a list of in-order middleware callables `middleware`
        and a base function `base`, chains them together so each middleware is
        fed the function below, and returns the top level ready to call.
        """
        for ware in reversed(middleware):
            base = ware(base)
        return base

    def _base_send_request(self, request_id, meta, job_request, message_expiry_in_seconds=None):
        # type: (int, Dict[six.text_type, Any], JobRequest, Optional[int]) -> None
        with self.metrics.timer('client.send.excluding_middleware', resolution=TimerResolution.MICROSECONDS):
            self.transport.send_request_message(
                request_id,
                meta,
                attr.asdict(job_request, dict_factory=UnicodeKeysDict),
                message_expiry_in_seconds,
            )

    def send_request(self, job_request, message_expiry_in_seconds=None):
        # type: (JobRequest, Optional[int]) -> int
        """
        Send a JobRequest, and return a request ID.

        :param job_request: The job request object to send
        :param message_expiry_in_seconds: How soon the message will expire if not received by a server (defaults to
                                          sixty seconds unless the settings are otherwise)

        :return: The request ID

        :raises: :class:`pysoa.common.transport.errors.PySOATransportError`
        """
        request_id = self.request_counter
        self.request_counter += 1
        meta = {
            'client_version': self._client_version,
        }  # type: Dict[six.text_type, Any]
        try:
            with self.metrics.timer('client.send.including_middleware', resolution=TimerResolution.MICROSECONDS):
                self._middleware_send_request_wrapper(request_id, meta, job_request, message_expiry_in_seconds)
            return request_id
        finally:
            self.metrics.publish_all()

    def _base_get_response(self, receive_timeout_in_seconds=None):
        # type: (int) -> Tuple[Optional[int], Optional[JobResponse]]
        with self.metrics.timer('client.receive.excluding_middleware', resolution=TimerResolution.MICROSECONDS):
            request_id, meta, message = self.transport.receive_response_message(receive_timeout_in_seconds)
            if message is None:
                return None, None
            else:
                return request_id, JobResponse(**message)

    def get_all_responses(self, receive_timeout_in_seconds=None):
        # type: (Optional[int]) -> Generator[Tuple[int, JobResponse], None, None]
        """
        Receive all available responses from the transport as a generator.

        :param receive_timeout_in_seconds: How long to block without receiving a message before raising
                                           :class:`pysoa.common.transport.errors.MessageReceiveTimeout` (defaults to
                                           five seconds unless the settings are otherwise).

        :return: A generator that yields a two-tuple of request ID, job response

        :raises: :class:`pysoa.common.transport.errors.PySOATransportError`, :class:`StopIteration`
        """
        try:
            while True:
                with self.metrics.timer('client.receive.including_middleware', resolution=TimerResolution.MICROSECONDS):
                    request_id, response = self._middleware_get_response_wrapper(receive_timeout_in_seconds)
                if request_id is None or response is None:
                    break
                yield request_id, response
        finally:
            self.metrics.publish_all()


_FR = TypeVar(
    '_FR',
    ActionResponse,
    JobResponse,
    List[ActionResponse],
    List[JobResponse],
    Generator[ActionResponse, None, None],
    Generator[JobResponse, None, None],
)
ActionRequestArgument = Union[
    ActionRequest,
    Dict[six.text_type, Any],
]
ActionRequestArgumentList = Union[
    List[ActionRequest],
    List[Dict[six.text_type, Any]],
]
ActionRequestArgumentIterable = Union[
    Iterable[ActionRequest],
    Iterable[Dict[six.text_type, Any]],
]
JobRequestArgument = Dict[six.text_type, Any]


class FutureSOAResponse(Generic[_FR]):
    """
    A future representing a retrievable response after sending a request.
    """

    DelayedException = NamedTuple('DelayedException', (
        ('tp', Type[BaseException]),
        ('value', BaseException),
        ('tb', Optional[TracebackType]),
    ))

    def __init__(self, get_response):  # type: (Callable[[Optional[int]], _FR]) -> None
        self._get_response = get_response  # type: Callable[[Optional[int]], _FR]
        self._response = None  # type: Optional[_FR]
        self._raise = None  # type: Optional[FutureSOAResponse.DelayedException]

    def result(self, timeout=None):  # type: (Optional[int]) -> _FR
        """
        Obtain the result of this future response.

        The first time you call this method on a given future response, it will block for a response and then
        either return the response or raise any errors raised by the response. You can specify an optional timeout,
        which will override any timeout specified in the client settings or when calling the request method. If a
        timeout occurs, :class:`pysoa.common.transport.errors.MessageReceiveTimeout` will be raised. It will not be
        cached, and you can attempt to call this again, and those subsequent calls to :meth:`result`
        (or :meth:`exception`) will be treated like first-time calls until a response is returned or non-timeout error
        is raised.

        The subsequent times you call this method on a given future response after obtaining a non-timeout response,
        any specified timeout will be ignored, and the cached response will be returned (or the cached exception
        re-raised).

        :param timeout: If specified, the client will block for at most this many seconds waiting for a response.
                        If not specified, but a timeout was specified when calling the request method, the client
                        will block for at most that many seconds waiting for a response. If neither this nor the
                        request method timeout are specified, the configured timeout setting (or default of 5
                        seconds) will be used.

        :return: The response

        :raises: :class:`pysoa.common.transport.errors.PySOATransportError`,
                 :class:`pysoa.client.errors.CallActionError`, :class:`pysoa.client.errors.CallJobError`
        """
        if self._raise:
            if six.PY2:
                six.reraise(tp=self._raise.tp, value=self._raise.value, tb=self._raise.tb)
            else:
                # We do it this way because six.reraise adds extra traceback items in Python 3
                raise self._raise.value.with_traceback(self._raise.tb)
        if self._response:
            return self._response

        try:
            self._response = self._get_response(timeout)
            return self._response
        except MessageReceiveTimeout:
            raise
        except Exception:
            t, e, tb = sys.exc_info()
            assert t is not None and e is not None
            self._raise = self.DelayedException(t, e, tb)
            raise

    def exception(self, timeout=None):  # type: (int) -> Optional[BaseException]
        """
        Obtain the exception raised by the call, blocking if necessary, per the rules specified in the
        documentation for :meth:`result`. If the call completed without raising an exception, `None` is returned.
        If a timeout occurs, :class:`pysoa.common.transport.errors.MessageReceiveTimeout` will be raised (not returned).

        :param timeout: If specified, the client will block for at most this many seconds waiting for a response.
                        If not specified, but a timeout was specified when calling the request method, the client
                        will block for at most that many seconds waiting for a response. If neither this nor the
                        request method timeout are specified, the configured timeout setting (or default of 5
                        seconds) will be used.

        :return: The exception
        """
        if self.running():
            try:
                self.result(timeout)
                return None
            except MessageReceiveTimeout:
                raise
            except Exception as e:
                # TODO self._raise = self.DelayedException(*sys.exc_info())
                return e

        if self._raise:
            return self._raise.value

        return None

    def running(self):  # type: () -> bool
        """
        Returns `True` if the response (or exception) has not yet been obtained, `False` otherwise.

        :return: Whether the request is believed to still be running (this is updated only when `result` or
                 `exception` is called).
        """
        return not self.done()

    def done(self):  # type: () -> bool
        """
        Returns `False` if the response (or exception) has not yet been obtained, `True` otherwise.

        :return: Whether the request is known to be done (this is updated only when `result` or `exception` is
                 called).
        """
        return bool(self._response or self._raise)


class Client(object):
    """
    The `Client` provides a simple interface for calling actions on services and supports both sequential and
    parallel action invocation.
    """

    settings_class = ClientSettings  # type: Type[ClientSettings]
    handler_class = ServiceHandler  # type: Type[ServiceHandler]

    def __init__(
        self,
        config,  # type: Mapping[six.text_type, SettingsData]
        expansion_config=None,  # type: Optional[SettingsData]
        settings_class=None,  # type: Optional[Type[ClientSettings]]
        context=None,  # type: Optional[Context]
    ):
        # type: (...) -> None
        """
        :param config: The entire client configuration dict, whose keys are service names and values are settings dicts
                       abiding by the :class:`pysoa.client.settings.ClientSettings` schema
        :param expansion_config: The optional expansion configuration dict, if this client supports expansions, which
                                 is a dict abiding by the :class:`pysoa.client.expander.ExpansionSettings` schema
        :param settings_class: An optional settings schema enforcement class to use, which overrides the default of
                               :class:`pysoa.client.settings.ClientSettings`
        :param context: An optional base request context that will be used for all requests this client instance sends
                        (individual calls can add to and override the values supplied in this context dict)
        """
        self.settings_class = settings_class or self.__class__.settings_class
        self.context = context or {}  # type: Context

        self.handlers = {}  # type: Dict[six.text_type, ServiceHandler]
        self.settings = {}  # type: Dict[six.text_type, ClientSettings]
        self.config = config or {}  # type: Mapping[six.text_type, SettingsData]
        for service_name, service_config in self.config.items():
            self.settings[service_name] = self.settings_class(service_config)

        if expansion_config:
            expansion_settings = ExpansionSettings(expansion_config)
            self.expansion_converter = ExpansionConverter(
                type_routes=cast(TypeRoutes, expansion_settings['type_routes']),
                type_expansions=cast(TypeExpansions, expansion_settings['type_expansions']),
            )

    FutureResponse = FutureSOAResponse  # TODO backwards compatibility, will be removed in 1.0.0

    # Exceptions

    ImproperlyConfigured = ImproperlyConfigured
    """Convenience alias for :class:`pysoa.client.errors.ImproperlyConfigured`"""

    InvalidExpansionKey = InvalidExpansionKey
    """Convenience alias for :class:`pysoa.client.errors.InvalidExpansionKey`"""

    JobError = CallJobError
    """Convenience alias for :class:`pysoa.client.errors.CallJobError`"""

    CallJobError = CallJobError
    """Convenience alias for :class:`pysoa.client.errors.CallJobError`"""

    CallActionError = CallActionError
    """Convenience alias for :class:`pysoa.client.errors.CallActionError`"""

    # Blocking methods that send a request and wait until a response is available

    def call_action(
        self,
        service_name,  # type: six.text_type
        action,  # type: six.text_type
        body=None,  # type: Body
        expansions=None,  # type: Expansions
        raise_job_errors=True,  # type: bool
        raise_action_errors=True,  # type: bool
        timeout=None,  # type: Optional[int]
        switches=None,  # type: Optional[Union[List[int], AbstractSet[int]]]
        correlation_id=None,  # type: Optional[six.text_type]
        context=None,  # type: Optional[Context]
        control_extra=None,  # type: Optional[Control]
    ):
        # type: (...) -> ActionResponse
        """
        Build and send a single job request with one action.

        Returns the action response or raises an exception if the action response is an error (unless
        `raise_action_errors` is passed as `False`) or if the job response is an error (unless `raise_job_errors` is
        passed as `False`).

        This method performs expansions if the `Client` is configured with an expansion converter.

        :param service_name: The name of the service to call.
        :param action: The name of the action to call.
        :param body: The action request body.
        :param expansions: A dictionary representing the expansions to perform.
        :param raise_job_errors: Whether to raise a :class:`pysoa.client.errors.CallJobError` if the job response
                                 contains errors (defaults to `True`).
        :param raise_action_errors: Whether to raise a :class:`pysoa.client.errors.CallActionError` if any action
                                    responses contain errors (defaults to `True`).
        :param timeout: If provided, this will override the default transport timeout values to; requests will expire
                        after this number of seconds plus some buffer defined by the transport, and the client will not
                        block waiting for a response for longer than this amount of time.
        :param switches: A list of switch value integers.
        :param correlation_id: The request correlation ID.
        :param context: A dictionary of extra values to include in the context header.
        :param control_extra: A dictionary of extra values to include in the control header.

        :return: The action response.

        :raises: :class:`pysoa.common.transport.errors.PySOATransportError`,
                 :class:`pysoa.client.errors.CallActionError`, :class:`pysoa.client.errors.CallJobError`
        """
        return self.call_action_future(
            service_name=service_name,
            action=action,
            body=body,
            expansions=expansions,
            raise_job_errors=raise_job_errors,
            raise_action_errors=raise_action_errors,
            timeout=timeout,
            switches=switches,
            correlation_id=correlation_id,
            context=context,
            control_extra=control_extra,
        ).result()

    def call_actions(
        self,
        service_name,  # type: six.text_type
        actions,  # type: ActionRequestArgumentList
        expansions=None,  # type: Expansions
        raise_job_errors=True,  # type: bool
        raise_action_errors=True,  # type: bool
        timeout=None,  # type: Optional[int]
        switches=None,  # type: Optional[Union[List[int], AbstractSet[int]]]
        correlation_id=None,  # type: Optional[six.text_type]
        continue_on_error=False,  # type: bool
        context=None,  # type: Optional[Context]
        control_extra=None,  # type: Optional[Control]
    ):
        # type: (...) -> JobResponse
        """
        Build and send a single job request with one or more actions.

        Returns a list of action responses, one for each action in the same order as provided, or raises an exception
        if any action response is an error (unless `raise_action_errors` is passed as `False`) or if the job response
        is an error (unless `raise_job_errors` is passed as `False`).

        This method performs expansions if the `Client` is configured with an expansion converter.

        :param service_name: The name of the service to call.
        :param actions: A list of :class:`pysoa.common.types.ActionRequest` objects and/or dicts that can be converted
                        to `ActionRequest` objects.
        :param expansions: A dictionary representing the expansions to perform.
        :param raise_job_errors: Whether to raise a :class:`pysoa.client.errors.CallJobError` if the job response
                                 contains errors (defaults to `True`).
        :param raise_action_errors: Whether to raise a :class:`pysoa.client.errors.CallActionError` if any action
                                    responses contain errors (defaults to `True`).
        :param timeout: If provided, this will override the default transport timeout values to; requests will expire
                        after this number of seconds plus some buffer defined by the transport, and the client will not
                        block waiting for a response for longer than this amount of time.
        :param switches: A list of switch value integers.
        :param correlation_id: The request correlation ID.
        :param continue_on_error: Whether the service should continue executing further actions once one action has
                                  returned errors.
        :param context: A dictionary of extra values to include in the context header.
        :param control_extra: A dictionary of extra values to include in the control header.

        :return: The job response.

        :raises: :class:`pysoa.common.transport.errors.PySOATransportError`,
                 :class:`pysoa.client.errors.CallActionError`, :class:`pysoa.client.errors.CallJobError`
        """
        return self.call_actions_future(
            service_name=service_name,
            actions=actions,
            expansions=expansions,
            raise_job_errors=raise_job_errors,
            raise_action_errors=raise_action_errors,
            timeout=timeout,
            switches=switches,
            correlation_id=correlation_id,
            continue_on_error=continue_on_error,
            context=context,
            control_extra=control_extra,
        ).result()

    def call_actions_parallel(
        self,
        service_name,  # type: six.text_type
        actions,  # type: ActionRequestArgumentIterable
        expansions=None,  # type: Expansions
        raise_job_errors=True,  # type: bool
        raise_action_errors=True,  # type: bool
        catch_transport_errors=False,  # type: bool
        timeout=None,  # type: Optional[int]
        switches=None,  # type: Optional[Union[List[int], AbstractSet[int]]]
        correlation_id=None,  # type: Optional[six.text_type]
        context=None,  # type: Optional[Context]
        control_extra=None,  # type: Optional[Control]
    ):
        # type: (...) -> Generator[ActionResponse, None, None]
        """
        Build and send multiple job requests to one service, each job with one action, to be executed in parallel, and
        return once all responses have been received.

        Returns a list of action responses, one for each action in the same order as provided, or raises an exception
        if any action response is an error (unless `raise_action_errors` is passed as `False`) or if any job response
        is an error (unless `raise_job_errors` is passed as `False`).

        This method performs expansions if the `Client` is configured with an expansion converter.

        :param service_name: The name of the service to call.
        :param actions: A list of :class:`pysoa.common.types.ActionRequest` objects and/or dicts that can be converted
                        to `ActionRequest` objects.
        :param expansions: A dictionary representing the expansions to perform.
        :param raise_job_errors: Whether to raise a :class:`pysoa.client.errors.CallJobError` if the job response
                                 contains errors (defaults to `True`).
        :param raise_action_errors: Whether to raise a :class:`pysoa.client.errors.CallActionError` if any action
                                    responses contain errors (defaults to `True`).
        :param catch_transport_errors: Whether to catch transport errors and return them instead of letting them
                                       propagate. By default (`False`), all raised
                                       :class:`pysoa.common.transport.errors.PySOATransportError` exceptions cause the
                                       entire process to terminate, potentially losing responses. If this argument is
                                       set to `True`, those errors are, instead, caught, and they are returned in place
                                       of their corresponding responses in the returned list of job responses. You
                                       should not do this in most cases, but it is helpful if you really need to get
                                       the successful responses even if there are errors getting other responses.
        :param timeout: If provided, this will override the default transport timeout values to; requests will expire
                        after this number of seconds plus some buffer defined by the transport, and the client will not
                        block waiting for a response for longer than this amount of time.
        :param switches: A list of switch value integers.
        :param correlation_id: The request correlation ID.
        :param context: A dictionary of extra values to include in the context header.
        :param control_extra: A dictionary of extra values to include in the control header.

        :return: A generator of action responses

        :raises: :class:`pysoa.common.transport.errors.PySOATransportError`,
                 :class:`pysoa.client.errors.CallActionError`, :class:`pysoa.client.errors.CallJobError`
        """
        return self.call_actions_parallel_future(
            service_name=service_name,
            actions=actions,
            expansions=expansions,
            raise_job_errors=raise_job_errors,
            raise_action_errors=raise_action_errors,
            catch_transport_errors=catch_transport_errors,
            timeout=timeout,
            switches=switches,
            correlation_id=correlation_id,
            context=context,
            control_extra=control_extra,
        ).result()

    def call_jobs_parallel(
        self,
        jobs,  # type: Iterable[JobRequestArgument]
        expansions=None,  # type: Expansions
        raise_job_errors=True,  # type: bool
        raise_action_errors=True,  # type: bool
        catch_transport_errors=False,  # type: bool
        timeout=None,  # type: Optional[int]
        switches=None,  # type: Optional[Union[List[int], AbstractSet[int]]]
        correlation_id=None,  # type: Optional[six.text_type]
        continue_on_error=False,  # type: bool
        context=None,  # type: Optional[Context]
        control_extra=None,  # type: Optional[Control]
    ):
        # type: (...) -> List[JobResponse]
        """
        Build and send multiple job requests to one or more services, each with one or more actions, to be executed in
        parallel, and return once all responses have been received.

        Returns a list of job responses, one for each job in the same order as provided, or raises an exception if any
        job response is an error (unless `raise_job_errors` is passed as `False`) or if any action response is an
        error (unless `raise_action_errors` is passed as `False`).

        This method performs expansions if the `Client` is configured with an expansion converter.

        :param jobs: A list of job request dicts, each containing `service_name` and `actions`, where `actions` is a
                     list of :class:`pysoa.common.types.ActionRequest` objects and/or dicts that can be converted to
                     `ActionRequest` objects.
        :param expansions: A dictionary representing the expansions to perform.
        :param raise_job_errors: Whether to raise a :class:`pysoa.client.errors.CallJobError` if the job response
                                 contains errors (defaults to `True`).
        :param raise_action_errors: Whether to raise a :class:`pysoa.client.errors.CallActionError` if any action
                                    responses contain errors (defaults to `True`).
        :param catch_transport_errors: Whether to catch transport errors and return them instead of letting them
                                       propagate. By default (`False`), all raised
                                       :class:`pysoa.common.transport.errors.PySOATransportError` exceptions cause the
                                       entire process to terminate, potentially losing responses. If this argument is
                                       set to `True`, those errors are, instead, caught, and they are returned in place
                                       of their corresponding responses in the returned list of job responses. You
                                       should not do this in most cases, but it is helpful if you really need to get
                                       the successful responses even if there are errors getting other responses.
        :param timeout: If provided, this will override the default transport timeout values to; requests will expire
                        after this number of seconds plus some buffer defined by the transport, and the client will not
                        block waiting for a response for longer than this amount of time.
        :param switches: A list of switch value integers.
        :param correlation_id: The request correlation ID.
        :param continue_on_error: Whether the service should continue executing further actions once one action has
                                  returned errors (only applies to multiple actions in a single job).
        :param context: A dictionary of extra values to include in the context header.
        :param control_extra: A dictionary of extra values to include in the control header.

        :return: The job response

        :raises: :class:`pysoa.common.transport.errors.PySOATransportError`,
                 :class:`pysoa.client.errors.CallActionError`, :class:`pysoa.client.errors.CallJobError`
        """
        return self.call_jobs_parallel_future(
            jobs=jobs,
            expansions=expansions,
            raise_job_errors=raise_job_errors,
            raise_action_errors=raise_action_errors,
            catch_transport_errors=catch_transport_errors,
            timeout=timeout,
            switches=switches,
            correlation_id=correlation_id,
            continue_on_error=continue_on_error,
            context=context,
            control_extra=control_extra,
        ).result()

    # Non-blocking methods that send a request and then return a future from which the response can later be obtained.

    def call_action_future(
        self,
        service_name,  # type: six.text_type
        action,  # type: six.text_type
        body=None,  # type: Optional[Body]
        expansions=None,  # type: Expansions
        raise_job_errors=True,  # type: bool
        raise_action_errors=True,  # type: bool
        timeout=None,  # type: Optional[int]
        switches=None,  # type: Optional[Union[List[int], AbstractSet[int]]]
        correlation_id=None,  # type: Optional[six.text_type]
        context=None,  # type: Optional[Context]
        control_extra=None,  # type: Optional[Control]
    ):
        # type: (...) -> FutureSOAResponse[ActionResponse]
        """
        This method is identical in signature and behavior to :meth:`call_action`, except that it sends the request
        and then immediately returns a :class:`FutureResponse` instead of blocking waiting on a response and returning
        an :class:`pysoa.common.types.ActionResponse`. Just call `result(timeout=None)` on the future response to block
        for an available response. Some of the possible exceptions may be raised when this method is called; others may
        be raised when the future is used.

        :return: A future from which the action response can later be retrieved

        :raises: :class:`pysoa.common.transport.errors.PySOATransportError`
        """
        action_request = ActionRequest(
            action=action,
            body=body or {},
        )
        future = self.call_actions_future(
            service_name=service_name,
            actions=[action_request],
            expansions=expansions,
            raise_job_errors=raise_job_errors,
            raise_action_errors=raise_action_errors,
            timeout=timeout,
            switches=switches,
            correlation_id=correlation_id,
            context=context,
            control_extra=control_extra,
        )

        def get_result(_timeout):  # type: (Optional[int]) -> ActionResponse
            result = future.result(_timeout)
            if result.errors:
                # This can only happen if raise_job_errors is set to False, so return the list of errors, just like
                # other methods do below. Being sneaky with the cast, can only happen if caller asks.
                return cast(ActionResponse, result.errors)
            return result.actions[0]

        return FutureSOAResponse(get_result)

    def call_actions_future(
        self,
        service_name,  # type: six.text_type
        actions,  # type: ActionRequestArgumentList
        expansions=None,  # type: Expansions
        raise_job_errors=True,  # type: bool
        raise_action_errors=True,  # type: bool
        timeout=None,  # type: Optional[int]
        switches=None,  # type: Optional[Union[List[int], AbstractSet[int]]]
        correlation_id=None,  # type: Optional[six.text_type]
        continue_on_error=False,  # type: bool
        context=None,  # type: Optional[Context]
        control_extra=None,  # type: Optional[Control]
    ):
        # type: (...) -> FutureSOAResponse[JobResponse]
        """
        This method is identical in signature and behavior to :meth:`call_actions`, except that it sends the request
        and then immediately returns a :class:`FutureResponse` instead of blocking waiting on a response and returning a
        :class:`pysoa.common.types.JobResponse`. Just call `result(timeout=None)` on the future response to block for
        an available response. Some of the possible exceptions may be raised when this method is called; others may be
        raised when the future is used.

        :return: A future from which the job response can later be retrieved

        :raises: :class:`pysoa.common.transport.errors.PySOATransportError`,
        """
        expected_request_id = self.send_request(
            service_name=service_name,
            actions=actions,
            switches=switches,
            correlation_id=correlation_id,
            continue_on_error=continue_on_error,
            context=context,
            control_extra=control_extra,
            message_expiry_in_seconds=timeout if timeout else None,
        )

        def get_response(_timeout):  # type: (Optional[int]) -> JobResponse
            # Get all responses
            responses = list(
                self.get_all_responses(service_name, receive_timeout_in_seconds=_timeout or timeout)
            )  # type: List[Tuple[int, JobResponse]]

            # Try to find the expected response
            found = False
            response = None  # type: Optional[JobResponse]
            for request_id, response in responses:
                if request_id == expected_request_id:
                    found = True
                    break
            if not found or not response:
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
                self._perform_expansion(
                    response.actions,
                    expansions,
                    switches=switches,
                    correlation_id=correlation_id,
                    context=context,
                    control_extra=control_extra,
                    message_expiry_in_seconds=timeout if timeout else None,
                )

            return response

        return FutureSOAResponse(get_response)

    def call_actions_parallel_future(
        self,
        service_name,  # type: six.text_type
        actions,  # type: ActionRequestArgumentIterable
        expansions=None,  # type: Expansions
        raise_job_errors=True,  # type: bool
        raise_action_errors=True,  # type: bool
        catch_transport_errors=False,  # type: bool
        timeout=None,  # type: Optional[int]
        switches=None,  # type: Optional[Union[List[int], AbstractSet[int]]]
        correlation_id=None,  # type: Optional[six.text_type]
        context=None,  # type: Optional[Context]
        control_extra=None,  # type: Optional[Control]
    ):
        # type: (...) -> FutureSOAResponse[Generator[ActionResponse, None, None]]
        """
        This method is identical in signature and behavior to :meth:`call_actions_parallel`, except that it sends the
        requests and then immediately returns a :class:`FutureResponse` instead of blocking waiting on responses and
        returning a generator. Just call `result(timeout=None)` on the future response to block for an available
        response (which will be a generator). Some of the possible exceptions may be raised when this method is called;
        others may be raised when the future is used.

        If argument `raise_job_errors` is supplied and is `False`, some items in the result list might be lists of job
        errors instead of individual :class:`pysoa.common.types.ActionResponse` objects. Be sure to check for that if
        used in this manner.

        If argument `catch_transport_errors` is supplied and is `True`, some items in the result list might be instances
        of `Exception` instead of individual :class:`pysoa.common.types.ActionResponse` objects. Be sure to check for
        that if used in this manner.

        :return: A generator of action responses that blocks waiting on responses once you begin iteration

        :raises: :class:`pysoa.common.transport.errors.PySOATransportError`,
        """
        job_responses = self.call_jobs_parallel_future(
            jobs=({'service_name': service_name, 'actions': [action]} for action in actions),
            expansions=expansions,
            raise_job_errors=raise_job_errors,
            raise_action_errors=raise_action_errors,
            catch_transport_errors=catch_transport_errors,
            timeout=timeout,
            switches=switches,
            correlation_id=correlation_id,
            context=context,
            control_extra=control_extra,
        )

        def parse_results(results):  # type: (List[JobResponse]) -> Generator[ActionResponse, None, None]
            for job in results:
                if isinstance(job, Exception):
                    yield cast(ActionResponse, job)  # sneaky cast, only happens if caller wants exceptions returned
                elif job.errors:
                    yield cast(ActionResponse, job.errors)  # sneaky cast, only happens if caller wants errors returned
                else:
                    yield job.actions[0]

        def get_response(_timeout):  # type: (Optional[int]) -> Generator[ActionResponse, None, None]
            # This looks weird, but we want `job_response.result` to be called eagerly, before they actually start
            # iterating over it.
            return parse_results(job_responses.result(_timeout))

        return FutureSOAResponse(get_response)

    def call_jobs_parallel_future(
        self,
        jobs,  # type: Iterable[JobRequestArgument]
        expansions=None,  # type: Expansions
        raise_job_errors=True,  # type: bool
        raise_action_errors=True,  # type: bool
        catch_transport_errors=False,  # type: bool
        timeout=None,  # type: Optional[int]
        switches=None,  # type: Optional[Union[List[int], AbstractSet[int]]]
        correlation_id=None,  # type: Optional[six.text_type]
        continue_on_error=False,  # type: bool
        context=None,  # type: Optional[Context]
        control_extra=None,  # type: Optional[Control]
    ):
        # type: (...) -> FutureSOAResponse[List[JobResponse]]
        """
        This method is identical in signature and behavior to :meth:`call_jobs_parallel`, except that it sends the
        requests and then immediately returns a :class:`FutureResponse` instead of blocking waiting on all responses and
        returning a `list` of :class:`pysoa.common.types.JobResponse` objects. Just call `result(timeout=None)` on the
        future response to block for an available response. Some of the possible exceptions may be raised when this
        method is called; others may be raised when the future is used.

        :return: A future from which the list of job responses can later be retrieved

        :raises: :class:`pysoa.common.transport.errors.PySOATransportError`
        """
        error_key = 0
        transport_errors = {}  # type: Dict[Tuple[six.text_type, int], Exception]

        response_reassembly_keys = []  # type: List[Tuple[six.text_type, int]]
        service_request_ids = {}  # type: Dict[six.text_type, Set[int]]
        for job in jobs:
            try:
                sent_request_id = self.send_request(
                    service_name=job['service_name'],
                    actions=job['actions'],
                    switches=switches,
                    correlation_id=correlation_id,
                    continue_on_error=continue_on_error,
                    context=context,
                    control_extra=control_extra,
                    message_expiry_in_seconds=timeout if timeout else None,
                )
                service_request_ids.setdefault(job['service_name'], set()).add(sent_request_id)
            except PySOATransportError as e:
                if not catch_transport_errors:
                    raise
                sent_request_id = error_key = error_key - 1
                transport_errors[(job['service_name'], sent_request_id)] = e

            response_reassembly_keys.append((job['service_name'], sent_request_id))

        def get_response(_timeout):  # type: (Optional[int]) -> List[JobResponse]
            service_responses = {}
            for service_name, request_ids in six.iteritems(service_request_ids):
                try:
                    for request_id, response in self.get_all_responses(
                        service_name,
                        receive_timeout_in_seconds=_timeout or timeout,
                    ):
                        if request_id not in request_ids:
                            raise Exception(
                                'Got response ID {}, not in set of expected IDs {}'.format(request_id, request_ids)
                            )
                        service_responses[(service_name, request_id)] = response
                        if catch_transport_errors:
                            # We don't need the set to be reduced unless we're catching errors
                            request_ids.remove(request_id)
                except PySOATransportError as t_e:
                    if not catch_transport_errors:
                        raise
                    for request_id in request_ids:
                        transport_errors[(service_name, request_id)] = t_e

            responses = []  # type: List[JobResponse]
            actions_to_expand = []  # type: List[ActionResponse]
            for service_name, request_id in response_reassembly_keys:
                if request_id < 0:
                    # A transport error occurred during send, and we are catching errors, so add it to the list
                    # Sneaky cast, but this can only happen if the caller explicitly asked for it
                    responses.append(cast(JobResponse, transport_errors[(service_name, request_id)]))
                    continue

                if (service_name, request_id) not in service_responses:
                    if (service_name, request_id) in transport_errors:
                        # A transport error occurred during receive, and we are catching errors, so add it to the list
                        # Sneaky cast, but this can only happen if the caller explicitly asked for it
                        responses.append(cast(JobResponse, transport_errors[(service_name, request_id)]))
                        continue

                    # It shouldn't be possible for this to happen unless the code has a bug, but let's raise a
                    # meaningful exception just in case a bug exists, because KeyError will not be helpful.
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
                self._perform_expansion(
                    actions_to_expand,
                    expansions,
                    switches=switches,
                    correlation_id=correlation_id,
                    context=context,
                    control_extra=control_extra,
                    message_expiry_in_seconds=timeout if timeout else None,
                )

            return responses

        return FutureSOAResponse(get_response)

    # Methods used to send a request in a non-blocking manner and then later block for a response as a separate step

    def send_request(
        self,
        service_name,  # type: six.text_type
        actions,  # type: ActionRequestArgumentList
        switches=None,  # type: Optional[Union[List[int], AbstractSet[int]]]
        correlation_id=None,  # type: Optional[six.text_type]
        continue_on_error=False,  # type: bool
        context=None,  # type: Optional[Context]
        control_extra=None,  # type: Optional[Control]
        message_expiry_in_seconds=None,  # type: Optional[int]
        suppress_response=False,  # type: bool
    ):
        # type: (...) -> int
        """
        Build and send a JobRequest, and return a request ID.

        The context and control_extra arguments may be used to include extra values in the
        context and control headers, respectively.

        :param service_name: The name of the service from which to receive responses
        :param actions: A list of `ActionRequest` objects or dictionaries
        :param switches: A list of switch value integers
        :param correlation_id: The request correlation ID
        :param continue_on_error: Whether to continue executing further actions once one action has returned errors
        :param context: A dictionary of extra values to include in the context header
        :param control_extra: A dictionary of extra values to include in the control header
        :param message_expiry_in_seconds: How soon the message will expire if not received by a server (defaults to
                                          sixty seconds unless the settings are otherwise)
        :param suppress_response: If `True`, the service will process the request normally but omit the step of
                                  sending a response back to the client (use this feature to implement send-and-forget
                                  patterns for asynchronous execution)

        :return: The request ID

        :raises: :class:`pysoa.common.transport.errors.PySOATransportError`
        """

        control_extra = control_extra.copy() if control_extra else {}
        if message_expiry_in_seconds and 'timeout' not in control_extra:
            control_extra['timeout'] = message_expiry_in_seconds

        handler = self._get_handler(service_name)
        control = self._make_control_header(
            continue_on_error=continue_on_error,
            control_extra=control_extra,
            suppress_response=suppress_response,
        )
        context = self._make_context_header(
            switches=switches,
            correlation_id=correlation_id,
            context_extra=context,
        )
        job_request = JobRequest(actions=actions, control=control, context=context or {})
        return handler.send_request(job_request, message_expiry_in_seconds)

    def get_all_responses(self, service_name, receive_timeout_in_seconds=None):
        # type: (six.text_type, Optional[int]) -> Generator[Tuple[int, JobResponse], None, None]
        """
        Receive all available responses from the service as a generator.

        :param service_name: The name of the service from which to receive responses
        :param receive_timeout_in_seconds: How long to block without receiving a message before raising
                                           :class:`pysoa.common.transport.errors.MessageReceiveTimeout` (defaults to
                                           five seconds unless the settings are otherwise).

        :return: A generator that yields a two-tuple of request ID, job response

        :raises: :class:`pysoa.common.transport.errors.PySOATransportError`
        """

        handler = self._get_handler(service_name)
        return handler.get_all_responses(receive_timeout_in_seconds)

    # Private methods used to support all of the above methods

    def _perform_expansion(
        self,
        actions,  # type: Iterable[ActionResponse]
        expansions,  # type: Expansions
        **kwargs  # type: Any
    ):
        # Perform expansions
        if expansions and getattr(self, 'expansion_converter', None):
            try:
                trees = self.expansion_converter.dict_to_trees(expansions)
                objects_to_expand = self._extract_candidate_objects(actions, trees)
            except KeyError as e:
                raise self.InvalidExpansionKey('Invalid key in expansion request: {}'.format(e.args[0]))
            else:
                self._expand_objects(objects_to_expand, trees, **kwargs)

    @classmethod
    def _extract_candidate_objects(
        cls,
        actions,  # type: Iterable[ActionResponse]
        expansion_trees,  # type: List[TypeNode]
    ):
        # type: (...) -> List[Tuple[Dict[Any, Any], List[ExpansionNode]]]
        # Build initial list of objects to expand
        objects_to_expand = []  # type: List[Tuple[Dict[Any, Any], List[ExpansionNode]]]
        for type_node in expansion_trees:
            for action in actions:
                cls._extend_expansion_objects(objects_to_expand, type_node, action.body)
        return objects_to_expand

    @staticmethod
    def _extend_expansion_objects(
        objects_to_expand,  # type: List[Tuple[Dict[Any, Any], List[ExpansionNode]]]
        type_node,  # type: TypeNode
        body,  # type: Body
    ):
        objects_to_expand.extend(
            (expansion_object, type_node.expansions)
            for expansion_object in type_node.find_objects(body)
        )

    def _expand_objects(
        self,
        objects_to_expand,  # type: List[Tuple[Dict[Any, Any], List[ExpansionNode]]]
        expansion_trees,  # type: List[TypeNode]
        **kwargs  # type: Any
    ):
        # Keep track of expansion action errors that need to be raised
        expansion_job_errors_to_raise = []  # type: List[Error]
        expansion_action_errors_to_raise = []  # type: List[ActionResponse]
        # Keep track of values that have been expanded already to prevent infinite recursion
        expansion_requests_made = {}  # type: Dict[six.text_type, Set[Any]]
        # Loop until we have no outstanding objects to expand
        while objects_to_expand:
            # Form a collection of optimized bulk requests that need to be made, a map of service name to a map of
            # action names to a dict instructing how to call the action and with what parameters
            pending_expansion_requests = collections.defaultdict(
                lambda: collections.defaultdict(dict),
            )  # type: Dict[six.text_type, Dict[six.text_type, Dict[six.text_type, Any]]]

            # Initialize mapping of service request IDs to expansion objects
            expansion_service_requests = collections.defaultdict(
                dict
            )  # type: Dict[six.text_type, Dict[int, List[Dict[six.text_type, Any]]]]

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
                    key = '{}.{}.{}'.format(service_name, action_name, instructions['field'])
                    values = instructions['values']
                    if expansion_requests_made.setdefault(key, set()):  # we've called this expansion action already
                        values = values - expansion_requests_made[key]  # exclude all values we've previously expanded
                        if not values:
                            # all values were excluded, so log a note
                            _logger.info('Avoiding infinite recursion by skipping duplicate expansion: {} = {}'.format(
                                key,
                                instructions['values'],
                            ))
                            continue
                    expansion_requests_made[key].update(values)  # record that we have now expanded these values

                    request_id = self.send_request(
                        service_name,
                        actions=[
                            {'action': action_name, 'body': {instructions['field']: list(values)}},
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
                    for request_id, response in self.get_all_responses(
                        service_name,
                        receive_timeout_in_seconds=kwargs.get('message_expiry_in_seconds'),
                    ):
                        action_response = None  # type: Optional[ActionResponse]
                        # Pop the request mapping off the list of pending requests and get the value of the expansion
                        # from the response.
                        for object_node in request_ids_to_objects.pop(request_id):
                            object_to_expand = object_node['object']
                            expansion_node = object_node['expansion']

                            if response.errors:
                                if expansion_node.raise_action_errors:
                                    expansion_job_errors_to_raise.extend(response.errors)
                                continue

                            action_response = response.actions[0]
                            if action_response.errors and expansion_node.raise_action_errors:
                                expansion_action_errors_to_raise.append(action_response)

                            # If everything is okay, replace the expansion object with the response value
                            if action_response.body:
                                values = action_response.body[expansion_node.response_field]
                                response_key = object_to_expand[expansion_node.source_field]
                                if response_key in values:
                                    # It's okay if there isn't a matching value for this expansion; just means no match
                                    object_to_expand[expansion_node.destination_field] = values[response_key]

                                # Potentially add additional pending expansion requests (nested approach).
                                if expansion_node.expansions:
                                    self._extend_expansion_objects(
                                        objects_to_expand,
                                        expansion_node,
                                        action_response.body,
                                    )

                        if action_response and not action_response.errors and action_response.body:
                            # Potentially add additional pending expansion requests (global approach).
                            for type_node in expansion_trees:
                                self._extend_expansion_objects(objects_to_expand, type_node, action_response.body)

            if expansion_action_errors_to_raise:
                raise self.CallActionError(expansion_action_errors_to_raise)

            if expansion_job_errors_to_raise:
                raise self.JobError(expansion_job_errors_to_raise)

    def _get_handler(self, service_name):  # type: (six.text_type) -> ServiceHandler
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
    def _make_control_header(continue_on_error=False, control_extra=None, suppress_response=False):
        # type: (bool, Optional[Control], bool) -> Control
        control = {
            'continue_on_error': continue_on_error,
            'suppress_response': suppress_response,
        }
        if control_extra:
            control.update(control_extra)
        return control

    def _make_context_header(
        self,
        switches=None,  # type: Optional[Union[List[int], AbstractSet[int]]]
        correlation_id=None,  # type: Optional[six.text_type]
        context_extra=None,  # type: Optional[Context]
    ):
        # type: (...) -> Context
        # Copy the underlying context object, if it was provided
        context = self.context.copy() if self.context else {}  # type: Context
        # Either add on, reuse or generate a correlation ID
        if correlation_id is not None:
            context['correlation_id'] = correlation_id
        elif 'correlation_id' not in context:
            context['correlation_id'] = six.text_type(uuid.uuid1().hex)
        # Switches can come from three different places, so merge them
        # and ensure that they are unique
        switches = set(switches or [])
        if context_extra:
            switches |= set(context_extra.pop('switches', []))
        context['switches'] = list(set(context.get('switches', [])) | switches)
        # Add any extra stuff
        if context_extra:
            context.update(context_extra)
        # context keys need to be guaranteed unicode
        return {six.text_type(k): v for k, v in six.iteritems(context)}
