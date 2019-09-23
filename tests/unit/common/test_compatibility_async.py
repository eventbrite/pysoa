from __future__ import (
    absolute_import,
    unicode_literals,
)

# noinspection PyCompatibility
import asyncio
import sys
import threading
import time
from typing import (
    Dict,
    Optional,
    Union,
)

import pytest

from pysoa.common.compatibility import (
    ContextVar,
    set_running_loop,
)


# noinspection PyCompatibility,PyUnresolvedReferences,PyProtectedMember
@pytest.mark.asyncio
async def test_task_creation_patching():  # noqa: E999
    var = ContextVar('test_task_creation_patching')  # type: ContextVar[Union[str, int]]
    var.set(12)

    test_context = {'var': None, 'new_var': None}  # type: Dict[str, Union[str, int, None]]

    # noinspection PyCompatibility
    async def coroutine():
        test_context['var'] = var.get('default')
        var.set(15)
        test_context['new_var'] = var.get('default')

    loop = asyncio.get_event_loop()
    task = loop.create_task(coroutine())

    assert var._cv_variable is not None

    if sys.version_info < (3, 7):
        assert var._cv_variable in task.context
        assert task.context[var._cv_variable] == 12

    await task

    assert test_context['var'] == 12
    assert test_context['new_var'] == 15
    assert var.get(12)


# noinspection PyCompatibility
class SimpleLoopThread(threading.Thread):
    def __init__(self):
        super().__init__()
        self.loop = asyncio.new_event_loop()

    def run(self):
        asyncio.set_event_loop(self.loop)
        set_running_loop(self.loop)
        try:
            self.loop.run_forever()
        finally:
            try:
                self.loop.run_until_complete(asyncio.gather(
                    *(getattr(asyncio, 'all_tasks', None) or getattr(asyncio.Task, 'all_tasks'))(self.loop)
                ))
            finally:
                self.loop.close()
                # noinspection PyTypeChecker
                asyncio.set_event_loop(None)  # type: ignore
                set_running_loop(None)

    def join(self, timeout=None):
        if self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)

        # noinspection PyCompatibility
        super().join(timeout)


# noinspection PyCompatibility
@pytest.mark.asyncio
async def test_multiple_coroutines_async():
    var1 = ContextVar('test_multiple_threads1')  # type: ContextVar[str]
    var2 = ContextVar('test_multiple_threads1')  # type: ContextVar[str]

    test_context = {
        'c1_called': False,
        'c1_complete': False,
        'c2_called': False,
        'c2_complete': False,
        'var1_thread1_start': None,
        'var2_thread1_start': None,
        'var1_thread1_mid': None,
        'var2_thread1_mid': None,
        'var1_thread1_end': None,
        'var2_thread1_end': None,
        'var1_thread2_start': None,
        'var2_thread2_start': None,
        'var1_thread2_mid': None,
        'var2_thread2_mid': None,
        'var1_thread2_end': None,
        'var2_thread2_end': None,
    }  # type: Dict[str, Union[bool, Optional[str]]]

    # noinspection PyCompatibility
    async def c1():
        test_context['c1_called'] = True
        test_context['var1_thread1_start'] = var1.get('default1_thread1')
        test_context['var2_thread1_start'] = var2.get('default2_thread1')

        var1.set('value1')
        var2.set('value2')

        await asyncio.sleep(0.1)

        test_context['var1_thread1_mid'] = var1.get()
        test_context['var2_thread1_mid'] = var2.get()

        await asyncio.sleep(0.3)

        test_context['var1_thread1_end'] = var1.get()
        test_context['var2_thread1_end'] = var2.get()
        test_context['c1_complete'] = True

    # noinspection PyCompatibility
    async def c2():
        test_context['c2_called'] = True
        test_context['var1_thread2_start'] = var1.get('default1_thread2')
        test_context['var2_thread2_start'] = var2.get('default2_thread2')

        var1.set('value3')
        var2.set('value4')

        await asyncio.sleep(0.3)

        test_context['var1_thread2_mid'] = var1.get()
        test_context['var2_thread2_mid'] = var2.get()

        await asyncio.sleep(0.1)

        test_context['var1_thread2_end'] = var1.get()
        test_context['var2_thread2_end'] = var2.get()
        test_context['c2_complete'] = True

    loop_thread = SimpleLoopThread()
    loop_thread.start()

    var1.set('super1')
    var2.set('super2')

    asyncio.run_coroutine_threadsafe(c1(), loop_thread.loop)
    asyncio.run_coroutine_threadsafe(c2(), loop_thread.loop)

    # It's _extremely_ unlikely that _both_ have already started and completed, and we want to ensure that our patched
    # run_coroutine_threadsafe hasn't run them both to completion before returning.
    assert (
        test_context['c1_called'] is False or
        test_context['c1_complete'] is False or
        test_context['c2_called'] is False or
        test_context['c2_complete'] is False
    )

    try:
        assert var1.get('default1_main') == 'super1'
        assert var2.get('default2_main') == 'super2'

        var1.set('value5')
        var2.set('value6')

        await asyncio.sleep(0.2)

        assert var1.get() == 'value5'
        assert var2.get() == 'value6'

        await asyncio.sleep(0.2)

        assert var1.get() == 'value5'
        assert var2.get() == 'value6'
    finally:
        loop_thread.join()

    assert test_context['c1_called'] is True
    assert test_context['c1_complete'] is True
    assert test_context['var1_thread1_start'] == 'super1'
    assert test_context['var2_thread1_start'] == 'super2'
    assert test_context['var1_thread1_mid'] == 'value1'
    assert test_context['var2_thread1_mid'] == 'value2'
    assert test_context['var1_thread1_end'] == 'value1'
    assert test_context['var2_thread1_end'] == 'value2'

    assert test_context['c2_called'] is True
    assert test_context['c2_complete'] is True
    assert test_context['var1_thread2_start'] == 'super1'
    assert test_context['var2_thread2_start'] == 'super2'
    assert test_context['var1_thread2_mid'] == 'value3'
    assert test_context['var2_thread2_mid'] == 'value4'
    assert test_context['var1_thread2_end'] == 'value3'
    assert test_context['var2_thread2_end'] == 'value4'


