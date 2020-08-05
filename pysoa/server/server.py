from __future__ import (
    absolute_import,
    unicode_literals,
)

import argparse
import atexit
import codecs
import importlib
import logging
import logging.config
import os
import random
import signal
import sys
import threading
import time
import traceback
from types import FrameType
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Mapping,
    Optional,
    Type,
    TypeVar,
    cast,
)

import attr
from pymetrics.instruments import (
    Timer,
    TimerResolution,
)
from pymetrics.recorders.base import MetricsRecorder
import six

from pysoa.client.client import Client
from pysoa.common.constants import (
    ERROR_CODE_ACTION_TIMEOUT,
    ERROR_CODE_JOB_TIMEOUT,
    ERROR_CODE_RESPONSE_NOT_SERIALIZABLE,
    ERROR_CODE_RESPONSE_TOO_LARGE,
    ERROR_CODE_SERVER_ERROR,
    ERROR_CODE_UNKNOWN,
)
from pysoa.common.errors import Error
from pysoa.common.logging import (
    PySOALogContextFilter,
    RecursivelyCensoredDictWrapper,
)
from pysoa.common.serializer.errors import InvalidField
from pysoa.common.transport.base import ServerTransport
from pysoa.common.transport.errors import (
    MessageReceiveTimeout,
    MessageTooLarge,
    TransientPySOATransportError,
)
from pysoa.common.types import (
    ActionResponse,
    Context,
    JobResponse,
    UnicodeKeysDict,
)
from pysoa.server import middleware
from pysoa.server.django.database import (
    django_close_old_database_connections,
    django_reset_database_queries,
)
from pysoa.server.errors import (
    ActionError,
    JobError,
)
from pysoa.server.internal.types import RequestSwitchSet
from pysoa.server.schemas import JobRequestSchema
from pysoa.server.settings import ServerSettings
from pysoa.server.types import (
    ActionType,
    EnrichedActionRequest,
    EnrichedJobRequest,
    IntrospectionActionType,
)
import pysoa.version


try:
    from pysoa.server.internal.event_loop import AsyncEventLoopThread
except (ImportError, SyntaxError):
    AsyncEventLoopThread = None  # type: ignore

try:
    from django.conf import settings as django_settings
    from django.core.cache import caches as django_caches
except ImportError:
    django_settings = None  # type: ignore
    django_caches = None  # type: ignore


__all__ = (
    'HarakiriInterrupt',
    'Server',
    'ServerMiddlewareActionTask',
    'ServerMiddlewareJobTask',
)

# A hack to make documentation generation work properly, otherwise there are errors (see `if TYPE_CHECKING`)
middleware.EnrichedActionRequest = EnrichedActionRequest  # type: ignore
middleware.EnrichedJobRequest = EnrichedJobRequest  # type: ignore

ServerMiddlewareJobTask = Callable[[EnrichedJobRequest], JobResponse]
ServerMiddlewareActionTask = Callable[[EnrichedActionRequest], ActionResponse]
_MT = TypeVar('_MT', ServerMiddlewareActionTask, ServerMiddlewareJobTask)
_RT = TypeVar('_RT', JobResponse, ActionResponse)


def _replace_fid(d, fid):  # type: (Dict[Any, Any], six.text_type) -> None
    for k, v in six.iteritems(d):
        if isinstance(v, six.text_type):
            d[k] = v.replace('{{fid}}', fid).replace('[[fid]]', fid).replace('%%fid%%', fid)
        elif isinstance(v, dict):
            _replace_fid(v, fid)


class HarakiriInterrupt(BaseException):
    """
    Raised internally to notify the server code about interrupts due to harakiri. You should never, ever, ever, ever
    catch this exception in your service code. As such, it inherits from `BaseException` so that even
    `except Exception:` won't catch it. However, `except:` will catch it, so, per standard Python coding standards,
    you should never use `except:` (or `except BaseException:`, for that matter).
    """


