from __future__ import (
    absolute_import,
    unicode_literals,
)

import sys


# Skip event loop tests for Python versions less than 3.5
collect_ignore = []
if sys.version_info < (3, 5):
    collect_ignore.append('tests/unit/server/internal/test_event_loop.py')
    collect_ignore.append('tests/unit/common/test_compatibility_async.py')
