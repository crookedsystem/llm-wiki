import asyncio
from pathlib import Path

import pytest

from personal_kb_mcp.domain.vault_note import compute_sha256
from personal_kb_mcp.domain.vault_path import VaultPaths
from personal_kb_mcp.domain.vault_write import WriteConflictError
from personal_kb_mcp.service.vault_write_queue import VaultWriteQueue
from personal_kb_mcp.service.vault_write_service import VaultWriteService


def test_note_작성은_hash와_provenance를_함께_반환한다(tmp_path: Path) -> None:
    async def exercise_writer() -> None:
        # Given: provenance actor가 지정된 vault writer가 있다.
        writer = VaultWriteService(
            VaultPaths(tmp_path / "vault"), VaultWriteQueue(), actor="tester"
        )

        # When: 새 markdown note를 작성한다.
        result = await writer.write_note("daily/today.md", "Body text")
        written_content = result.path.read_text(encoding="utf-8")

        # Then: 원본 hash, 최종 content hash, provenance trailer가 함께 남는다.
        assert result.source_hash == compute_sha256("Body text")
        assert result.content_hash == compute_sha256(written_content)
        assert result.commit_hash is None
        assert f"source_hash={result.source_hash}" in written_content
        assert "actor=tester" in written_content

    asyncio.run(exercise_writer())


def test_existing_note_수정은_현재_content_hash가_맞을_때만_허용된다(tmp_path: Path) -> None:
    async def exercise_writer() -> None:
        # Given: 이미 작성된 note와 그 note의 현재 content hash가 있다.
        writer = VaultWriteService(
            VaultPaths(tmp_path / "vault"), VaultWriteQueue(), actor="tester"
        )
        first_result = await writer.write_note("daily/today.md", "Initial body")

        # When / Then: if_hash가 없거나 오래된 값이면 수정이 거부된다.
        with pytest.raises(WriteConflictError, match="if_hash is required"):
            await writer.write_note("daily/today.md", "Update without hash")

        with pytest.raises(WriteConflictError, match="stale if_hash"):
            await writer.write_note("daily/today.md", "Stale update", if_hash="bad")

        # When: 현재 content hash로 note를 수정한다.
        updated_result = await writer.write_note(
            "daily/today.md",
            "Fresh update",
            if_hash=first_result.content_hash,
        )

        # Then: stale overwrite 없이 새 본문과 hash가 기록된다.
        assert updated_result.source_hash == compute_sha256("Fresh update")
        assert "Fresh update" in updated_result.path.read_text(encoding="utf-8")

    asyncio.run(exercise_writer())
