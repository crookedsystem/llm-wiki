import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TypeVar

ResultT = TypeVar("ResultT")


@dataclass
class VaultWriteQueue:
    """Serialize vault mutations through one async lock."""

    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def run(self, operation: Callable[[], Awaitable[ResultT]]) -> ResultT:
        async with self._lock:
            return await operation()
