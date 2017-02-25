class ClientMiddleware(object):

    def process_request_dict(self, request_dict):
        """
        Mutate the raw request dict before it is serialized and sent to a Server.

        request_dict: dict

        returns: None
        """
        pass

    def process_response_dict(self, response_dict):
        """
        Mutate the raw response dict after deserialization and before returning to the caller.

        response_dict: dict

        returns: None
        """
        pass
