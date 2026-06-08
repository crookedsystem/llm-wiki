from dataclasses import dataclass
from pathlib import Path
from threading import Lock

from personal_kb_mcp.config import Settings
from personal_kb_mcp.domain.vault.entity.vault_path import VaultPaths
from personal_kb_mcp.domain.vault.infrastructure.repositories.vault_note_repository import (
    VaultNoteRepository,
)
from personal_kb_mcp.domain.vault.service.vault_inspection_service import VaultInspectionService
from personal_kb_mcp.domain.vault.service.vault_search_service import VaultSearchService
from personal_kb_mcp.domain.vault.service.vault_write_queue import VaultWriteQueue
from personal_kb_mcp.domain.vault.service.vault_write_service import VaultWriteService


@dataclass(frozen=True)
class Runtime:
    write_queue: VaultWriteQueue
    write_service: VaultWriteService
    search_service: VaultSearchService
    inspection_service: VaultInspectionService


_queue_registry: dict[Path, VaultWriteQueue] = {}
_queue_registry_lock = Lock()


def get_write_queue(vault_path: Path) -> VaultWriteQueue:
    vault_root = vault_path.expanduser().resolve()
    with _queue_registry_lock:
        queue = _queue_registry.get(vault_root)
        if queue is None:
            queue = VaultWriteQueue()
            _queue_registry[vault_root] = queue
        return queue


def create_runtime(settings: Settings) -> Runtime:
    vault_root = settings.vault_path.expanduser().resolve()
    write_queue = get_write_queue(vault_root)
    note_repository = VaultNoteRepository(vault_root)
    write_service = VaultWriteService(
        VaultPaths(vault_root),
        write_queue,
        actor="personal-kb-mcp",
    )
    search_service = VaultSearchService(note_repository)
    inspection_service = VaultInspectionService(note_repository)
    return Runtime(
        write_queue=write_queue,
        write_service=write_service,
        search_service=search_service,
        inspection_service=inspection_service,
    )
