import asyncio
from pathlib import Path

import pytest

from personal_kb_mcp.domain.vault.entity.vault_path import VaultPaths
from personal_kb_mcp.domain.vault.service.command.write_note_command import WriteNoteCommand
from personal_kb_mcp.domain.vault.service.vault_write_errors import WriteConflictError
from personal_kb_mcp.domain.vault.service.vault_write_queue import VaultWriteQueue
from personal_kb_mcp.domain.vault.service.vault_write_service import VaultWriteService


def test_batch_write는_여러_note를_한_번에_작성한다(tmp_path: Path) -> None:
    async def exercise_writer() -> None:
        # Given: 같은 vault에 작성할 두 개의 write command가 있다.
        writer = VaultWriteService(
            VaultPaths(tmp_path / "vault"), VaultWriteQueue(), actor="tester"
        )
        commands = [
            WriteNoteCommand("daily/one.md", "One"),
            WriteNoteCommand("daily/two.md", "Two"),
        ]

        # When: batch write를 실행한다.
        results = await writer.batch_write_notes(commands)

        # Then: 모든 note가 작성되고 각 결과에 source hash가 포함된다.
        assert [result.source_hash for result in results]
        assert (tmp_path / "vault" / "daily" / "one.md").exists()
        assert (tmp_path / "vault" / "daily" / "two.md").exists()

    asyncio.run(exercise_writer())


def test_atomic_batch_write는_중간에_실패하면_작성된_파일을_롤백한다(tmp_path: Path) -> None:
    async def exercise_writer() -> None:
        # Given: 기존 note와 새 note 작성이 섞인 atomic batch command가 있다.
        writer = VaultWriteService(
            VaultPaths(tmp_path / "vault"), VaultWriteQueue(), actor="tester"
        )
        first_result = await writer.write_note(WriteNoteCommand("daily/existing.md", "Original"))
        existing_path = first_result.path
        original_content = existing_path.read_text(encoding="utf-8")
        new_path = tmp_path / "vault" / "daily" / "new.md"

        # When / Then: 기존 note를 stale hash로 수정하려 하면 batch 전체가 실패한다.
        with pytest.raises(WriteConflictError, match="stale if_hash"):
            await writer.batch_write_notes(
                [
                    WriteNoteCommand("daily/new.md", "New"),
                    WriteNoteCommand("daily/existing.md", "Bad update", if_hash="stale"),
                ],
                atomic=True,
            )

        # Then: 실패 전 새로 생긴 파일은 삭제되고 기존 note 내용은 원래대로 유지된다.
        assert existing_path.read_text(encoding="utf-8") == original_content
        assert not new_path.exists()

    asyncio.run(exercise_writer())
