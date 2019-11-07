from __future__ import (
    absolute_import,
    unicode_literals,
)

from typing import (
    Any,
    Callable,
    Dict,
    Optional,
    Tuple,
)

from conformity import fields
import six

from pysoa.common.types import (
    JobRequest,
    JobResponse,
)


__all__ = (
    'ClientMiddleware',
    'ClientRequestMiddlewareTask',
    'ClientResponseMiddlewareTask',
)


ClientRequestMiddlewareTask = Callable[[int, Dict[six.text_type, Any], JobRequest, Optional[int]], None]
ClientResponseMiddlewareTask = Callable[[Optional[int]], Tuple[Optional[int], Optional[JobResponse]]]


@fields.ClassConfigurationSchema.provider(fields.Dictionary(
    {},
    description='Most client middleware has no constructor arguments, but subclasses can override this schema',
))
class ClientMiddleware(object):
    """
    Base middleware class for client middleware. Not required, but provides some helpful stubbed methods and
    documentation that you should follow for creating your middleware classes. If you extend this class, you may
    override either one or both of the methods.

    Middleware must have two callable attributes, `request` and `response`, that, when called with the next level
    down, return a callable that takes the appropriate arguments and returns the appropriate value.
    """

    def request(self, send_request):  # type: (ClientRequestMiddlewareTask) -> ClientRequestMiddlewareTask
        """
        In sub-classes, used for creating a wrapper around `send_request`. In this simple implementation, just
        returns `send_request`.

        :param send_request: A callable that accepts a request ID int, meta `dict`,
                             :class:`pysoa.common.types.JobRequest` object, and message expiry int and returns nothing.

        :return: A callable that accepts a request ID int, meta `dict`, :class:`pysoa.common.types.JobRequest` object,
                 and message expiry int and returns nothing.
        """

        # Remove ourselves from the stack
        return send_request

    def response(self, get_response):  # type: (ClientResponseMiddlewareTask) -> ClientResponseMiddlewareTask
        """
        In sub-classes, used for creating a wrapper around `get_response`. In this simple implementation, just
        returns `get_response`.

        :param get_response: A callable that accepts a timeout int and returns tuple of request ID int and
                             :class:`pysoa.common.types.JobResponse` object.

        :return: A callable that accepts a timeout int and returns tuple of request ID int and
                 :class:`pysoa.common.types.JobResponse` object.
        """

        # Remove ourselves from the stack
        return get_response
