class ClientMiddleware(object):
    """Base middleware class for the Client."""

    def request(self, send_request):
        return send_request

    def response(self, get_response):
        return get_response
