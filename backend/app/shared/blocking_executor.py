import asyncio
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor


class BlockingExecutor:
    def __init__(self, *, executor_name: str, maximum_workers: int) -> None:
        self.thread_pool = ThreadPoolExecutor(max_workers=maximum_workers, thread_name_prefix=executor_name)

    async def run_blocking[ResultType](self, blocking_call: Callable[[], ResultType]) -> ResultType:
        return await asyncio.get_running_loop().run_in_executor(self.thread_pool, blocking_call)

    def close(self) -> None:
        self.thread_pool.shutdown(wait=True, cancel_futures=True)
