class JobError(Exception):
    def __init__(self, errors):
        self.errors = errors


class ActionError(Exception):
    def __init__(self, errors):
        self.errors = errors
