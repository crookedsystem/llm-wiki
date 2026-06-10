from pathlib import Path

from common.model import FrozenModel
from vault.component.write_queue import VaultWriteQueue
from vault.entity.vault_note import (
    append_provenance_trailer,
    compute_sha256,
)
from vault.entity.vault_path import VaultPaths
from vault.error.write_error import WriteConflictError
from vault.infrastructure.repository.git_repository import GitRepository
from vault.service.command.write_note_command import WriteNoteCommand
from vault.service.result.write_note_result import WriteNoteResult
from vault.service.vault_schema_service import VaultSchemaService


class _FileSnapshot(FrozenModel):
    path: Path
    content: str | None


class VaultWriteService(FrozenModel):
    paths: VaultPaths
    queue: VaultWriteQueue
    actor: str = "llm-wiki"
    git_repository: GitRepository | None = None
    schema_service: VaultSchemaService | None = None

    async def write_note(self, command: WriteNoteCommand) -> WriteNoteResult:
        async def operation() -> WriteNoteResult:
            return await self._write_note(command)

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
            return [await self._write_note(command) for command in commands]
        except Exception:
            if atomic:
                self._restore_snapshots(snapshots)
            raise

    async def _write_note(self, command: WriteNoteCommand) -> WriteNoteResult:
        resolved_path = self.paths.resolve_note_path(command.note_path)
        note_path = resolved_path.relative_to(self.paths.root.resolve()).as_posix()
        self._check_if_hash(resolved_path, command.if_hash)
        if self.schema_service is not None:
            self.schema_service.ensure_valid_write(note_path, command.content)

        source_hash = compute_sha256(command.content)
        final_content = (
            command.content
            if _is_raw_note_path(note_path)
            else append_provenance_trailer(
                command.content,
                source_hash=source_hash,
                operation="write_note",
                actor=self.actor,
            )
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
            snapshots.append(_FileSnapshot(path=resolved_path, content=content))
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


def _is_raw_note_path(note_path: str) -> bool:
    return Path(note_path).parts[:1] == ("raw",)
