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
class WriteNoteCommand:
    note_path: str | Path
    content: str
    if_hash: str | None = None


@dataclass(frozen=True)
class _FileSnapshot:
    path: Path
    content: str | None


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

    async def batch_write_notes(
        self,
        commands: list[WriteNoteCommand],
        *,
        atomic: bool = True,
    ) -> list[WriteNoteResult]:
        async def operation() -> list[WriteNoteResult]:
            return await self._batch_write_notes(commands, atomic=atomic)

        return await self.queue.run(operation)

    async def _batch_write_notes(
        self,
        commands: list[WriteNoteCommand],
        *,
        atomic: bool,
    ) -> list[WriteNoteResult]:
        snapshots = self._snapshot_commands(commands) if atomic else []
        try:
            return [
                await self._write_note(command.note_path, command.content, if_hash=command.if_hash)
                for command in commands
            ]
        except Exception:
            if atomic:
                self._restore_snapshots(snapshots)
            raise

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

    def _snapshot_commands(self, commands: list[WriteNoteCommand]) -> list[_FileSnapshot]:
        snapshots: list[_FileSnapshot] = []
        seen_paths: set[Path] = set()
        for command in commands:
            resolved_path = self.paths.resolve_note_path(command.note_path)
            if resolved_path in seen_paths:
                continue
            seen_paths.add(resolved_path)
            content = resolved_path.read_text(encoding="utf-8") if resolved_path.exists() else None
            snapshots.append(_FileSnapshot(resolved_path, content))
        return snapshots

    def _restore_snapshots(self, snapshots: list[_FileSnapshot]) -> None:
        for snapshot in snapshots:
            if snapshot.content is None:
                snapshot.path.unlink(missing_ok=True)
                continue
            snapshot.path.parent.mkdir(parents=True, exist_ok=True)
            snapshot.path.write_text(snapshot.content, encoding="utf-8")

    def _check_if_hash(self, resolved_path: Path, if_hash: str | None) -> None:
        if not resolved_path.exists():
            return
        if if_hash is None:
            raise WriteConflictError("if_hash is required for existing notes")

        current_hash = compute_sha256(resolved_path.read_text(encoding="utf-8"))
        if current_hash != if_hash:
            raise WriteConflictError("stale if_hash does not match current note content")
