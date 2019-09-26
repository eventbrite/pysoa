from __future__ import (
    absolute_import,
    unicode_literals,
)

import sys
from typing import List

import six


# Skip event loop tests for Python versions less than 3.5
collect_ignore = []  # type: List[six.text_type]
if sys.version_info < (3, 5):
    collect_ignore.append('tests/unit/server/internal/test_event_loop.py')
    collect_ignore.append('tests/unit/common/test_compatibility_async.py')
