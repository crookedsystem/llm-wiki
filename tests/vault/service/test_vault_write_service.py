import asyncio
from pathlib import Path

import pytest

from vault.component.write_queue import VaultWriteQueue
from vault.entity.vault_note import compute_sha256
from vault.entity.vault_path import VaultPaths
from vault.error.write_error import WriteConflictError
from vault.infrastructure.repository.vault_note_repository import VaultNoteRepository
from vault.service.command.write_note_command import WriteNoteCommand
from vault.service.vault_schema_service import SchemaValidationError, VaultSchemaService
from vault.service.vault_write_service import VaultWriteService


def test_note_작성은_hash와_provenance를_함께_반환한다(tmp_path: Path) -> None:
    async def exercise_writer() -> None:
        # Given: provenance actor가 지정된 vault writer가 있다.
        writer = VaultWriteService(
            paths=VaultPaths(root=tmp_path / "vault"), queue=VaultWriteQueue(), actor="tester"
        )

        # When: 새 markdown note를 작성한다.
        result = await writer.write_note(
            WriteNoteCommand(note_path="daily/today.md", content="Body text")
        )
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
            paths=VaultPaths(root=tmp_path / "vault"), queue=VaultWriteQueue(), actor="tester"
        )
        first_result = await writer.write_note(
            WriteNoteCommand(note_path="daily/today.md", content="Initial body")
        )

        # When / Then: if_hash가 없거나 오래된 값이면 수정이 거부된다.
        with pytest.raises(WriteConflictError, match="if_hash is required"):
            await writer.write_note(
                WriteNoteCommand(note_path="daily/today.md", content="Update without hash")
            )

        with pytest.raises(WriteConflictError, match="stale if_hash"):
            await writer.write_note(
                WriteNoteCommand(note_path="daily/today.md", content="Stale update", if_hash="bad")
            )

        # When: 현재 content hash로 note를 수정한다.
        updated_result = await writer.write_note(
            WriteNoteCommand(
                note_path="daily/today.md",
                content="Fresh update",
                if_hash=first_result.content_hash,
            )
        )

        # Then: stale overwrite 없이 새 본문과 hash가 기록된다.
        assert updated_result.source_hash == compute_sha256("Fresh update")
        assert "Fresh update" in updated_result.path.read_text(encoding="utf-8")

    asyncio.run(exercise_writer())


def _schema_text() -> str:
    return """# Wiki Schema

## Frontmatter
Required fields: `title`, `created`, `updated`, `type`, `tags`, `sources`,
`confidence`, `contested`.
Allowed `type` values: `entity`, `concept`, `comparison`, `query`, `summary`.

## Tag taxonomy
- Knowledge: agent-memory
"""


def _schema_validating_writer(vault_root: Path) -> VaultWriteService:
    schema_service = VaultSchemaService(note_repository=VaultNoteRepository(root=vault_root))
    return VaultWriteService(
        paths=VaultPaths(root=vault_root),
        queue=VaultWriteQueue(),
        actor="tester",
        schema_service=schema_service,
    )


def test_write_note는_schema_service가_있으면_잘못된_concept_write를_거부한다(
    tmp_path: Path,
) -> None:
    async def exercise_writer() -> None:
        # Given: schema validation이 write boundary에 연결된 writer가 있다.
        vault_root = tmp_path / "vault"
        writer = _schema_validating_writer(vault_root)
        await writer.write_note(WriteNoteCommand(note_path="SCHEMA.md", content=_schema_text()))

        # When / Then: synthesized page가 frontmatter 없이 저장되려고 하면 거부된다.
        with pytest.raises(SchemaValidationError) as error:
            await writer.write_note(
                WriteNoteCommand(note_path="concepts/agent-memory.md", content="# Agent Memory\n")
            )
        assert error.value.issues[0].code == "missing_frontmatter"
        assert not (vault_root / "concepts" / "agent-memory.md").exists()

    asyncio.run(exercise_writer())


def test_write_note는_정규화된_resolved_path로_schema_validation을_수행한다(
    tmp_path: Path,
) -> None:
    async def exercise_writer() -> None:
        # Given: schema validation이 write boundary에 연결된 writer가 있다.
        vault_root = tmp_path / "vault"
        writer = _schema_validating_writer(vault_root)
        await writer.write_note(WriteNoteCommand(note_path="SCHEMA.md", content=_schema_text()))
        body = "# Raw Session\n"
        raw_content = f"""---
source_url: hermes-session:abc
ingested: 2026-06-10
sha256: {compute_sha256(body)}
---
{body}"""

        # When / Then: raw/.. path가 concepts/로 정규화되면 synthesized contract로 거부된다.
        with pytest.raises(SchemaValidationError) as error:
            await writer.write_note(
                WriteNoteCommand(note_path="raw/../concepts/agent-memory.md", content=raw_content)
            )
        assert error.value.issues[0].code == "missing_required_field"
        assert error.value.issues[0].path == "concepts/agent-memory.md"
        assert not (vault_root / "concepts" / "agent-memory.md").exists()

    asyncio.run(exercise_writer())


def test_write_note는_raw_body_sha256을_보존하기_위해_raw에는_provenance를_붙이지_않는다(
    tmp_path: Path,
) -> None:
    async def exercise_writer() -> None:
        # Given: body-only sha256을 가진 raw note content가 있다.
        vault_root = tmp_path / "vault"
        writer = _schema_validating_writer(vault_root)
        await writer.write_note(WriteNoteCommand(note_path="SCHEMA.md", content=_schema_text()))
        body = "# Raw Session\n"
        raw_content = f"""---
source_url: hermes-session:abc
ingested: 2026-06-10
sha256: {compute_sha256(body)}
---
{body}"""

        # When: raw note를 kb_write_note 경로로 저장한다.
        result = await writer.write_note(
            WriteNoteCommand(note_path="raw/hermes/session.md", content=raw_content)
        )
        written_content = result.path.read_text(encoding="utf-8")

        # Then: provenance trailer로 source body를 오염시키지 않아 validate_vault가 통과한다.
        assert written_content == raw_content
        assert "kb-provenance" not in written_content
        assert writer.schema_service is not None
        assert writer.schema_service.validate_vault().issues == []

    asyncio.run(exercise_writer())
