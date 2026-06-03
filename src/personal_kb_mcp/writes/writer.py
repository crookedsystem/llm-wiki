from dataclasses import dataclass
from pathlib import Path

from personal_kb_mcp.git.repository import GitRepository
from personal_kb_mcp.vault.notes import append_provenance_trailer, compute_sha256
from personal_kb_mcp.vault.paths import VaultPaths
from personal_kb_mcp.writes.queue import WriteQueue


class WriteConflictError(RuntimeError):
    """Raised when an update does not satisfy optimistic concurrency."""


@dataclass(frozen=True)
class WriteNoteResult:
    path: Path
    source_hash: str
    content_hash: str
    commit_hash: str | None = None


@dataclass(frozen=True)
class VaultWriter:
    paths: VaultPaths
    queue: WriteQueue
    actor: str = "personal-kb-mcp"
    git_repository: GitRepository | None = None

    async def write_note(
        self,
        note_path: str | Path,
        content: str,
        *,
        if_hash: str | None = None,
    ) -> WriteNoteResult:
        async def operation() -> WriteNoteResult:
            return await self._write_note(
                note_path,
                content,
                if_hash=if_hash,
            )

        return await self.queue.run(operation)

    async def _write_note(
        self,
        note_path: str | Path,
        content: str,
        *,
        if_hash: str | None,
    ) -> WriteNoteResult:
        resolved_path = self.paths.resolve_note_path(note_path)
        self._check_if_hash(resolved_path, if_hash)

        source_hash = compute_sha256(content)
        final_content = append_provenance_trailer(
            content,
            source_hash=source_hash,
            operation="write_note",
            actor=self.actor,
        )
        resolved_path.parent.mkdir(parents=True, exist_ok=True)
        resolved_path.write_text(final_content, encoding="utf-8")
        commit_hash = self._commit_written_path(resolved_path)
        return WriteNoteResult(
            path=resolved_path,
            source_hash=source_hash,
            content_hash=compute_sha256(final_content),
            commit_hash=commit_hash,
        )

    def _commit_written_path(self, resolved_path: Path) -> str | None:
        if self.git_repository is None:
            return None
        return self.git_repository.commit_paths(
            [resolved_path],
            f"Update {resolved_path.relative_to(self.paths.root.resolve()).as_posix()}",
        )

    def _check_if_hash(self, resolved_path: Path, if_hash: str | None) -> None:
        if not resolved_path.exists():
            return
        if if_hash is None:
            raise WriteConflictError("if_hash is required for existing notes")

        current_hash = compute_sha256(resolved_path.read_text(encoding="utf-8"))
        if current_hash != if_hash:
            raise WriteConflictError("stale if_hash does not match current note content")
