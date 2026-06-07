from dataclasses import dataclass
from pathlib import Path
from threading import Lock

from personal_kb_mcp.config import Settings
from personal_kb_mcp.vault.paths import VaultPaths
from personal_kb_mcp.writes.queue import WriteQueue
from personal_kb_mcp.writes.writer import VaultWriter


@dataclass(frozen=True)
class Runtime:
    write_queue: WriteQueue
    writer: VaultWriter


_queue_registry: dict[Path, WriteQueue] = {}
_queue_registry_lock = Lock()


def get_write_queue(vault_path: Path) -> WriteQueue:
    vault_root = vault_path.expanduser().resolve()
    with _queue_registry_lock:
        queue = _queue_registry.get(vault_root)
        if queue is None:
            queue = WriteQueue()
            _queue_registry[vault_root] = queue
        return queue


def create_runtime(settings: Settings) -> Runtime:
    vault_root = settings.vault_path.expanduser().resolve()
    write_queue = get_write_queue(vault_root)
    writer = VaultWriter(
        VaultPaths(vault_root),
        write_queue,
        actor="personal-kb-mcp",
    )
    return Runtime(write_queue=write_queue, writer=writer)
