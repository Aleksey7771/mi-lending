"""Track and stop all running worker tasks."""
import asyncio
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator


class WorkerRegistry:
    def __init__(self) -> None:
        self._tasks: set[asyncio.Task[object]] = set()
        self._stopped = False

    @property
    def stopped(self) -> bool:
        return self._stopped

    @asynccontextmanager
    async def running(self) -> AsyncIterator[None]:
        if self._stopped:
            raise RuntimeError("Workers have been stopped")

        task = asyncio.current_task()
        if task is None:
            raise RuntimeError("Worker must run inside an asyncio task")

        self._tasks.add(task)
        try:
            if self._stopped:
                raise RuntimeError("Workers have been stopped")
            yield
        finally:
            self._tasks.discard(task)

    async def stop_all(self) -> None:
        self._stopped = True
        current = asyncio.current_task()
        tasks = [task for task in self._tasks if task is not current and not task.done()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


_worker_registry = WorkerRegistry()


async def stop_all() -> None:
    """Permanently stop active workers and reject new worker runs."""
    await _worker_registry.stop_all()
