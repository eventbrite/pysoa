
class Client(object):

    def __init__(self, service_name, transport, serializer):
        self.service_name = service_name
        self.transport = transport
        self.serializer = serializer

    def send_request(self, message_dict):
        """
        Serialize and send a request message, and return a request ID.

        returns: int
        raises: ConnectionError, InvalidField, MessageSendError, MessageSendTimeout,
            MessageTooLarge
        """
        message = self.serializer.dict_to_blob(message_dict)
        return self.transport.send_request_message(message)

    def get_all_responses(self):
        """
        Receive all available responses from the trasnport as a generator.

        yields: (int, dict)
        raises: ConnectionError, MessageReceiveError, MessageReceiveTimeout, InvalidMessage,
            StopIteration
        """
        while True:
            request_id, message = self.transport.receive_response_message()
            if message is None:
                break
            else:
                yield request_id, self.serializer.blob_to_dict(message)
