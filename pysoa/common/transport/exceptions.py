from __future__ import (
    absolute_import,
    unicode_literals,
)


class MessageTooLarge(Exception):
    def __init__(self, message_size_in_bytes, *args):
        self.message_size_in_bytes = message_size_in_bytes
        super(MessageTooLarge, self).__init__(*args)


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
