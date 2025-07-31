import contextvars
import threading
from typing import (
    Any,
    Generic,
    Optional,
    TypeVar,
    cast,
)
import asyncio

__all__ = (
    'ContextVar',
    'set_running_loop',
)

# In Python 3.7+, contextvars is always available
ContextVar = contextvars.ContextVar

_ContextVarToken = TypeVar('_ContextVarToken')
_ThreadLocalToken = TypeVar('_ThreadLocalToken')

def set_running_loop(loop: Optional[asyncio.AbstractEventLoop]) -> None:
    asyncio.set_event_loop(loop)
