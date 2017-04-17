class ServerMiddleware(object):
    """
    Base middleware class for server middleware. Not required, but gives you
    some helpful utility functions.

    Middleware must have two callables, `job` and `action`, that when called
    with the next level down, return a callable that takes a request and
    either returns a response or errors.
    """

    def job(self, process_job):
        # Remove ourselves from the stack
        return process_job

    def action(self, process_action):
        # Remove ourselves from the stack
        return process_action
