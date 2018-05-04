class ClientMiddleware(object):
    """
    Base middleware class for client middleware. Not required, but provides some helpful stubbed methods and
    documentation that you should follow for creating your middleware classes. If you extend this class, you may
    override either one or both of the methods.

    Middleware must have two callable attributes, ``request`` and ``response``, that, when called with the next level
    down, return a callable that takes the appropriate arguments and returns the appropriate value.
    """

    def request(self, send_request):
        """
        In sub-classes, used for creating a wrapper around ``send_request``. In this simple implementation, just
        returns ``send_request``.

        :param send_request: A callable that accepts a request ID int, meta ``dict``, ``JobRequest`` object, and
                             message expiry int and returns nothing
        :type send_request: callable(int, dict, JobRequest, int): undefined

        :return: A callable that accepts a request ID int, meta ``dict``, ``JobRequest`` object, and message expiry int
                 and returns nothing.
        :rtype: callable(int, dict, JobRequest, int): undefined
        """

        # Remove ourselves from the stack
        return send_request

    def response(self, get_response):
        """
        In sub-classes, used for creating a wrapper around ``get_response``. In this simple implementation, just
        returns ``get_response``.

        :param get_response: A callable that accepts a timeout int and returns tuple of request ID int and
                             ``JobResponse`` object
        :type get_response: callable(int): tuple<int, JobResponse>

        :return: A callable that accepts a timeout int and returns tuple of request ID int and ``JobResponse`` object.
        :rtype: callable(int): tuple<int, JobResponse>
        """

        # Remove ourselves from the stack
        return get_response
