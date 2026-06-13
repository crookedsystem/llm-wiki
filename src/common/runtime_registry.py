"""Process-local runtime registry for application dependencies."""

from pathlib import Path
from threading import Lock

from common.config import Settings
from common.model import FrozenModel
from vault.component.write_queue import VaultWriteQueue
from vault.entity.vault_path import VaultPaths
from vault.infrastructure.repository.git_repository import GitRepository
from vault.infrastructure.repository.vault_note_repository import (
    VaultNoteRepository,
)
from vault.service.vault_git_push_service import VaultGitPushService
from vault.service.vault_inspection_service import VaultInspectionService
from vault.service.vault_search_service import VaultSearchService
from vault.service.vault_write_service import VaultWriteService


class Runtime(FrozenModel):
    note_repository: VaultNoteRepository
    write_queue: VaultWriteQueue
    write_service: VaultWriteService
    git_push_service: VaultGitPushService
    search_service: VaultSearchService
    inspection_service: VaultInspectionService


class RuntimeRegistry:
    def __init__(self) -> None:
        self._runtime_by_vault: dict[Path, Runtime] = {}
        self._lock = Lock()

    def get(self, settings: Settings) -> Runtime:
        vault_root = settings.vault_path.expanduser().resolve()
        with self._lock:
            runtime = self._runtime_by_vault.get(vault_root)
            if runtime is None:
                runtime = self._create(vault_root)
                self._runtime_by_vault[vault_root] = runtime
            return runtime

    def _create(self, vault_root: Path) -> Runtime:
        write_queue = VaultWriteQueue()
        note_repository = VaultNoteRepository(root=vault_root)
        git_repository = GitRepository(root=vault_root)
        write_service = VaultWriteService(
            paths=VaultPaths(root=vault_root),
            queue=write_queue,
            actor="llm-wiki",
        )
        git_push_service = VaultGitPushService(repository=git_repository, queue=write_queue)
        search_service = VaultSearchService(note_repository=note_repository)
        inspection_service = VaultInspectionService(note_repository=note_repository)
        return Runtime(
            note_repository=note_repository,
            write_queue=write_queue,
            write_service=write_service,
            git_push_service=git_push_service,
            search_service=search_service,
            inspection_service=inspection_service,
        )


_runtime_registry = RuntimeRegistry()


def get_runtime(settings: Settings) -> Runtime:
    return _runtime_registry.get(settings)


def create_runtime(settings: Settings) -> Runtime:
    return get_runtime(settings)
