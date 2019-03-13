import sys

# Skip event loop tests for Python versions less than 3.5
collect_ignore = []
if sys.version_info < (3, 5):
    collect_ignore.append('tests/server/internal/test_event_loop.py')
