import asyncio
from pathlib import Path

import pytest

from personal_kb_mcp.vault.paths import VaultPaths
from personal_kb_mcp.writes.queue import WriteQueue
from personal_kb_mcp.writes.writer import VaultWriter, WriteConflictError, WriteNoteCommand


def test_batch_write_notes_writes_all_notes(tmp_path: Path) -> None:
    async def exercise_writer() -> None:
        writer = VaultWriter(VaultPaths(tmp_path / "vault"), WriteQueue(), actor="tester")

        results = await writer.batch_write_notes(
            [
                WriteNoteCommand("daily/one.md", "One"),
                WriteNoteCommand("daily/two.md", "Two"),
            ]
        )

        assert [result.source_hash for result in results]
        assert (tmp_path / "vault" / "daily" / "one.md").exists()
        assert (tmp_path / "vault" / "daily" / "two.md").exists()

    asyncio.run(exercise_writer())


def test_batch_write_notes_rolls_back_files_when_atomic_write_fails(tmp_path: Path) -> None:
    async def exercise_writer() -> None:
        writer = VaultWriter(VaultPaths(tmp_path / "vault"), WriteQueue(), actor="tester")
        first_result = await writer.write_note("daily/existing.md", "Original")
        existing_path = first_result.path
        original_content = existing_path.read_text(encoding="utf-8")
        new_path = tmp_path / "vault" / "daily" / "new.md"

        with pytest.raises(WriteConflictError, match="stale if_hash"):
            await writer.batch_write_notes(
                [
                    WriteNoteCommand("daily/new.md", "New"),
                    WriteNoteCommand("daily/existing.md", "Bad update", if_hash="stale"),
                ],
                atomic=True,
            )

        assert existing_path.read_text(encoding="utf-8") == original_content
        assert not new_path.exists()

    asyncio.run(exercise_writer())
