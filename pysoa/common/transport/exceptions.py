
class MessageTooLarge(Exception):
    pass


class MessageReceiveTimeout(Exception):
    pass


class MessageSendTimeout(Exception):
    pass


class MessageReceiveError(Exception):
    pass


class MessageSendError(Exception):
    pass


class ConnectionError(Exception):
    pass


class InvalidMessageError(Exception):
    pass
