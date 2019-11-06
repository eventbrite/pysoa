from __future__ import (
    absolute_import,
    unicode_literals,
)

from typing import (
    TYPE_CHECKING,
    Callable,
)

from conformity import fields

from pysoa.common.types import (
    ActionResponse,
    JobResponse,
)


if TYPE_CHECKING:
    # To prevent circular imports
    from pysoa.server.types import (
        EnrichedActionRequest,
        EnrichedJobRequest,
    )


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
        process_job,  # type: Callable[[EnrichedJobRequest], JobResponse]
    ):
        # type: (...) -> Callable[[EnrichedJobRequest], JobResponse]
        """
        In sub-classes, used for creating a wrapper around `process_job`. In this simple implementation, just returns
        'process_job`.

        :param process_job: A callable that accepts a :class:`pysoa.server.types.EnrichedJobRequest` and returns a
                            :class:`pysoa.common.types.JobResponse` object, or raises an exception.

        :return: A callable that accepts a :class:`pysoa.server.types.EnrichedJobRequest` and returns a
                 :class:`pysoa.common.types.JobResponse` object, or raises an exception, by calling the provided
                 `process_job` argument and possibly doing other things.
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

        :param process_action: A callable that accepts a :class:`pysoa.server.types.EnrichedActionRequest` object and
                               returns a :class:`pysoa.common.types.ActionResponse` object, or raises an exception.

        :return: A callable that accepts a :class:`pysoa.server.types.EnrichedActionRequest` object and returns a
                 :class:`pysoa.common.types.ActionResponse` object, or raises an exception, by calling the provided
                 `process_action` argument and possibly doing other things.
        """

        # Remove ourselves from the stack
        return process_action
