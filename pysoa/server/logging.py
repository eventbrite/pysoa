from __future__ import absolute_import, unicode_literals

import logging
import threading


class PySOALogContextFilter(logging.Filter):
    def __init__(self):
        super(PySOALogContextFilter, self).__init__('')

    def filter(self, record):
        context = self.get_logging_request_context()
        if context:
            record.correlation_id = context.get('correlation_id') or ''
            record.request_id = context.get('request_id') or ''
        else:
            record.correlation_id = ''
            record.request_id = ''
        return True

    _logging_context = threading.local()

    @classmethod
    def set_logging_request_context(cls, **context):
        if not getattr(cls._logging_context, 'context_stack', None):
            cls._logging_context.context_stack = []
        cls._logging_context.context_stack.append(context)

    @classmethod
    def clear_logging_request_context(cls):
        if getattr(cls._logging_context, 'context_stack', None):
            cls._logging_context.context_stack.pop()

    @classmethod
    def get_logging_request_context(cls):
        if getattr(cls._logging_context, 'context_stack', None):
            return cls._logging_context.context_stack[-1]
        return None
