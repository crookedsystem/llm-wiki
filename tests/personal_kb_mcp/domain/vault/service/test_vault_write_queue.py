import asyncio
from collections.abc import Awaitable, Callable

from personal_kb_mcp.domain.vault.service.vault_write_queue import VaultWriteQueue


def test_write_queue는_동시_쓰기_요청을_하나씩_직렬화한다() -> None:
    async def exercise_queue() -> None:
        # Given: 동시에 실행될 여러 write operation과 공유 실행 상태가 있다.
        queue = VaultWriteQueue()
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

        # When: 20개의 operation을 동시에 queue에 제출한다.
        results = await asyncio.gather(*(queue.run(make_operation(index)) for index in range(20)))

        # Then: 모든 operation은 제출 순서대로 끝나고 동시에 2개 이상 활성화되지 않는다.
        assert list(results) == list(range(20))
        assert execution_order == list(range(20))
        assert max_active_count == 1

    asyncio.run(exercise_queue())
