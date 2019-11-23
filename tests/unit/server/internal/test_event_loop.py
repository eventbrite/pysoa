"""isort:skip_file until https://github.com/timothycrosley/isort/issues/726 is fixed"""
from __future__ import (
    absolute_import,
    unicode_literals,
)

# noinspection PyCompatibility
import asyncio
# noinspection PyCompatibility
import contextvars
import threading
from typing import (
    Any,
    Dict,
    List,
)
import unittest

from conformity import fields
from conformity.error import ValidationError
import pytest

from pysoa.server.coroutine import (
    CoroutineMiddleware,
    DefaultCoroutineMiddleware,
)
from pysoa.server.internal.event_loop import (
    AsyncEventLoopThread,
    coroutine_middleware_config,
)
from pysoa.test.compatibility import mock


# noinspection PyCompatibility
class TestAsyncEventLoopThread(unittest.TestCase):
    def setUp(self):
        super(TestAsyncEventLoopThread, self).setUp()
        self.thread = AsyncEventLoopThread([])
        self.thread.start()

    def tearDown(self):
        self.thread.join()

    def test_loop_runs_in_another_thread(self):
        async def test_threads(thread):  # noqa E999
            assert thread is not threading.current_thread()

        future = self.thread.run_coroutine(test_threads(threading.current_thread()))
        future.result()

    def test_loop_executes_pending_tasks_before_close(self):
        async def test_execs_pending():  # noqa E999
            await asyncio.sleep(1)
            return 1

        def callback(_):
            assert future.done()
            assert future.result() == 1

        future = self.thread.run_coroutine(test_execs_pending())
        future.add_done_callback(callback)

    def test_join_stops_and_closes_loop(self):
        self.thread.join()
        assert not self.thread.loop.is_running()
        assert self.thread.loop.is_closed()


before_call_trace = []  # type: List[str]
create_call_trace = []  # type: List[str]
run_call_trace_pre = []  # type: List[str]
run_call_trace_post = []  # type: List[str]


@fields.ClassConfigurationSchema.provider(
    fields.Dictionary({'var_value': fields.Integer()}),
)
class SpecialCoroutineMiddleware(CoroutineMiddleware):
    def __init__(self, var_value: int):
        self.var_value = var_value

    def before_run_coroutine(self):
        before_call_trace.append('SpecialCoroutineMiddleware')

    def coroutine(self, coroutine):
        create_call_trace.append('SpecialCoroutineMiddleware')

        # noinspection PyCompatibility
        async def wrapper():
            var = contextvars.ContextVar('middleware_var')  # type: contextvars.ContextVar[int]
            var.set(self.var_value)

            run_call_trace_pre.append('SpecialCoroutineMiddleware')

            try:
                return await coroutine
            finally:
                run_call_trace_post.append('SpecialCoroutineMiddleware')

        return wrapper()


@fields.ClassConfigurationSchema.provider(fields.Dictionary({}))
class TracingCoroutineMiddleware(CoroutineMiddleware):
    def before_run_coroutine(self):
        before_call_trace.append('TracingCoroutineMiddleware')

    def coroutine(self, coroutine):
        create_call_trace.append('TracingCoroutineMiddleware')

        # noinspection PyCompatibility
        async def wrapper():
            run_call_trace_pre.append('TracingCoroutineMiddleware')

            try:
                return await coroutine
            finally:
                run_call_trace_post.append('TracingCoroutineMiddleware')

        return wrapper()


@fields.ClassConfigurationSchema.provider(fields.Dictionary({}))
class NotCoroutineMiddleware:
    pass


