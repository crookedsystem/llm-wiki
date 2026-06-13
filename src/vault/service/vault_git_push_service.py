from collections.abc import Callable
from datetime import UTC, datetime

from common.model import FrozenModel
from vault.component.write_queue import VaultWriteQueue
from vault.infrastructure.repository.git_repository import GitRepository
from vault.service.result.git_push_result import GitPushResult


def _utc_now() -> datetime:
    return datetime.now(UTC)


class VaultGitPushService(FrozenModel):
    repository: GitRepository
    queue: VaultWriteQueue
    clock: Callable[[], datetime] = _utc_now

    async def push_vault(self) -> GitPushResult:
        async def operation() -> GitPushResult:
            return self._push_vault()

        return await self.queue.run(operation)

    def _push_vault(self) -> GitPushResult:
        commit_hash = self.repository.commit_all_changed(self._commit_message())
        push_outcome = self.repository.push()
        return GitPushResult(
            committed=commit_hash is not None,
            commit_hash=commit_hash,
            pushed=True,
            remote=push_outcome.remote,
            branch=push_outcome.branch,
            push_tool=push_outcome.push_tool,
            push_command=push_outcome.push_command,
        )

    def _commit_message(self) -> str:
        return f"{self.clock().astimezone(UTC).strftime('%Y-%m-%d %H:%M')} - vault sync"
