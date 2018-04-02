class ServerMiddleware(object):
    """
    Base middleware class for server middleware. Not required, but provides some helpful stubbed methods and
    documentation that you should follow for creating your middleware classes. If you extend this class, you may
    override either one or both of the methods.

    Middleware must have two callable attributes, `job` and `action`, that, when called with the next level down,
    return a callable that takes the appropriate arguments and returns the appropriate value.
    """

    def job(self, process_job):
        """
        In sub-classes, used for creating a wrapper around `process_job`. In this simple implementation, just returns
        'process_job`.

        :param process_job: A callable that accepts a job request `dict` and returns a job response `dict`, or errors
        :type process_job: callable(dict): dict

        :return: A callable that accepts a job request `dict` and returns a job response `dict`, or errors, by calling
                 the provided `process_job` and possibly doing other things.
        :rtype: callable(dict): dict
        """

        # Remove ourselves from the stack
        return process_job

    def action(self, process_action):
        """
        In sub-classes, used for creating a wrapper around `process_action`. In this simple implementation, just
        returns `process_action`.

        :param process_action: A callable that accepts an `ActionRequest` object and returns an `ActionResponse`
                               object, or errors
        :type process_action: callable(ActionRequest): ActionResponse

        :return: A callable that accepts an `ActionRequest` object and returns an `ActionResponse` object, or errors,
                 by calling the provided `process_action` and possibly doing other things.
        :rtype: callable(ActionRequest): ActionResponse
        """

        # Remove ourselves from the stack
        return process_action
