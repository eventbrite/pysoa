from __future__ import (
    absolute_import,
    unicode_literals,
)
from unittest import mock
from typing import Any, Optional

__all__ = ['mock']

# Backwards compatibility layer
def get_mock() -> Any:
    return mock
