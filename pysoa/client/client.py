"""
The Client provides a simple interface for calling actions on Servers.

The base Client class provides the core workflow for request sending and receiving.
Requests are passed and returned as dicts, and the format of the request depends on the
implementation.

The on_request and on_response methods provide hooks for any actions that need to be
taken after a successful request or response. These may include, for example, logging
all requests and responses or raising exceptions on error responses.
"""


class Client(object):

    def __init__(self, service_name, transport, serializer, middleware=None):
        self.service_name = service_name
        self.transport = transport
        self.serializer = serializer
        self.middleware = middleware or []
        self.request_counter = 0

    def prepare_metadata(self):
        """
        Return a dict containing metadata that will be passed to
        Transport.send_request_message. Implementations should override this method to
        include any metadata required by their Transport classes.

        Returns: dict
        """
        return {}

    def send_request(self, job_request):
        """
        Serialize and send a request message, and return a request ID.

        Args:
            job_request: JobRequest dict
        Returns:
            int
        Raises:
            ConnectionError, InvalidField, MessageSendError, MessageSendTimeout,
            MessageTooLarge
        """
        request_id = self.request_counter
        self.request_counter += 1
        meta = self.prepare_metadata()
        for middleware in self.middleware:
            middleware.process_job_request(request_id, meta, job_request)
        message = self.serializer.dict_to_blob(job_request)
        self.transport.send_request_message(request_id, meta, message)
        return request_id

    def get_all_responses(self):
        """
        Receive all available responses from the trasnport as a generator.

        Yields:
            (int, dict)
        Raises:
            ConnectionError, MessageReceiveError, MessageReceiveTimeout, InvalidMessage,
            StopIteration
        """
        while True:
            request_id, meta, message = self.transport.receive_response_message()
            if message is None:
                break
            else:
                job_response = self.serializer.blob_to_dict(message)
                for middleware in self.middleware:
                    middleware.process_job_response(request_id, meta, job_response)
                yield request_id, job_response
