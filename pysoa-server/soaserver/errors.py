class JobError(Exception):
    pass


class ActionError(Exception):
    def __init__(self, errors):
        self.errors = errors