class Server(object):
    """
    The base class from which all PySOA service servers inherit, and contains the code that does all of the heavy
    lifting for receiving and handling requests, passing those requests off to the relevant actions, and sending
    the actions' responses back to the caller.

    Required attributes that all concrete subclasses must provide:

    - `service_name`: A (unicode) string name of the service.
    - `action_class_map`: An object supporting `__contains__` and `__getitem__` (typically a `dict`) whose keys are
      action names and whose values are callable objects that return a callable action when called (such as subclasses
      of `Action` which, when "called" [constructed], yield a callable object [instance of the subclass])
    """

    settings_class = ServerSettings  # type: Type[ServerSettings]
    request_class = EnrichedActionRequest  # type: Type[EnrichedActionRequest]
    client_class = Client  # type: Type[Client]

    use_django = False  # type: bool
    service_name = None  # type: Optional[six.text_type]
    action_class_map = {}  # type: Mapping[six.text_type, ActionType]

    # Allow a server to specify a custom introspection action
    introspection_action = None  # type: Optional[IntrospectionActionType]

    def __init__(self, settings, forked_process_id=None):
        # type: (ServerSettings, Optional[int]) -> None
        """
        :param settings: The settings object, which must be an instance of `ServerSettings` or one of its subclasses
        :param forked_process_id: If multiple processes are forked by the same parent process, this will be set to a
                                  unique, deterministic (incremental) ID which can be used in logging, the heartbeat
                                  file, etc. For example, if the `--fork` argument is used with the value 5 (creating
                                  five child processes), this argument will have the values 1, 2, 3, 4, and 5 across
                                  the five respective child processes.
        """
        # Check subclassing setup
        if not self.service_name:
            raise AttributeError('Server subclass must set service_name')

        # Store settings and tweak if necessary based on the forked process ID
        self.settings = settings
        if self.settings['metrics'].get('kwargs', {}).get('config', {}).get('publishers', {}):
            # Check if the metrics publisher config needs the FID anywhere and, if it does, replace it with the FID
            fid = 'main' if forked_process_id is None else six.text_type(forked_process_id)
            for publisher in self.settings['metrics']['kwargs']['config']['publishers']:
                if self.settings['metrics']['kwargs']['config']['version'] == 1:
                    _replace_fid(publisher, fid)
                elif publisher.get('kwargs', {}):
                    _replace_fid(publisher['kwargs'], fid)

        # Create the metrics recorder and transport
        self.metrics = self.settings['metrics']['object'](
            **self.settings['metrics'].get('kwargs', {})
        )  # type: MetricsRecorder
        self.transport = self.settings['transport']['object'](
            self.service_name,
            self.metrics,
            forked_process_id or 1,  # If no forking, there's only 1 instance
            **self.settings['transport'].get('kwargs', {})
        )  # type: ServerTransport

        self._async_event_loop_thread = None  # type: Optional[AsyncEventLoopThread]
        if AsyncEventLoopThread:
            self._async_event_loop_thread = AsyncEventLoopThread([
                m['object'](**m.get('kwargs', {}))
                for m in self.settings['coroutine_middleware']
            ])

        # Set initial state
        self.shutting_down = False
        self._shutdown_lock = threading.Lock()
        self._last_signal = 0
        self._last_signal_received = 0.0

        # Instantiate middleware
        self._middleware = [
            m['object'](**m.get('kwargs', {}))
            for m in self.settings['middleware']
        ]  # type: List[middleware.ServerMiddleware]
        self._middleware_job_wrapper = self.make_middleware_stack([m.job for m in self._middleware], self.execute_job)

        # Set up logger
        # noinspection PyTypeChecker
        self.logger = logging.getLogger('pysoa.server')
        # noinspection PyTypeChecker
        self.job_logger = logging.getLogger('pysoa.server.job')

        # Set these as the integer equivalents of the level names
        self.request_log_success_level = logging.getLevelName(self.settings['request_log_success_level'])  # type: int
        self.request_log_error_level = logging.getLevelName(self.settings['request_log_error_level'])  # type: int

        class DictWrapper(RecursivelyCensoredDictWrapper):
            SENSITIVE_FIELDS = frozenset(
                RecursivelyCensoredDictWrapper.SENSITIVE_FIELDS | settings['extra_fields_to_redact'],
            )
        self.logging_dict_wrapper_class = DictWrapper  # type: Type[RecursivelyCensoredDictWrapper]

        self._default_status_action_class = None  # type: Optional[ActionType]

        self._idle_timer = None  # type: Optional[Timer]

        self._heartbeat_file = None  # type: Optional[codecs.StreamReaderWriter]
        self._heartbeat_file_path = None  # type: Optional[six.text_type]
        self._heartbeat_file_last_update = 0.0
        self._forked_process_id = forked_process_id

        self._skip_django_database_cleanup = False

    def handle_next_request(self):  # type: () -> None
        """
        Retrieves the next request from the transport, or returns if it times out (no request has been made), and then
        processes that request, sends its response, and returns when done.
        """
        if not self._idle_timer:
            # This method may be called multiple times before receiving a request, so we only create and start a timer
            # if it's the first call or if the idle timer was stopped on the last call.
            self._idle_timer = self.metrics.timer('server.idle_time', resolution=TimerResolution.MICROSECONDS)
            self._idle_timer.start()

        # Get the next JobRequest
        try:
            request_id, meta, job_request = self.transport.receive_request_message()
            if request_id is None or meta is None or job_request is None:
                self.logger.warning('Thought to be impossible, but the transport returned None')
                raise MessageReceiveTimeout()
        except MessageReceiveTimeout:
            # no new message, nothing to do
            self._idle_timer.stop()
            self.perform_idle_actions()
            self._set_busy_metrics(False)
            self._idle_timer.start()
            return

        # We are no longer idle, so stop the timer, reset for the next idle period, and indicate busy in the gauges
        self._idle_timer.stop()
        self._idle_timer = None
        self._set_busy_metrics(True)
        self.metrics.publish_all()

        try:
            PySOALogContextFilter.set_logging_request_context(request_id=request_id, **job_request.get('context', {}))
        except TypeError:
            # Non unicode keys in job_request['context'] will break keywording of a function call.
            # Try to recover by coercing the keys to unicode.
            PySOALogContextFilter.set_logging_request_context(
                request_id=request_id,
                **{six.text_type(k): v for k, v in six.iteritems(job_request['context'])}
            )

        request_for_logging = self.logging_dict_wrapper_class(job_request)
        self.job_logger.log(self.request_log_success_level, 'Job request: %s', request_for_logging)

        client_version = tuple(meta['client_version']) if 'client_version' in meta else (0, 40, 0)

        def attr_filter(attrib, _value):  # type: (attr.Attribute, Any) -> bool
            # We don't want older clients to blow up trying to re-attr de-attr'd objects that have unexpected attrs
            return (
                not attrib.metadata or
                'added_in_version' not in attrib.metadata or
                client_version >= attrib.metadata['added_in_version']
            )

        try:
            self.perform_pre_request_actions()

            # Process and run the Job
            job_response = self.process_job(job_request)

            # Prepare the JobResponse for sending by converting it to a message dict
            try:
                response_message = attr.asdict(job_response, dict_factory=UnicodeKeysDict, filter=attr_filter)
            except Exception as e:
                self.metrics.counter('server.error.response_conversion_failure').increment()
                job_response = self.handle_unhandled_exception(e, JobResponse, variables={'job_response': job_response})
                response_message = attr.asdict(job_response, dict_factory=UnicodeKeysDict, filter=attr_filter)

            response_for_logging = self.logging_dict_wrapper_class(response_message)

            # Send the response message
            try:
                if not job_request.get('control', {}).get('suppress_response', False):
                    self.transport.send_response_message(request_id, meta, response_message)
            except MessageTooLarge as e:
                self.metrics.counter('server.error.response_too_large').increment()
                job_response = self.handle_job_error_code(
                    ERROR_CODE_RESPONSE_TOO_LARGE,
                    'Could not send the response because it was too large',
                    request_for_logging,
                    response_for_logging,
                    extra={'serialized_length_in_bytes': e.message_size_in_bytes},
                )
                self.transport.send_response_message(
                    request_id,
                    meta,
                    attr.asdict(job_response, dict_factory=UnicodeKeysDict, filter=attr_filter),
                )
            except InvalidField:
                self.metrics.counter('server.error.response_not_serializable').increment()
                job_response = self.handle_job_error_code(
                    ERROR_CODE_RESPONSE_NOT_SERIALIZABLE,
                    'Could not send the response because it failed to serialize',
                    request_for_logging,
                    response_for_logging,
                )
                self.transport.send_response_message(
                    request_id,
                    meta,
                    attr.asdict(job_response, dict_factory=UnicodeKeysDict, filter=attr_filter),
                )
            finally:
                if job_response.errors or any(a.errors for a in job_response.actions):
                    if (
                        self.request_log_error_level > self.request_log_success_level and
                        self.job_logger.getEffectiveLevel() > self.request_log_success_level
                    ):
                        # When we originally logged the request, it may have been hidden because the effective logging
                        # level threshold was greater than the level at which we logged the request. So re-log the
                        # request at the error level, if set higher.
                        self.job_logger.log(self.request_log_error_level, 'Job request: %s', request_for_logging)
                    self.job_logger.log(self.request_log_error_level, 'Job response: %s', response_for_logging)
                else:
                    self.job_logger.log(self.request_log_success_level, 'Job response: %s', response_for_logging)
        finally:
            PySOALogContextFilter.clear_logging_request_context()
            self.perform_post_request_actions()
            self._set_busy_metrics(False)

    def make_client(self, context, extra_context=None, **kwargs):
        # type: (Context, Optional[Context], **Any) -> Client
        """
        Gets a `Client` that will propagate the passed `context` in order to to pass it down to middleware or Actions.
        The server code will call this method only with the `context` argument and no other arguments. Subclasses can
        override this method and replace its behavior completely or call `super` to pass `extra_context` data or
        keyword arguments that will be passed to the client. The supplied `context` argument will not be modified in
        any way (it will be copied); the same promise is not made for the `extra_context` argument.

        :param context: The context parameter, supplied by the server code when making a client
        :param extra_context: Extra context information supplied by subclasses as they see fit
        :param kwargs: Keyword arguments that will be passed as-is to the `Client` constructor

        :return: A `Client` configured with this server's `client_routing` settings and the supplied context, extra
                 context, and keyword arguments.
        """
        context = context.copy()
        if extra_context:
            context.update(extra_context)
        context['calling_service'] = self.service_name
        return self.client_class(self.settings['client_routing'], context=context, **kwargs)

    # noinspection PyShadowingNames
    @staticmethod
    def make_middleware_stack(middleware, base):  # type: (List[Callable[[_MT], _MT]], _MT) -> _MT
        """
        Given a list of in-order middleware callable objects `middleware` and a base function `base`, chains them
        together so each middleware is fed the function below, and returns the top level ready to call.

        :param middleware: The middleware stack
        :param base: The base callable that the lowest-order middleware wraps

        :return: The topmost middleware, which calls the next middleware ... which calls the lowest-order middleware,
                 which calls the `base` callable.
        """
        for ware in reversed(middleware):
            base = ware(base)
        return base

    def process_job(self, job_request):  # type: (Dict[six.text_type, Any]) -> JobResponse
        """
        Validate, execute, and run the job request, wrapping it with any applicable job middleware.

        :param job_request: The job request dict

        :return: A `JobResponse` object
        """

        try:
            # Validate JobRequest message
            validation_errors = [
                Error(
                    code=error.code,
                    message=error.message,
                    field=error.pointer,
                    is_caller_error=False,  # because this only happens if the client library code is buggy
                )
                for error in (JobRequestSchema.errors(job_request) or [])
            ]
            if validation_errors:
                raise JobError(errors=validation_errors, set_is_caller_error_to=None)

            # Add the client object in case a middleware or action wishes to use it
            job_request['client'] = self.make_client(job_request['context'])

            # Add the run_coroutine in case a middleware or action wishes to use it
            if self._async_event_loop_thread:
                job_request['run_coroutine'] = self._async_event_loop_thread.run_coroutine
            else:
                job_request['run_coroutine'] = None

            job_response = self._middleware_job_wrapper(EnrichedJobRequest(**job_request))

            if 'correlation_id' in job_request['context']:
                job_response.context['correlation_id'] = job_request['context']['correlation_id']
        except HarakiriInterrupt:
            self.metrics.counter('server.error.harakiri', harakiri_level='job')
            job_response = JobResponse(
                errors=[Error(
                    code=ERROR_CODE_JOB_TIMEOUT,
                    message='The service job ran for too long and had to be interrupted (probably a middleware issue).',
                    is_caller_error=False,
                )],
            )
        except JobError as e:
            self.metrics.counter('server.error.job_error').increment()
            job_response = JobResponse(errors=e.errors)
        except Exception as e:
            # Send a job error response if no middleware caught this.
            self.metrics.counter('server.error.unhandled_error').increment()
            return self.handle_unhandled_exception(e, JobResponse)

        return job_response

    def handle_unhandled_exception(self, exception, response_type, variables=None, **kwargs):
        # type: (Exception, Type[_RT], Optional[Dict[six.text_type, Any]], **Any) -> _RT
        """
        Makes and returns a last-ditch error response based on an unknown, unexpected error.

        :param exception: The exception that happened.
        :param response_type: The response type (:class:`JobResponse` or :class:`ActionResponse`) that should be
                              created.
        :param variables: An optional dictionary of context-relevant variables to include in the error response.
        :param kwargs: Keyword arguments that will be passed to the response object created.

        :return: A `JobResponse` object or `ActionResponse` error based on the `response_type` argument.
        """
        # noinspection PyBroadException
        try:
            # Get the error and traceback if we can
            error_str, traceback_str = six.text_type(exception), traceback.format_exc()
        except Exception:
            self.metrics.counter('server.error.error_formatting_failure').increment()
            error_str, traceback_str = 'Error formatting error', traceback.format_exc()

        # Log what happened
        self.logger.exception(exception)
        if not isinstance(traceback_str, six.text_type):
            try:
                traceback_str = traceback_str.decode('utf-8')
            except UnicodeDecodeError:
                traceback_str = 'UnicodeDecodeError: Traceback could not be decoded'

        error_dict = {
            'code': ERROR_CODE_SERVER_ERROR,
            'message': 'Internal server error: %s' % error_str,
            'traceback': traceback_str,
            'is_caller_error': False,
        }  # type: Dict[six.text_type, Any]

        if variables is not None:
            # noinspection PyBroadException
            try:
                error_dict['variables'] = {key: repr(value) for key, value in variables.items()}
            except Exception:
                self.metrics.counter('server.error.variable_formatting_failure').increment()
                error_dict['variables'] = 'Error formatting variables'

        return response_type(errors=[Error(**error_dict)], **kwargs)

    def handle_job_error_code(
        self,
        code,  # type: six.text_type
        message,  # type: six.text_type
        request_for_logging,  # type: RecursivelyCensoredDictWrapper
        response_for_logging,  # type: RecursivelyCensoredDictWrapper
        extra=None,  # type: Optional[Dict[six.text_type, Any]]
    ):
        # type: (...) -> JobResponse
        """
        Makes and returns a last-ditch error response based on a known, expected (though unwanted) error while
        logging details about it.

        :param code: The error code.
        :param message: The error message.
        :param request_for_logging: The censor-wrapped request dictionary.
        :param response_for_logging: The censor-wrapped response dictionary.
        :param extra: Any extra items to add to the logged error.

        :return: A `JobResponse` object.
        """
        log_extra = {'data': {'request': request_for_logging, 'response': response_for_logging}}
        if extra:
            log_extra['data'].update(extra)

        self.logger.error(
            message,
            exc_info=True,
            extra=log_extra,
        )
        return JobResponse(errors=[Error(code=code, message=message, is_caller_error=False)])

    def execute_job(self, job_request):  # type: (EnrichedJobRequest) -> JobResponse
        """
        Processes and runs the action requests contained in the job and returns a `JobResponse`.

        :param job_request: The job request

        :return: A `JobResponse` object
        """
        # Run the Job's Actions
        harakiri = False
        job_response = JobResponse()
        job_switches = RequestSwitchSet(job_request.context['switches'])
        for i, simple_action_request in enumerate(job_request.actions):
            # noinspection PyArgumentList
            action_request = self.request_class(
                action=simple_action_request.action,
                body=simple_action_request.body,
                switches=job_switches,
                context=job_request.context,
                control=job_request.control,
                client=job_request.client,
                run_coroutine=job_request.run_coroutine,
            )
            action_request._server = self

            action_in_class_map = action_request.action in self.action_class_map
            if action_in_class_map or action_request.action in ('status', 'introspect'):
                # Get action to run
                if action_in_class_map:
                    action = self.action_class_map[action_request.action](self.settings)
                elif action_request.action == 'introspect':
                    # If set, use custom introspection action. Use default otherwise.
                    if self.introspection_action is not None:
                        action = self.introspection_action(self)
                    else:
                        from pysoa.server.action.introspection import IntrospectionAction
                        action = IntrospectionAction(server=self)
                else:
                    if not self._default_status_action_class:
                        from pysoa.server.action.status import make_default_status_action_class
                        self._default_status_action_class = make_default_status_action_class(self.__class__)
                    # noinspection PyTypeChecker
                    action = self._default_status_action_class(self.settings)

                # Wrap it in middleware
                wrapper = self.make_middleware_stack(
                    [m.action for m in self._middleware],
                    action,
                )
                # Execute the middleware stack
                try:
                    PySOALogContextFilter.set_logging_action_name(action_request.action)
                    action_response = wrapper(action_request)
                except HarakiriInterrupt:
                    self.metrics.counter('server.error.harakiri', harakiri_level='action')
                    action_response = ActionResponse(
                        action=action_request.action,
                        errors=[Error(
                            code=ERROR_CODE_ACTION_TIMEOUT,
                            message='The action "{}" ran for too long and had to be interrupted.'.format(
                                action_request.action,
                            ),
                            is_caller_error=False,
                        )],
                    )
                    harakiri = True
                except ActionError as e:
                    # An action error was thrown while running the action (or its middleware)
                    action_response = ActionResponse(
                        action=action_request.action,
                        errors=e.errors,
                    )
                except JobError:
                    # It's unusual for an action or action middleware to raise a JobError, so when it happens it's
                    # usually for testing purposes or a really important reason, so we re-raise instead of handling
                    # like we handle all other exceptions below.
                    raise
                except Exception as e:
                    # Send an action error response if no middleware caught this.
                    self.metrics.counter('server.error.unhandled_error').increment()
                    action_response = self.handle_unhandled_exception(e, ActionResponse, action=action_request.action)
                finally:
                    PySOALogContextFilter.clear_logging_action_name()
            else:
                # Error: Action not found.
                action_response = ActionResponse(
                    action=action_request.action,
                    errors=[Error(
                        code=ERROR_CODE_UNKNOWN,
                        message='The action "{}" was not found on this server.'.format(action_request.action),
                        field='action',
                        is_caller_error=True,
                    )],
                )

            job_response.actions.append(action_response)
            if harakiri or (
                action_response.errors and
                not job_request.control.get('continue_on_error', False)
            ):
                # Quit running Actions if harakiri occurred or an error occurred and continue_on_error is False
                break

        return job_response

    def handle_shutdown_signal(self, signal_number, _stack_frame):  # type: (int, FrameType) -> None
        """
        Handles the reception of a shutdown signal.
        """
        if not self._shutdown_lock.acquire(False):
            # Ctrl+C can result in 2 or even more signals coming in within nanoseconds of each other. We lock to
            # prevent handling them all. The duplicates can always be ignored, so this is a non-blocking acquire.
            return

        try:
            if self.shutting_down:
                if (
                    self._last_signal in (signal.SIGINT, signal.SIGTERM) and
                    self._last_signal != signal_number and
                    time.time() - self._last_signal_received < 1
                ):
                    self.logger.info('Ignoring duplicate shutdown signal received within one second of original signal')
                else:
                    self.logger.warning('Received double interrupt, forcing shutdown')
                    sys.exit(1)
            else:
                self.logger.warning('Received interrupt, initiating shutdown')
                self.shutting_down = True

            self._last_signal = signal_number
            self._last_signal_received = time.time()
        finally:
            self._shutdown_lock.release()

    def harakiri(self, signal_number, _stack_frame):  # type: (int, FrameType) -> None
        """
        Handles the reception of a timeout signal indicating that a request has been processing for too long, as
        defined by the harakiri settings. This method makes use of two "private" Python functions,
        `sys._current_frames` and `os._exit`, but both of these functions are publicly documented and supported.
        """
        if not self._shutdown_lock.acquire(False):
            # Ctrl+C can result in 2 or even more signals coming in within nanoseconds of each other. We lock to
            # prevent handling them all. The duplicates can always be ignored, so this is a non-blocking acquire.
            return

        threads = {
            cast(int, t.ident): {'name': t.name, 'traceback': ['Unknown']}
            for t in threading.enumerate()
        }  # type: Dict[int, Dict[six.text_type, Any]]
        # noinspection PyProtectedMember
        for thread_id, frame in sys._current_frames().items():
            stack = []
            for f in traceback.format_stack(frame):
                stack.extend(f.rstrip().split('\n'))
            if 'for f in traceback.format_stack(frame):' in stack[-1] and 'in harakiri' in stack[-2]:
                # We don't need the stack data from this code right here at the end of the stack; it's just confusing.
                stack = stack[:-2]
            threads.setdefault(thread_id, {'name': thread_id})['traceback'] = stack

        extra = {'data': {'thread_status': {
            t['name']: [line.rstrip() for line in t['traceback']] for t in threads.values()
        }}}
        details = 'Current thread status at harakiri trigger:\n{}'.format('\n'.join((
            'Thread {}:\n{}'.format(t['name'], '\n'.join(t['traceback'])) for t in threads.values()
        )))

        try:
            self._last_signal = signal_number
            self._last_signal_received = time.time()

            if self.shutting_down:
                self.logger.error(
                    'Graceful shutdown failed {} seconds after harakiri. Exiting now!'.format(
                        self.settings['harakiri']['shutdown_grace']
                    ),
                    extra=extra,
                )
                self.logger.info(details)

                try:
                    self.metrics.counter('server.error.harakiri', harakiri_level='emergency')
                    self.metrics.publish_all()
                finally:
                    # We tried shutting down gracefully, but it didn't work. This probably means that we are CPU bound
                    # in lower-level C code that can't be easily interrupted. Because of this, we forcefully terminate
                    # the server with prejudice. But first, we do our best to let things finish cleanly, if possible.
                    # noinspection PyProtectedMember
                    try:
                        exit_func = getattr(atexit, '_run_exitfuncs', None)
                        if exit_func:
                            thread = threading.Thread(target=exit_func)
                            thread.start()
                            thread.join(5.0)  # don't let cleanup tasks take more than five seconds
                        else:
                            # we have no way to run exit functions, so at least give I/O two seconds to flush
                            time.sleep(2.0)
                    finally:
                        # noinspection PyProtectedMember
                        os._exit(1)
            else:
                self.logger.warning(
                    'No activity for {} seconds, triggering harakiri with grace period of {} seconds'.format(
                        self.settings['harakiri']['timeout'],
                        self.settings['harakiri']['shutdown_grace'],
                    ),
                    extra=extra,
                )
                self.logger.info(details)

                # We re-set the alarm so that if the graceful shutdown we're attempting here doesn't work, harakiri
                # will be triggered again to force a non-graceful shutdown.
                signal.alarm(self.settings['harakiri']['shutdown_grace'])

                # Just setting the shutting_down flag isn't enough, because, if harakiri was triggered, we're probably
                # CPU or I/O bound in some way that won't return any time soon. So we also raise HarakiriInterrupt to
                # interrupt the main thread and cause the service to shut down in an orderly fashion.
                self.shutting_down = True
                raise HarakiriInterrupt()
        finally:
            self._shutdown_lock.release()

    def setup(self):  # type: () -> None
        """
        Runs just before the server starts, if you need to do one-time loads or cache warming. Call super().setup() if
        you override. See the documentation for `Server.main` for full details on the chain of `Server` method calls.
        """

    def teardown(self):  # type: () -> None
        """
        Runs just before the server shuts down, if you need to do any kind of clean up (like updating a metrics gauge,
        etc.). Call super().teardown() if you override. See the documentation for `Server.main` for full details on the
        chain of `Server` method calls.
        """

    def _close_old_django_connections(self):  # type: () -> None
        if self.use_django and not self._skip_django_database_cleanup:
            django_close_old_database_connections()

    def _close_django_caches(self, shutdown=False):  # type: (bool) -> None
        if self.use_django and django_caches:
            if shutdown:
                self.logger.info('Closing all Django caches')

            for cache in django_caches.all():
                cache.close(for_shutdown=shutdown)

    def _create_heartbeat_file(self):  # type: () -> None
        if self.settings['heartbeat_file']:
            heartbeat_file_path = self.settings['heartbeat_file'].replace('{{pid}}', six.text_type(os.getpid()))
            if '{{fid}}' in heartbeat_file_path and self._forked_process_id is not None:
                heartbeat_file_path = heartbeat_file_path.replace('{{fid}}', six.text_type(self._forked_process_id))

            self.logger.info('Creating heartbeat file {}'.format(heartbeat_file_path))

            file_path = os.path.abspath(heartbeat_file_path)
            self._heartbeat_file_path = file_path
            self._heartbeat_file = codecs.open(
                filename=file_path,
                mode='wb',
                encoding='utf-8',
            )

            self._update_heartbeat_file()

    def _delete_heartbeat_file(self):  # type: () -> None
        if self._heartbeat_file:
            self.logger.info('Closing and removing heartbeat file')

            # noinspection PyBroadException
            try:
                self._heartbeat_file.close()
            except Exception:
                self.logger.warning('Error while closing heartbeat file', exc_info=True)
            finally:
                # noinspection PyBroadException
                try:
                    if self._heartbeat_file_path:
                        os.remove(self._heartbeat_file_path)
                except Exception:
                    self.logger.warning('Error while removing heartbeat file', exc_info=True)

    def _update_heartbeat_file(self):  # type: () -> None
        if self._heartbeat_file and time.time() - self._heartbeat_file_last_update > 2.5:
            # Only update the heartbeat file if one is configured and it has been at least 2.5 seconds since the last
            # update. This prevents us from dragging down service performance by constantly updating the file system.
            self._heartbeat_file.seek(0)
            self._heartbeat_file.write(six.text_type(time.time()))
            self._heartbeat_file.flush()
            self._heartbeat_file_last_update = time.time()

    def perform_pre_request_actions(self):  # type: () -> None
        """
        Runs just before the server accepts a new request. Call super().perform_pre_request_actions() if you override.
        Be sure your purpose for overriding isn't better met with middleware. See the documentation for `Server.main`
        for full details on the chain of `Server` method calls.
        """
        self.metrics.publish_all()

        if self.use_django:
            django_reset_database_queries()

        self._close_old_django_connections()

    def perform_post_request_actions(self):  # type: () -> None
        """
        Runs just after the server processes a request. Call super().perform_post_request_actions() if you override. Be
        sure your purpose for overriding isn't better met with middleware. See the documentation for `Server.main` for
        full details on the chain of `Server` method calls.
        """
        self._close_old_django_connections()

        self._close_django_caches()

        self._update_heartbeat_file()

    def perform_idle_actions(self):  # type: () -> None
        """
        Runs periodically when the server is idle, if it has been too long since it last received a request. Call
        super().perform_idle_actions() if you override. See the documentation for `Server.main` for full details on the
        chain of `Server` method calls.
        """
        self._close_old_django_connections()

        self._update_heartbeat_file()

    def _set_busy_metrics(self, busy, running=True):  # type: (bool, bool) -> None
        self.metrics.gauge('server.worker.running').set(1 if running else 0)
        self.metrics.gauge('server.worker.busy').set(1 if busy else 0)

    def run(self):  # type: () -> None
        """
        Starts the server run loop and returns after the server shuts down due to a shutdown-request, Harakiri signal,
        or unhandled exception. See the documentation for `Server.main` for full details on the chain of `Server`
        method calls.
        """

        self.logger.info(
            'Service "{service}" server starting up, pysoa version {pysoa}, listening on transport {transport}.'.format(
                service=self.service_name,
                pysoa=pysoa.version.__version__,
                transport=self.transport,
            )
        )

        self.setup()
        self.metrics.counter('server.worker.startup').increment()
        self._set_busy_metrics(False)
        self.metrics.publish_all()

        if self._async_event_loop_thread:
            self._async_event_loop_thread.start()

        self._create_heartbeat_file()

        signal.signal(signal.SIGINT, self.handle_shutdown_signal)
        signal.signal(signal.SIGTERM, self.handle_shutdown_signal)
        signal.signal(signal.SIGALRM, self.harakiri)

        transient_failures = 0

        # noinspection PyBroadException
        try:
            while not self.shutting_down:
                # reset harakiri timeout
                signal.alarm(self.settings['harakiri']['timeout'])

                # Get, process, and execute the next JobRequest
                try:
                    self.handle_next_request()
                    if transient_failures > 0:
                        transient_failures -= 1
                except TransientPySOATransportError:
                    if transient_failures > 5:
                        self.logger.exception('Too many errors receiving message from transport; shutting down!')
                        break

                    # This sleeps using an exponential back-off period in the hopes that the problem will recover
                    sleep = (2 ** transient_failures + random.random()) / 4.0
                    self.logger.info(
                        'Transient error receiving message from transport, sleeping {} seconds and continuing.'.format(
                            sleep,
                        ),
                    )
                    time.sleep(sleep)
                    transient_failures += 1
                finally:
                    self.metrics.publish_all()
        except HarakiriInterrupt:
            self.metrics.counter('server.error.harakiri', harakiri_level='server')
            self.logger.error('Harakiri interrupt occurred outside of action or job handling')
        except Exception:
            self.metrics.counter('server.error.unknown').increment()
            self.logger.exception('Unhandled server error; shutting down')
        finally:
            self.teardown()
            self.metrics.counter('server.worker.shutdown').increment()
            self._set_busy_metrics(False, False)
            self.metrics.publish_all()
            self.logger.info('Server shutting down')
            if self._async_event_loop_thread:
                self._async_event_loop_thread.join()
            self._close_django_caches(shutdown=True)
            self._delete_heartbeat_file()
            self.logger.info('Server shutdown complete')

    @classmethod
    def pre_fork(cls):  # type: () -> None
        """
        Called only if the --fork argument is used to pre-fork multiple worker processes. In this case, it is called
        by the parent process immediately after signal handlers are set and immediately before the worker sub-processes
        are spawned. It is never called again in the life span of the parent process, even if a worker process crashes
        and gets re-spawned.
        """

    # noinspection PyUnusedLocal
    @classmethod
    def initialize(cls, settings):  # type: (ServerSettings) -> Type[Server]
        """
        Called just before the `Server` class is instantiated, and passed the settings dict. Can be used to perform
        settings manipulation, server class patching (such as for performance tracing operations), and more. Use with
        great care and caution. Overriding methods must call `super` and return `cls` or a new/modified `cls`, which
        will be used to instantiate the server. See the documentation for `Server.main` for full details on the chain
        of `Server` method calls.

        :return: The server class or a new/modified server class
        """
        return cls

    @classmethod
    def main(cls, forked_process_id=None):  # type: (Optional[int]) -> None
        """
        Command-line entry point for running a PySOA server. The chain of method calls is as follows::

            cls.main
              |
              -> cls.initialize => new_cls
              -> new_cls.__init__ => self
              -> self.run
                  |
                  -> self.setup
                  -> [async event loop started if Python 3.5+]
                  -> [heartbeat file created if configured]
                  -> loop: self.handle_next_request while not self.shutting_down
                            |
                            -> transport.receive_request_message
                            -> self.perform_idle_actions (if no request)
                            -> self.perform_pre_request_actions
                            -> self.process_job
                                |
                                -> middleware(self.execute_job)
                            -> transport.send_response_message
                            -> self.perform_post_request_actions
                  -> self.teardown
                  -> [async event loop joined in Python 3.5+; this make take a few seconds to finish running tasks]
                  -> [Django resources cleaned up]
                  -> [heartbeat file deleted if configured]

        :param forked_process_id: If multiple processes are forked by the same parent process, this will be set to a
                                  unique, deterministic (incremental) ID which can be used in logging, the heartbeat
                                  file, etc. For example, if the `--fork` argument is used with the value 5 (creating
                                  five child processes), this argument will have the values 1, 2, 3, 4, and 5 across
                                  the five respective child processes.
        """
        parser = argparse.ArgumentParser(
            description='Server for the {} SOA service'.format(cls.service_name),
        )
        parser.add_argument(
            '-d', '--daemon',
            action='store_true',
            help='run the server process as a daemon',
        )
        if not cls.use_django:
            # If Django mode is turned on, we use the Django settings framework to get our settings, so the caller
            # needs to set DJANGO_SETTINGS_MODULE. Otherwise, the caller must pass in the -s/--settings argument.
            parser.add_argument(
                '-s', '--settings',
                help='The settings module to use',
                required=True,
            )
        cmd_options, _ = parser.parse_known_args(sys.argv[1:])

        # Load settings from the given file (or use Django and grab from its settings)
        if cls.use_django:
            # noinspection PyUnresolvedReferences
            if not django_settings:
                raise ImportError(
                    'Could not import Django. You must install Django if you enable Django support in your service.'
                )
            try:
                settings = cls.settings_class(django_settings.SOA_SERVER_SETTINGS)
            except AttributeError:
                raise ValueError('Cannot find `SOA_SERVER_SETTINGS` in the Django settings.')
        else:
            try:
                settings_module = importlib.import_module(cmd_options.settings)
            except ImportError as e:
                raise ValueError('Cannot import settings module `%s`: %s' % (cmd_options.settings, e))
            try:
                settings_dict = getattr(settings_module, 'SOA_SERVER_SETTINGS')
            except AttributeError:
                try:
                    settings_dict = getattr(settings_module, 'settings')
                except AttributeError:
                    raise ValueError(
                        "Cannot find `SOA_SERVER_SETTINGS` or `settings` variable in settings module `{}`.".format(
                            cmd_options.settings,
                        )
                    )
            settings = cls.settings_class(settings_dict)

        if not cls.service_name:
            raise AttributeError('Server subclass must set service_name')

        PySOALogContextFilter.set_service_name(cls.service_name)

        # Set up logging
        logging.config.dictConfig(settings['logging'])

        # Optionally daemonize
        if cmd_options.daemon:
            pid = os.fork()
            if pid > 0:
                print('PID={}'.format(pid))
                sys.exit()

        # Set up server and signal handling
        server = cls.initialize(settings)(settings, forked_process_id)  # type: Server

        # Start server event loop
        server.run()
