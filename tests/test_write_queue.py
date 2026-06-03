import asyncio
from collections.abc import Awaitable, Callable

from personal_kb_mcp.writes.queue import WriteQueue


def test_write_queue_serializes_concurrent_operations() -> None:
    async def exercise_queue() -> None:
        queue = WriteQueue()
        active_count = 0
        max_active_count = 0
        execution_order: list[int] = []

        async def operation(index: int) -> int:
            nonlocal active_count, max_active_count
            active_count += 1
            max_active_count = max(max_active_count, active_count)
            execution_order.append(index)
            await asyncio.sleep(0)
            active_count -= 1
            return index

        def make_operation(index: int) -> Callable[[], Awaitable[int]]:
            return lambda: operation(index)

        results = await asyncio.gather(*(queue.run(make_operation(index)) for index in range(20)))

        assert list(results) == list(range(20))
        assert execution_order == list(range(20))
        assert max_active_count == 1

    asyncio.run(exercise_queue())