# noinspection PyCompatibility
def test_multiple_coroutines_sync():
    var1 = ContextVar('test_multiple_threads1')  # type: ContextVar[str]
    var2 = ContextVar('test_multiple_threads1')  # type: ContextVar[str]

    test_context = {
        'c1_called': False,
        'c1_complete': False,
        'c2_called': False,
        'c2_complete': False,
        'var1_thread1_start': None,
        'var2_thread1_start': None,
        'var1_thread1_mid': None,
        'var2_thread1_mid': None,
        'var1_thread1_end': None,
        'var2_thread1_end': None,
        'var1_thread2_start': None,
        'var2_thread2_start': None,
        'var1_thread2_mid': None,
        'var2_thread2_mid': None,
        'var1_thread2_end': None,
        'var2_thread2_end': None,
    }  # type: Dict[str, Union[bool, Optional[str]]]

    # noinspection PyCompatibility
    async def c1():
        test_context['c1_called'] = True
        test_context['var1_thread1_start'] = var1.get('default1_thread1')
        test_context['var2_thread1_start'] = var2.get('default2_thread1')

        var1.set('value1')
        var2.set('value2')

        await asyncio.sleep(0.1)

        test_context['var1_thread1_mid'] = var1.get()
        test_context['var2_thread1_mid'] = var2.get()

        await asyncio.sleep(0.3)

        test_context['var1_thread1_end'] = var1.get()
        test_context['var2_thread1_end'] = var2.get()
        test_context['c1_complete'] = True

    # noinspection PyCompatibility
    async def c2():
        test_context['c2_called'] = True
        test_context['var1_thread2_start'] = var1.get('default1_thread2')
        test_context['var2_thread2_start'] = var2.get('default2_thread2')

        var1.set('value3')
        var2.set('value4')

        await asyncio.sleep(0.3)

        test_context['var1_thread2_mid'] = var1.get()
        test_context['var2_thread2_mid'] = var2.get()

        await asyncio.sleep(0.1)

        test_context['var1_thread2_end'] = var1.get()
        test_context['var2_thread2_end'] = var2.get()
        test_context['c2_complete'] = True

    loop_thread = SimpleLoopThread()
    loop_thread.start()

    var1.set('super1')
    var2.set('super2')

    asyncio.run_coroutine_threadsafe(c1(), loop_thread.loop)
    asyncio.run_coroutine_threadsafe(c2(), loop_thread.loop)

    # It's _extremely_ unlikely that _both_ have already started and completed, and we want to ensure that our patched
    # run_coroutine_threadsafe hasn't run them both to completion before returning.
    assert (
        test_context['c1_called'] is False or
        test_context['c1_complete'] is False or
        test_context['c2_called'] is False or
        test_context['c2_complete'] is False
    )

    try:
        assert var1.get('default1_main') == 'super1'
        assert var2.get('default2_main') == 'super2'

        var1.set('value5')
        var2.set('value6')

        time.sleep(0.2)

        assert var1.get() == 'value5'
        assert var2.get() == 'value6'

        time.sleep(0.2)

        assert var1.get() == 'value5'
        assert var2.get() == 'value6'
    finally:
        loop_thread.join()

    assert test_context['c1_called'] is True
    assert test_context['c1_complete'] is True
    assert test_context['var1_thread1_start'] == 'super1'
    assert test_context['var2_thread1_start'] == 'super2'
    assert test_context['var1_thread1_mid'] == 'value1'
    assert test_context['var2_thread1_mid'] == 'value2'
    assert test_context['var1_thread1_end'] == 'value1'
    assert test_context['var2_thread1_end'] == 'value2'

    assert test_context['c2_called'] is True
    assert test_context['c2_complete'] is True
    assert test_context['var1_thread2_start'] == 'super1'
    assert test_context['var2_thread2_start'] == 'super2'
    assert test_context['var1_thread2_mid'] == 'value3'
    assert test_context['var2_thread2_mid'] == 'value4'
    assert test_context['var1_thread2_end'] == 'value3'
    assert test_context['var2_thread2_end'] == 'value4'
