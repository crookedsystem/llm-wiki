import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest

from vault.component.write_queue import VaultWriteQueue
from vault.entity.vault_path import VaultPaths
from vault.error.write_error import WriteConflictError
from vault.service.command.write_note_command import WriteNoteCommand
from vault.service.vault_write_service import VaultWriteService


def _write_command(
    note_path: str,
    title: str,
    body: str,
    *,
    if_hash: str | None = None,
) -> WriteNoteCommand:
    return WriteNoteCommand(
        note_path=note_path,
        title=title,
        type="concept",
        tags=("batch",),
        sources=("raw/articles/source.md",),
        body=f"## Summary\n{body}",
        created=datetime(2026, 6, 12, 9, 30, 45, tzinfo=UTC),
        updated=datetime(2026, 6, 12, 10, 31, 46, tzinfo=UTC),
        if_hash=if_hash,
    )


def test_batch_write는_여러_note를_한_번에_작성한다(tmp_path: Path) -> None:
    async def exercise_writer() -> None:
        # Given: 같은 vault에 작성할 두 개의 write command가 있다.
        writer = VaultWriteService(
            paths=VaultPaths(root=tmp_path / "vault"), queue=VaultWriteQueue(), actor="tester"
        )
        commands = [
            _write_command("concepts/one.md", "One", "One"),
            _write_command("concepts/two.md", "Two", "Two"),
        ]

        # When: batch write를 실행한다.
        results = await writer.batch_write_notes(commands)

        # Then: 모든 note가 작성되고 각 결과에 source hash가 포함된다.
        assert [result.source_hash for result in results]
        assert (tmp_path / "vault" / "concepts" / "one.md").exists()
        assert (tmp_path / "vault" / "concepts" / "two.md").exists()

    asyncio.run(exercise_writer())


def test_atomic_batch_write는_중간에_실패하면_작성된_파일을_롤백한다(tmp_path: Path) -> None:
    async def exercise_writer() -> None:
        # Given: 기존 note와 새 note 작성이 섞인 atomic batch command가 있다.
        writer = VaultWriteService(
            paths=VaultPaths(root=tmp_path / "vault"), queue=VaultWriteQueue(), actor="tester"
        )
        first_result = await writer.write_note(
            _write_command("concepts/existing.md", "Existing", "Original")
        )
        existing_path = first_result.path
        original_content = existing_path.read_text(encoding="utf-8")
        new_path = tmp_path / "vault" / "concepts" / "new.md"

        # When / Then: 기존 note를 stale hash로 수정하려 하면 batch 전체가 실패한다.
        with pytest.raises(WriteConflictError, match="stale if_hash"):
            await writer.batch_write_notes(
                [
                    _write_command("concepts/new.md", "New", "New"),
                    _write_command(
                        "concepts/existing.md",
                        "Existing",
                        "Bad update",
                        if_hash="stale",
                    ),
                ],
                atomic=True,
            )

        # Then: 실패 전 새로 생긴 파일은 삭제되고 기존 note 내용은 원래대로 유지된다.
        assert existing_path.read_text(encoding="utf-8") == original_content
        assert not new_path.exists()

    asyncio.run(exercise_writer())
