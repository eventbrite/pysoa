from __future__ import (
    absolute_import,
    unicode_literals,
)

from typing import (  # noqa: F401 TODO Python 3
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
)

from conformity import fields
import six  # noqa: F401 TODO Python 3

from pysoa.common.types import (  # noqa: F401 TODO Python 3
    ActionResponse,
    JobResponse,
)


if TYPE_CHECKING:
    # To prevent circular imports
    from pysoa.server.types import EnrichedActionRequest  # noqa: F401 TODO Python 3


__all__ = (
    'ServerMiddleware',
)


@fields.ClassConfigurationSchema.provider(fields.Dictionary(
    {},
    description='Most server middleware has no constructor arguments, but subclasses can override this schema',
))
class ServerMiddleware(object):
    """
    Base middleware class for server middleware. Not required, but provides some helpful stubbed methods and
    documentation that you should follow for creating your middleware classes. If you extend this class, you may
    override either one or both of the methods.

    Middleware must have two callable attributes, `job` and `action`, that, when called with the next level down,
    return a callable that takes the appropriate arguments and returns the appropriate value.
    """

    def job(
        self,
        process_job,  # type: Callable[[Dict[six.text_type, Any]], JobResponse]
    ):
        # type: (...) -> Callable[[Dict[six.text_type, Any]], JobResponse]
        """
        In sub-classes, used for creating a wrapper around `process_job`. In this simple implementation, just returns
        'process_job`.

        .. caution::
           `This bug <https://github.com/eventbrite/pysoa/issues/197>`_ details a flaw in this method. Unlike all other
           middleware tasks, which accept and return proper objects, this one accepts a dictionary and returns a proper
           object. This is inconsistent and will be fixed prior to the release of PySOA 1.0.0, at which point the
           callable argument and returned callable must accept a :class:`JobRequest` object instead of a job request
           `dict`. TODO: Change this.

        :param process_job: A callable that accepts a job request `dict` and returns a :class:`JobResponse` object, or
                            errors

        :return: A callable that accepts a job request `dict` and returns a a :class:`JobResponse` object, or errors,
                 by calling the provided `process_job` and possibly doing other things.
        """

        # Remove ourselves from the stack
        return process_job

    def action(
        self,
        process_action,  # type: Callable[[EnrichedActionRequest], ActionResponse]
    ):
        # type: (...) -> Callable[[EnrichedActionRequest], ActionResponse]
        """
        In sub-classes, used for creating a wrapper around `process_action`. In this simple implementation, just
        returns `process_action`.

        :param process_action: A callable that accepts an :class:`ActionRequest` object and returns an
                               :class:`ActionResponse` object, or errors

        :return: A callable that accepts an :class:`ActionRequest` object and returns an :class:`ActionResponse`
                 object, or errors, by calling the provided `process_action` and possibly doing other things.
        """

        # Remove ourselves from the stack
        return process_action