def test_coroutine_middleware_config():
    coroutine_middleware_config.contents.instantiate_from({
        'path': 'tests.unit.server.internal.test_event_loop:SpecialCoroutineMiddleware',
        'kwargs': {'var_value': 12},
    })

    with pytest.raises(ValidationError):
        coroutine_middleware_config.contents.instantiate_from({
            'path': 'tests.unit.server.internal.test_event_loop:SpecialCoroutineMiddleware',
        })

    with pytest.raises(ValidationError):
        coroutine_middleware_config.contents.instantiate_from({
            'path': 'tests.unit.server.internal.test_event_loop:SpecialCoroutineMiddleware',
            'kwargs': {},
        })

    with pytest.raises(ValidationError):
        coroutine_middleware_config.contents.instantiate_from({
            'path': 'tests.unit.server.internal.test_event_loop:SpecialCoroutineMiddleware',
            'kwargs': {'var_value': 'not_an_int'},
        })

    with pytest.raises(ValidationError):
        coroutine_middleware_config.contents.instantiate_from({
            'path': 'tests.unit.server.internal.test_event_loop:NotCoroutineMiddleware',
        })


# noinspection PyCompatibility
@pytest.mark.asyncio
async def test_coroutine_middleware():
    before_call_trace.clear()
    create_call_trace.clear()
    run_call_trace_pre.clear()
    run_call_trace_post.clear()

    var = contextvars.ContextVar('caller_var')  # type: contextvars.ContextVar[str]
    var.set('yes man')

    test_context = {
        'caller_var': None,
        'middleware_var': None
    }  # type: Dict[str, Any]

    # noinspection PyCompatibility
    async def coroutine():
        run_call_trace_pre.append('target')

        test_context['caller_var'] = var.get('default_cv')
        for context_var in contextvars.copy_context().keys():
            if context_var.name == 'middleware_var':
                test_context['middleware_var'] = context_var.get('default_mv')
        await asyncio.sleep(0.05)

        run_call_trace_post.append('target')

        return 'foo_coroutine_returned_this'

    thread = AsyncEventLoopThread([
        SpecialCoroutineMiddleware(42),
        TracingCoroutineMiddleware(),
    ])
    thread.start()

    future = thread.run_coroutine(coroutine())

    await asyncio.sleep(0.01)

    assert future.result() == 'foo_coroutine_returned_this'

    thread.join()

    assert before_call_trace == ['SpecialCoroutineMiddleware', 'TracingCoroutineMiddleware']
    assert create_call_trace == ['TracingCoroutineMiddleware', 'SpecialCoroutineMiddleware']
    assert run_call_trace_pre == ['SpecialCoroutineMiddleware', 'TracingCoroutineMiddleware', 'target']
    assert run_call_trace_post == ['target', 'TracingCoroutineMiddleware', 'SpecialCoroutineMiddleware']

    assert test_context['caller_var'] == 'yes man'
    assert test_context['middleware_var'] == 42


# noinspection PyCompatibility
@pytest.mark.asyncio
async def test_default_coroutine_middleware():
    class SpecialError(Exception):
        pass

    context = {'i': 0}

    # noinspection PyCompatibility
    async def coroutine():
        context['i'] += 1
        if context['i'] > 2:
            return 'bar_returned_by_coroutine'
        raise SpecialError(context['i'])

    thread = AsyncEventLoopThread([DefaultCoroutineMiddleware()])
    thread.start()

    with mock.patch('logging.Logger.exception') as mock_log_exception:
        future = thread.run_coroutine(coroutine())

        await asyncio.sleep(0.01)

        with pytest.raises(SpecialError) as error_context:
            future.result()

        assert error_context.value.args[0] == 1
        mock_log_exception.assert_called_once_with('Error occurred while awaiting coroutine in request.run_coroutine')
        mock_log_exception.reset_mock()

        future = thread.run_coroutine(coroutine())

        await asyncio.sleep(0.01)

        with pytest.raises(SpecialError) as error_context:
            future.result()

        assert error_context.value.args[0] == 2
        mock_log_exception.assert_called_once_with('Error occurred while awaiting coroutine in request.run_coroutine')
        mock_log_exception.reset_mock()

        future = thread.run_coroutine(coroutine())

        await asyncio.sleep(0.01)

        assert future.result() == 'bar_returned_by_coroutine'
        assert mock_log_exception.call_count == 0

        thread.join()
