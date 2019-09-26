"""isort:skip_file"""
# noinspection PyCompatibility
import asyncio
# noinspection PyCompatibility
import concurrent.futures
import logging
import sys
import threading
from typing import (
    List,
    Optional,
)

from conformity import fields

from pysoa.common.compatibility import set_running_loop
from pysoa.server.coroutine import (
    Coroutine,
    CoroutineMiddleware,
)


__all__ = (
    'AsyncEventLoopThread',
    'coroutine_middleware_config',
)


if sys.version_info >= (3, 7):
    all_tasks = asyncio.all_tasks
else:
    all_tasks = asyncio.Task.all_tasks


class AsyncEventLoopThread(threading.Thread):
    def __init__(self, coroutine_middleware: List[CoroutineMiddleware]):  # noqa: E999
        # noinspection PyCompatibility
        super().__init__()
        self.loop = asyncio.new_event_loop()  # type: asyncio.AbstractEventLoop
        self._coroutine_middleware = coroutine_middleware  # type: List[CoroutineMiddleware]
        self._done = threading.Event()
        self._logger = logging.getLogger('pysoa.async')

    def _loop_stop_callback(self) -> None:
        self._logger.info('Stopping async event loop thread')
        self.loop.stop()

    def run(self) -> None:
        self._logger.info('Starting async event loop thread')
        self._done.clear()
        asyncio.set_event_loop(self.loop)
        set_running_loop(self.loop)
        try:
            self._logger.info('Async event loop thread available and running')
            self.loop.run_forever()
        finally:
            try:
                pending_tasks = all_tasks(self.loop)
                if pending_tasks:
                    self._logger.info('Completing uncompleted async tasks')
                self.loop.run_until_complete(asyncio.gather(*pending_tasks))
            finally:
                self._logger.info('Closing async event loop')
                self.loop.close()
                # noinspection PyTypeChecker
                asyncio.set_event_loop(None)  # type: ignore
                set_running_loop(None)
                self._done.set()

    def join(self, timeout: Optional[float] = None):
        if self.loop.is_running():
            self._logger.info('Scheduling async event loop thread shutdown')
            self.loop.call_soon_threadsafe(self._loop_stop_callback)
            self._done.wait()
        else:
            self._logger.warning('Async event loop is already not running!')

        # noinspection PyCompatibility
        super().join(timeout)

    def run_coroutine(self, coroutine: Coroutine) -> concurrent.futures.Future:
        for middleware_obj in self._coroutine_middleware:
            middleware_obj.before_run_coroutine()

        for middleware_obj in reversed(self._coroutine_middleware):
            coroutine = middleware_obj.coroutine(coroutine)

        return asyncio.run_coroutine_threadsafe(coroutine, self.loop)


coroutine_middleware_config = fields.List(
    fields.ClassConfigurationSchema(base_class=CoroutineMiddleware),
    description='The list of all `CoroutineMiddleware` classes that should be constructed and applied to '
                '`request.run_coroutine` calls processed by this server. By default, '
                '`pysoa.server.coroutine:DefaultCoroutineMiddleware` will be configured first. You can change and/or '
                'add to this, but we recommend that you always configure `DefaultCoroutineMiddleware` as the first '
                'middleware.',
)
coroutine_middleware_config.contents.initiate_cache_for('pysoa.server.coroutine:DefaultCoroutineMiddleware')
