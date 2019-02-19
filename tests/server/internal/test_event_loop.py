import asyncio
import threading
import unittest

from pysoa.server.internal.event_loop import AsyncEventLoopThread


class AsyncEventLoopThreadTests(unittest.TestCase):
    def setUp(self):
        super(AsyncEventLoopThreadTests, self).setUp()
        self.thread = AsyncEventLoopThread()
        self.thread.start()

    def tearDown(self):
        self.thread.join()

    def test_loop_runs_in_another_thread(self):
        async def test_threads(thread):
            assert thread is not threading.current_thread()

        future = self.thread.run_coroutine(test_threads(threading.current_thread()))
        future.result()

    def test_loop_executes_pending_tasks_before_close(self):
        async def test_execs_pending():
            await asyncio.sleep(1)
            return 1

        def callback():
            assert future.done()
            assert future.result() == 1

        future = self.thread.run_coroutine(test_execs_pending())
        future.add_done_callback(callback)

    def test_join_stops_and_closes_loop(self):
        self.thread.join()
        assert not self.thread.loop.is_running()
        assert self.thread.loop.is_closed()
