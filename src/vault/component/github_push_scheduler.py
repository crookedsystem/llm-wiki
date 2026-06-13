import asyncio
import logging
import random
from collections.abc import Callable
from contextlib import suppress

from pydantic import PrivateAttr

from common.model import MutableModel
from vault.service.vault_git_push_service import VaultGitPushService

logger = logging.getLogger(__name__)
MIN_INTERVAL_SECONDS = 1800
MAX_INTERVAL_SECONDS = 3600


class GithubPushScheduler(MutableModel):
    push_service: VaultGitPushService
    random_interval: Callable[[int, int], float] = random.uniform

    _task: asyncio.Task[None] | None = PrivateAttr(default=None)

    def start(self) -> None:
        if self.is_running:
            return
        self._task = asyncio.create_task(self._run_forever())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        with suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    def next_interval_seconds(self) -> float:
        return self.random_interval(MIN_INTERVAL_SECONDS, MAX_INTERVAL_SECONDS)

    async def _run_forever(self) -> None:
        while True:
            await asyncio.sleep(self.next_interval_seconds())
            try:
                await self.push_service.push_vault()
            except Exception:
                logger.exception("Scheduled vault GitHub push failed")
