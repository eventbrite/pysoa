from __future__ import (
    absolute_import,
    unicode_literals,
)

import sys
import threading
from typing import (
    Any,
    Generic,
    Optional,
    TypeVar,
    cast,
)

import six


try:
    import contextvars
except ImportError:
    contextvars = None  # type: ignore


__all__ = (
    'ContextVar',
    'set_running_loop',
)


# noinspection PyUnusedLocal
def set_running_loop(loop):  # noqa
    pass


if (3, 4) < sys.version_info < (3, 7):  # pragma: no cover
    # Some context is necessary here. ContextVars were added in Python 3.7, but we need them in Python 3.5+. The
    # contextvars PyPi library is an API-compatible backport, but it has two drawbacks: It uses thread locals under the
    # hood (not safe in asyncio contexts) and it doesn't copy the context when a new task is created (like Python 3.7
    # does). The aiocontextvars PyPi library patches the contextvars PyPi library to correct these deficiencies, but
    # even it is not complete, as it requires at least Python 3.5.3, and we must support Python 3.5.2 for Ubuntu 16.04.
    # So we do some extra patching here, then import aiocontextvars to load its patches, and finally do one more patch.
    import asyncio
    import asyncio.coroutines
    import asyncio.futures
    import concurrent.futures

    if not hasattr(asyncio, '_get_running_loop'):
        # Python 3.5.0-3.5.3
        # noinspection PyCompatibility
        import asyncio.events
        from threading import local as threading_local

        if not hasattr(asyncio.events, '_get_running_loop'):
            # Python 3.5.0-3.5.2
            class _RunningLoop(threading_local):
                _loop = None

            _running_loop = _RunningLoop()

            def _get_running_loop():
                return _running_loop._loop

            def set_running_loop(loop):  # noqa: F811
                _running_loop._loop = loop

            def _get_event_loop():
                current_loop = _get_running_loop()
                if current_loop is not None:
                    return current_loop
                return asyncio.events.get_event_loop_policy().get_event_loop()

            asyncio.events.get_event_loop = _get_event_loop
            asyncio.events._get_running_loop = _get_running_loop
            asyncio.events._set_running_loop = set_running_loop

        asyncio._get_running_loop = asyncio.events._get_running_loop
        asyncio._set_running_loop = asyncio.events._set_running_loop

    # noinspection PyUnresolvedReferences
    import aiocontextvars  # noqa

    def _run_coroutine_threadsafe(coro, loop):
        """
        Patch to create task in the same thread instead of in the callback. This ensures that contextvars get copied.
        Python 3.7 copies contextvars without this.
        """
        if not asyncio.coroutines.iscoroutine(coro):
            raise TypeError('A coroutine object is required')
        future = concurrent.futures.Future()  # type: concurrent.futures.Future

        # This is the only change to this function: Creating the task here, in the caller thread, instead of within
        # `callback`, which is executed in the loop's thread. This does not run the task; it just _creates_ it.
        task = asyncio.ensure_future(coro, loop=loop)

        def callback():
            try:
                # noinspection PyProtectedMember,PyUnresolvedReferences
                asyncio.futures._chain_future(task, future)  # type: ignore
            except Exception as exc:
                if future.set_running_or_notify_cancel():
                    future.set_exception(exc)
                raise

        loop.call_soon_threadsafe(callback)
        return future

    asyncio.run_coroutine_threadsafe = _run_coroutine_threadsafe


_NO_DEFAULT = object()


VT = TypeVar('VT')


class ContextVar(Generic[VT]):
    """
    ContextVars are backwards-compatible with thread locals; that is, you can drop-in replace a thread local with a
    context variable and the synchronous behavior will remain identical, while the new, asynchronous behavior will work
    with asynchronous code.

    However, ContextVars exist natively only in Python 3.7+, and the PyPi backport is available only for Python 3.5-3.6.
    This enables service code to use one API (this class) to access ContextVar when available and thread locals
    otherwise.
    """
    def __init__(self, name, default=cast(VT, _NO_DEFAULT)):  # type: (six.text_type, VT) -> None
        self.name = name
        self._has_default = default is not _NO_DEFAULT
        self._default = default

        self._cv_variable = None  # type: Optional[contextvars.ContextVar[VT]]
        self._tl_variable = None  # type: Optional[threading.local]
        if contextvars:
            if self._has_default:
                self._cv_variable = contextvars.ContextVar(name, default=default)
            else:
                self._cv_variable = contextvars.ContextVar(name)
        elif threading:
            self._tl_variable = threading.local()
        # else is not possible

    def set(self, value):  # type: (VT) -> Token
        if self._cv_variable is not None:
            token = self._cv_variable.set(value)
            return _ContextVarToken(self, token)
        elif self._tl_variable is not None:
            previous_value = getattr(self._tl_variable, 'value', _NO_DEFAULT)
            self._tl_variable.value = value
            return _ThreadLocalToken(self, previous_value)
        else:
            raise TypeError('This context var has been internally messed with and is no longer valid.')

    def reset(self, token):  # type: (Token) -> None
        if token.context_var is not self:
            raise ValueError('Token was created by a different ContextVar')
        if self._cv_variable is not None:
            if not isinstance(token, _ContextVarToken):
                raise TypeError('Unexpected `{}` expecting `_ContextVarToken`'.format(token.__class__.__name__))
            self._cv_variable.reset(token.token)
        elif self._tl_variable is not None:
            if not isinstance(token, _ThreadLocalToken):
                raise TypeError('Unexpected `{}` expecting `_ThreadLocalToken`'.format(token.__class__.__name__))
            if token.previous_value is _NO_DEFAULT:
                delattr(self._tl_variable, 'value')
            else:
                self._tl_variable.value = token.previous_value
        else:
            raise TypeError('This context var has been internally messed with and is no longer valid.')

    def get(self, default=cast(VT, _NO_DEFAULT)):  # type: (VT) -> VT
        has_default = default is not _NO_DEFAULT

        if self._cv_variable is not None:
            return self._cv_variable.get(default) if has_default else self._cv_variable.get()

        if self._tl_variable is None:
            raise TypeError('This context var has been internally messed with and is no longer valid.')

        if has_default or self._has_default:
            return cast(VT, getattr(self._tl_variable, 'value', default if has_default else self._default))

        try:
            return cast(VT, self._tl_variable.value)
        except AttributeError:
            raise LookupError(self)

    def __repr__(self):  # type: () -> six.text_type
        r = "<ContextVar name='{}'".format(self.name)
        if self._default is not _NO_DEFAULT:
            r += ' default={!r}'.format(self._default)
        return r + ' at {:0x}>'.format(id(self))


class Token(object):
    def __init__(self, context_var):  # type: (ContextVar) -> None
        self.context_var = context_var


class _ContextVarToken(Token):
    def __init__(self, context_var, token):  # type: (ContextVar, contextvars.Token) -> None
        super(_ContextVarToken, self).__init__(context_var)
        self.token = token


class _ThreadLocalToken(Token):
    def __init__(self, context_var, previous_value):  # type: (ContextVar, Any) -> None
        super(_ThreadLocalToken, self).__init__(context_var)
        self.previous_value = previous_value
