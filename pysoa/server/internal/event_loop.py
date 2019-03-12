import asyncio
import threading


class AsyncEventLoopThread(threading.Thread):
    def __init__(self):
        super().__init__()
        self.loop = asyncio.new_event_loop()
        self._done = threading.Event()

    def _loop_stop_callback(self):
        self.loop.stop()

    def run(self):
        self._done.clear()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_forever()
        finally:
            try:
                pending_tasks = asyncio.Task.all_tasks(self.loop)
                self.loop.run_until_complete(asyncio.gather(*pending_tasks))
            finally:
                self.loop.close()
                asyncio.set_event_loop(None)
                self._done.set()

    def join(self):
        if self.loop.is_running():
            self.loop.call_soon_threadsafe(self._loop_stop_callback)
        self._done.wait()

    def run_coroutine(self, coroutine):
        return asyncio.run_coroutine_threadsafe(coroutine, self.loop)
