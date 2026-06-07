import asyncio
from pathlib import Path

import pytest

from personal_kb_mcp.vault.notes import compute_sha256
from personal_kb_mcp.vault.paths import VaultPaths
from personal_kb_mcp.writes.queue import WriteQueue
from personal_kb_mcp.writes.writer import VaultWriter, WriteConflictError


def test_write_note_returns_hashes_and_provenance(tmp_path: Path) -> None:
    async def exercise_writer() -> None:
        writer = VaultWriter(VaultPaths(tmp_path / "vault"), WriteQueue(), actor="tester")

        result = await writer.write_note("daily/today.md", "Body text")
        written_content = result.path.read_text(encoding="utf-8")

        assert result.source_hash == compute_sha256("Body text")
        assert result.content_hash == compute_sha256(written_content)
        assert result.commit_hash is None
        assert f"source_hash={result.source_hash}" in written_content
        assert "actor=tester" in written_content

    asyncio.run(exercise_writer())


def test_write_note_requires_matching_if_hash_for_updates(tmp_path: Path) -> None:
    async def exercise_writer() -> None:
        writer = VaultWriter(VaultPaths(tmp_path / "vault"), WriteQueue(), actor="tester")
        first_result = await writer.write_note("daily/today.md", "Initial body")

        with pytest.raises(WriteConflictError, match="if_hash is required"):
            await writer.write_note("daily/today.md", "Update without hash")

        with pytest.raises(WriteConflictError, match="stale if_hash"):
            await writer.write_note("daily/today.md", "Stale update", if_hash="bad")

        updated_result = await writer.write_note(
            "daily/today.md",
            "Fresh update",
            if_hash=first_result.content_hash,
        )

        assert updated_result.source_hash == compute_sha256("Fresh update")
        assert "Fresh update" in updated_result.path.read_text(encoding="utf-8")

    asyncio.run(exercise_writer())
