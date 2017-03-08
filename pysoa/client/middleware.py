class ClientMiddleware(object):

    def process_request_dict(self, request_dict, client):
        """
        Mutate the raw request dict before it is serialized and sent to a Server.

        request_dict: dict
        client: Client object

        returns: None
        """
        pass

    def process_response_dict(self, response_dict, client):
        """
        Mutate the raw response dict after deserialization and before returning to the caller.

        response_dict: dict
        client: Client object

        returns: None
        """
        pass
