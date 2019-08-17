# The __future__ imports are only here to satisfy isort; they are not needed.
from __future__ import (
    absolute_import,
    unicode_literals,
)

import logging

from conformity import fields

# noinspection PyUnresolvedReferences
import pysoa.common.compatibility  # noqa To make sure patching happens


try:
    from typing import Coroutine  # python 3.5.3+
except ImportError:
    # noinspection PyCompatibility
    from collections.abc import Coroutine  # python 3.5.1-2 (Ubuntu 16.04, unfortunately)


__all__ = (
    'Coroutine',
    'CoroutineMiddleware',
    'DefaultCoroutineMiddleware',
)


_logger = logging.getLogger(__name__)


class CoroutineMiddleware:
    def before_run_coroutine(self):
        """
        When `request.run_coroutine` is called, this method will be invoked, synchronously, in the calling context
        (e.g., the calling thread), to execute any logic necessary before handing the coroutine off to the async event
        loop.

        The advantage of implementing this method instead of or in addition to implementing `coroutine` is that, when
        multiple middleware are configured, this method will be called in the same order the middleware are configured,
        while `coroutine` will be called in the reverse order the middleware are configured (in order to create a
        coroutine call stack in the same order the middleware are configured).
        """

    def coroutine(self, coroutine: Coroutine) -> Coroutine:  # noqa: E999
        """
        Returns a coroutine (`async def ...`) that wraps the given coroutine. This wrapping coroutine can be used to
        execute code before and after the target coroutine. The wrapping pattern is identical to server and client
        middleware except that it deals with coroutines instead of callables.

        Example:

        .. code-block:: python

            class CustomCoroutineMiddleware:
                ...

                def coroutine(self, coroutine):
                    async def wrapper():
                        do_stuff_before_coroutine()

                        await coroutine

                        do_stuff_after_coroutine()

                    return wrapper()

        Note: When multiple middleware are configured, this method will be called in the reverse order the middleware
        are configured, in order to create a coroutine call stack in the same order the middleware are configured. For
        example, if `Middleware1` and `Middleware2` are configured in that order, `Middleware2.coroutine()` will be
        called before `Middleware1.coroutine()`, so that the coroutine call stack will be `middleware_wrapper_1` ->
        `middleware_wrapper_2` -> `coroutine`.

        :param coroutine: The target coroutine (or coroutine returned by the previous middleware)

        :return: The new, wrapping coroutine (or the unmodified coroutine argument, if no wrapping necessary).
        """
        return coroutine


@fields.ClassConfigurationSchema.provider(
    fields.Dictionary({}, description='The default coroutine middleware has no constructor arguments'),
)
class DefaultCoroutineMiddleware(CoroutineMiddleware):
    """
    Your server should have this middleware configured as the very first coroutine middleware. All of your custom
    coroutine middleware should be configured after this.
    """
    def coroutine(self, coroutine: Coroutine) -> Coroutine:
        # noinspection PyCompatibility
        async def handler():
            try:
                await coroutine
            except Exception:
                _logger.exception('Error occurred while awaiting coroutine in request.run_coroutine')

        return handler()
