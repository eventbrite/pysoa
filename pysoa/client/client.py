import uuid
import six
import attr

from pysoa.common.types import (
    JobRequest,
    JobResponse,
)


class Client(object):
    """The Client provides a simple interface for calling actions on Servers."""

    def __init__(self, service_name, transport, serializer, middleware=None):
        self.service_name = service_name
        self.transport = transport
        self.serializer = serializer
        self.middleware = middleware or []
        self.request_counter = 0

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

    @staticmethod
    def generate_correlation_id():
        return six.u(uuid.uuid1().hex)

    def make_control_header(
        self,
        switches=None,
        correlation_id=None,
        continue_on_error=False,
        control_extra=None,
    ):
        control = {
            'correlation_id': correlation_id or self.generate_correlation_id(),
            'switches': switches or [],
            'continue_on_error': continue_on_error,
        }
        if control_extra:
            control.update(control_extra)
        return control

    def make_middleware_stack(self, middleware, base):
        """
        Given a list of in-order middleware callables `middleware`
        and a base function `base`, chains them together so each middleware is
        fed the function below, and returns the top level ready to call.
        """
        for ware in reversed(middleware):
            base = ware(base)
        return base

    def call_actions(
        self,
        actions,
        context=None,
        switches=None,
        correlation_id=None,
        continue_on_error=False,
        control_extra=None,
    ):
        """
        Build and send a single job request with one or more actions.

        Returns a list of action responses, one for each action, or raises an exception if any action response is an
        error.

        The control_extra argument will be merged into the control header, overwriting any duplicate keys. It should be
        used to add implementation-specific control parameters to the request.

        Args:
            actions: list of ActionRequest
            switches: list
            context: dict
            correlation_id: string
            continue_on_error: bool
            control_extra: dict
        Returns:
            JobResponse
        """
        control = self.make_control_header(
            switches=switches,
            correlation_id=correlation_id,
            continue_on_error=continue_on_error,
            control_extra=control_extra,
        )
        request = JobRequest(actions=actions, control=control, context=context or {})
        request_id = self.send_request(request)
        # Dump everything from the generator. There should only be one response.
        responses = list(self.get_all_responses())
        response_id, response = responses[0]
        if response_id != request_id:
            raise Exception('Got response with ID {} for request with ID {}'.format(response_id, request_id))
        if response.errors:
            raise self.JobError(response.errors)
        error_actions = [action for action in response.actions if action.errors]
        if error_actions:
            raise self.CallActionError(error_actions)
        return response

    def call_action(
        self,
        action_name,
        body=None,
        **kwargs
    ):
        """
        Build and send a single job request with one action.

        Returns the action response or raises an exception if the action response is an error.

        Args:
            action_name: string
            body: dict
            switches: list of ints
            context: dict
            correlation_id: string
        Returns:
            ActionResponse
        """
        action_request = {'action': action_name}
        if body:
            action_request['body'] = body
        return self.call_actions(
            [action_request],
            **kwargs
        ).actions[0]

    def prepare_metadata(self):
        """
        Return a dict containing metadata that will be passed to
        Transport.send_request_message. Implementations should override this method to
        include any metadata required by their Transport classes.

        Returns: dict
        """
        return {'mime_type': self.serializer.mime_type}

    def _send_request(self, request_id, meta, job_request):
        if isinstance(job_request, JobRequest):
            job_request = attr.asdict(job_request)
        message = self.serializer.dict_to_blob(job_request)
        self.transport.send_request_message(request_id, meta, message)

    def send_request(self, job_request):
        """
        Serialize and send a request message, and return a request ID.

        Args:
            job_request: JobRequest or dict
        Returns:
            int
        Raises:
            ConnectionError, InvalidField, MessageSendError, MessageSendTimeout,
            MessageTooLarge
        """
        request_id = self.request_counter
        self.request_counter += 1
        meta = self.prepare_metadata()
        wrapper = self.make_middleware_stack(
            [m.request for m in self.middleware],
            self._send_request,
        )
        wrapper(request_id, meta, job_request)
        return request_id

    def _get_response(self):
        request_id, meta, message = self.transport.receive_response_message()
        if message is None:
            return (None, None)
        else:
            raw_response = self.serializer.blob_to_dict(message)
            job_response = JobResponse(**raw_response)
            return request_id, job_response

    def get_all_responses(self):
        """
        Receive all available responses from the trasnport as a generator.

        Yields:
            (int, JobResponse)
        Raises:
            ConnectionError, MessageReceiveError, MessageReceiveTimeout, InvalidMessage,
            StopIteration
        """
        wrapper = self.make_middleware_stack(
            [m.response for m in self.middleware],
            self._get_response,
        )
        while True:
            request_id, response = wrapper()
            if response is None:
                break
            yield request_id, response
