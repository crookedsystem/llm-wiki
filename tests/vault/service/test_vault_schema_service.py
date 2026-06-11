from pathlib import Path

from vault.entity.vault_note import compute_sha256
from vault.infrastructure.repository.vault_note_repository import VaultNoteRepository
from vault.service.vault_schema_service import VaultSchemaService

SCHEMA = """# Wiki Schema

## Frontmatter
Required fields: `title`, `created`, `updated`, `type`, `tags`, `sources`,
`confidence`, `contested`.
Allowed `type` values: `entity`, `concept`, `comparison`, `query`, `summary`.

## Tag taxonomy
- Knowledge: knowledge-base, agent-memory, mcp
- Engineering: verification
"""


def _write_schema(vault_root: Path, schema: str = SCHEMA) -> None:
    vault_root.mkdir(parents=True, exist_ok=True)
    (vault_root / "SCHEMA.md").write_text(schema, encoding="utf-8")


def _write_raw_note(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""---
source_url: test://{path.stem}
ingested: 2026-06-10
sha256: {compute_sha256(body)}
---
{body}""",
        encoding="utf-8",
    )


def test_validate_write_rejects_invalid_synthesized_frontmatter(tmp_path: Path) -> None:
    # Given: tag taxonomy가 있는 LLM Wiki vault가 있다.
    vault_root = tmp_path / "vault"
    _write_schema(vault_root)
    schema_service = VaultSchemaService(note_repository=VaultNoteRepository(root=vault_root))

    # When: synthesized page frontmatter가 없거나 taxonomy 밖 tag를 쓰면 검증한다.
    missing_frontmatter = schema_service.validate_write(
        "concepts/agent-memory.md",
        "# Agent Memory\n",
    )
    unknown_tag = schema_service.validate_write(
        "concepts/agent-memory.md",
        """---
title: Agent Memory
created: 2026-06-10
updated: 2026-06-10
type: concept
tags: [unknown-tag]
sources: [raw/hermes/source.md]
confidence: medium
contested: false
---

# Agent Memory
""",
    )

    # Then: write boundary에서 바로 고칠 수 있는 issue code가 반환된다.
    assert [issue.code for issue in missing_frontmatter.issues] == ["missing_frontmatter"]
    assert [issue.code for issue in unknown_tag.issues] == ["unknown_tag"]
    assert unknown_tag.issues[0].value == "unknown-tag"


def test_validate_write_accepts_crlf_synthesized_frontmatter(tmp_path: Path) -> None:
    # Given: schema가 준비된 LLM Wiki vault가 있다.
    vault_root = tmp_path / "vault"
    _write_schema(vault_root)
    schema_service = VaultSchemaService(note_repository=VaultNoteRepository(root=vault_root))

    # When: Windows/Obsidian 스타일 CRLF frontmatter로 synthesized page를 검증한다.
    result = schema_service.validate_write(
        "concepts/agent-memory.md",
        "---\r\n"
        "title: Agent Memory\r\n"
        "created: 2026-06-10\r\n"
        "updated: 2026-06-10\r\n"
        "type: concept\r\n"
        "tags: [agent-memory]\r\n"
        "sources: [raw/hermes/source.md]\r\n"
        "confidence: medium\r\n"
        "contested: false\r\n"
        "---\r\n"
        "# Agent Memory\r\n",
    )

    # Then: 유효한 YAML frontmatter로 인식되어 missing_frontmatter가 발생하지 않는다.
    assert result.issues == []


def test_validate_write_rejects_blank_synthesized_sources(tmp_path: Path) -> None:
    # Given: schema가 준비된 LLM Wiki vault가 있다.
    vault_root = tmp_path / "vault"
    _write_schema(vault_root)
    schema_service = VaultSchemaService(note_repository=VaultNoteRepository(root=vault_root))

    # When: sources가 list 형식이지만 실제 source 값은 비어 있다.
    result = schema_service.validate_write(
        "concepts/agent-memory.md",
        """---
title: Agent Memory
created: 2026-06-10
updated: 2026-06-10
type: concept
tags: [agent-memory]
sources: ["   "]
confidence: medium
contested: false
---

# Agent Memory
""",
    )

    # Then: 빈 list와 동일하게 사용할 수 없는 source로 검증 실패한다.
    assert [issue.code for issue in result.issues] == ["empty_sources"]


def test_validate_write_rejects_synthesized_page_when_schema_is_missing(
    tmp_path: Path,
) -> None:
    # Given: SCHEMA.md가 아직 없는 vault가 있다.
    vault_root = tmp_path / "vault"
    schema_service = VaultSchemaService(note_repository=VaultNoteRepository(root=vault_root))

    # When: required frontmatter를 갖춘 synthesized page를 먼저 쓰려고 한다.
    result = schema_service.validate_write(
        "concepts/agent-memory.md",
        """---
title: Agent Memory
created: 2026-06-10
updated: 2026-06-10
type: concept
tags: []
sources: [raw/hermes/source.md]
confidence: medium
contested: false
---

# Agent Memory
""",
    )

    # Then: 기본 type fallback으로 통과시키지 않고 schema 생성부터 요구한다.
    assert [issue.code for issue in result.issues] == ["schema_missing"]


def test_validate_write_rejects_non_string_synthesized_type(tmp_path: Path) -> None:
    # Given: schema가 준비된 LLM Wiki vault가 있다.
    vault_root = tmp_path / "vault"
    _write_schema(vault_root)
    schema_service = VaultSchemaService(note_repository=VaultNoteRepository(root=vault_root))

    # When: synthesized page type이 문자열이 아니다.
    result = schema_service.validate_write(
        "concepts/agent-memory.md",
        """---
title: Agent Memory
created: 2026-06-10
updated: 2026-06-10
type: [concept]
tags: []
sources: [raw/hermes/source.md]
confidence: medium
contested: false
---

# Agent Memory
""",
    )

    # Then: required field 존재만으로 통과시키지 않고 타입 오류를 보고한다.
    assert [(issue.code, issue.field) for issue in result.issues] == [
        ("invalid_field_type", "type")
    ]


def test_validate_write_treats_scalar_synthesized_title_as_string(
    tmp_path: Path,
) -> None:
    # Given: schema가 준비된 LLM Wiki vault가 있다.
    vault_root = tmp_path / "vault"
    _write_schema(vault_root)
    schema_service = VaultSchemaService(note_repository=VaultNoteRepository(root=vault_root))

    # When: title이 문자열은 아니지만 YAML scalar다.
    result = schema_service.validate_write(
        "concepts/agent-memory.md",
        """---
title: 123
created: 2026-06-10
updated: 2026-06-10
type: concept
tags: []
sources: [raw/hermes/source.md]
confidence: medium
contested: false
---

# Agent Memory
""",
    )

    # Then: scalar title은 문자열 title로 취급한다.
    assert result.issues == []


def test_validate_write_rejects_non_scalar_or_blank_synthesized_title(
    tmp_path: Path,
) -> None:
    # Given: schema가 준비된 LLM Wiki vault가 있다.
    vault_root = tmp_path / "vault"
    _write_schema(vault_root)
    schema_service = VaultSchemaService(note_repository=VaultNoteRepository(root=vault_root))

    # When: title이 list이거나 빈 문자열이다.
    non_scalar = schema_service.validate_write(
        "concepts/agent-memory.md",
        """---
title: [Agent Memory]
created: 2026-06-10
updated: 2026-06-10
type: concept
tags: []
sources: [raw/hermes/source.md]
confidence: medium
contested: false
---

# Agent Memory
""",
    )
    blank = schema_service.validate_write(
        "concepts/agent-memory.md",
        """---
title: "   "
created: 2026-06-10
updated: 2026-06-10
type: concept
tags: []
sources: [raw/hermes/source.md]
confidence: medium
contested: false
---

# Agent Memory
""",
    )

    # Then: wiki map에서 사용할 수 없는 title은 거부한다.
    assert [(issue.code, issue.field) for issue in non_scalar.issues] == [
        ("invalid_field_type", "title")
    ]
    assert [(issue.code, issue.field) for issue in blank.issues] == [("invalid_title", "title")]


def test_validate_write_rejects_non_string_synthesized_confidence(
    tmp_path: Path,
) -> None:
    # Given: schema가 준비된 LLM Wiki vault가 있다.
    vault_root = tmp_path / "vault"
    _write_schema(vault_root)
    schema_service = VaultSchemaService(note_repository=VaultNoteRepository(root=vault_root))

    # When: synthesized page confidence가 문자열이 아니다.
    result = schema_service.validate_write(
        "concepts/agent-memory.md",
        """---
title: Agent Memory
created: 2026-06-10
updated: 2026-06-10
type: concept
tags: []
sources: [raw/hermes/source.md]
confidence: [medium]
contested: false
---

# Agent Memory
""",
    )

    # Then: required field 존재만으로 통과시키지 않고 타입 오류를 보고한다.
    assert [(issue.code, issue.field) for issue in result.issues] == [
        ("invalid_field_type", "confidence")
    ]


def test_validate_write_requires_raw_frontmatter_and_body_sha256(tmp_path: Path) -> None:
    # Given: schema가 준비된 LLM Wiki vault가 있다.
    vault_root = tmp_path / "vault"
    _write_schema(vault_root)
    schema_service = VaultSchemaService(note_repository=VaultNoteRepository(root=vault_root))

    # When: raw note에 frontmatter나 body-only sha256이 빠져 있다.
    missing_raw_metadata = schema_service.validate_write(
        "raw/hermes/session.md",
        "# Raw Session\n",
    )
    wrong_hash = schema_service.validate_write(
        "raw/hermes/session.md",
        """---
source_url: hermes-session:abc
ingested: 2026-06-10
sha256: bad
---

# Raw Session
""",
    )

    # Then: raw frontmatter와 sha256 mismatch를 hard error로 보고한다.
    assert [issue.code for issue in missing_raw_metadata.issues] == ["missing_frontmatter"]
    assert [issue.code for issue in wrong_hash.issues] == ["raw_sha256_mismatch"]


def test_validate_write_allows_raw_note_without_source_metadata(tmp_path: Path) -> None:
    # Given: schema가 준비된 LLM Wiki vault가 있다.
    vault_root = tmp_path / "vault"
    _write_schema(vault_root)
    schema_service = VaultSchemaService(note_repository=VaultNoteRepository(root=vault_root))
    body = "# 조사 메모\n\n직접 조사해 정리한 raw 내용.\n"

    # When: 외부 source 없이 raw note를 쓴다.
    result = schema_service.validate_write(
        "raw/manual/research.md",
        f"""---
ingested: 2026-06-10
sha256: {compute_sha256(body)}
---
{body}""",
    )

    # Then: source metadata가 없어도 raw archive로 허용한다.
    assert result.issues == []


def test_validate_write_allows_multiple_raw_source_urls(tmp_path: Path) -> None:
    # Given: schema가 준비된 LLM Wiki vault가 있다.
    vault_root = tmp_path / "vault"
    _write_schema(vault_root)
    schema_service = VaultSchemaService(note_repository=VaultNoteRepository(root=vault_root))
    body = "# Multi-source Raw\n"

    # When: raw note가 여러 source URL을 가진다.
    result = schema_service.validate_write(
        "raw/articles/multi-source.md",
        f"""---
source_urls:
  - https://example.com/one
  - https://example.com/two
ingested: 2026-06-10
sha256: {compute_sha256(body)}
---
{body}""",
    )

    # Then: 다중 source URL metadata를 허용한다.
    assert result.issues == []


def test_validate_write_rejects_non_list_raw_source_urls(tmp_path: Path) -> None:
    # Given: schema가 준비된 LLM Wiki vault가 있다.
    vault_root = tmp_path / "vault"
    _write_schema(vault_root)
    schema_service = VaultSchemaService(note_repository=VaultNoteRepository(root=vault_root))
    body = "# Multi-source Raw\n"

    # When: source_urls가 YAML list가 아니다.
    result = schema_service.validate_write(
        "raw/articles/multi-source.md",
        f"""---
source_urls: https://example.com/one
ingested: 2026-06-10
sha256: {compute_sha256(body)}
---
{body}""",
    )

    # Then: 다중 source field의 타입 오류를 보고한다.
    assert [(issue.code, issue.field) for issue in result.issues] == [
        ("invalid_field_type", "source_urls")
    ]


def test_validate_write_rejects_non_string_raw_source_url(tmp_path: Path) -> None:
    # Given: schema가 준비된 LLM Wiki vault가 있다.
    vault_root = tmp_path / "vault"
    _write_schema(vault_root)
    schema_service = VaultSchemaService(note_repository=VaultNoteRepository(root=vault_root))

    # When: raw source_url frontmatter가 문자열이 아니다.
    result = schema_service.validate_write(
        "raw/hermes/session.md",
        """---
source_url: [hermes-session:abc]
ingested: 2026-06-10
sha256: abc
---

# Raw Session
""",
    )

    # Then: source identifier로 사용할 수 없는 값을 타입 오류로 보고한다.
    assert [(issue.code, issue.field) for issue in result.issues] == [
        ("invalid_field_type", "source_url"),
        ("raw_sha256_mismatch", "sha256"),
    ]


def test_validate_write_rejects_non_string_raw_sha256(tmp_path: Path) -> None:
    # Given: schema가 준비된 LLM Wiki vault가 있다.
    vault_root = tmp_path / "vault"
    _write_schema(vault_root)
    schema_service = VaultSchemaService(note_repository=VaultNoteRepository(root=vault_root))

    # When: raw sha256 frontmatter가 문자열이 아니다.
    result = schema_service.validate_write(
        "raw/hermes/session.md",
        """---
source_url: hermes-session:abc
ingested: 2026-06-10
sha256: [bad]
---

# Raw Session
""",
    )

    # Then: hash 비교를 건너뛰지 않고 필드 타입 오류를 보고한다.
    assert [(issue.code, issue.field) for issue in result.issues] == [
        ("invalid_field_type", "sha256")
    ]


def test_validate_vault_reports_schema_hygiene_summary(tmp_path: Path) -> None:
    # Given: valid schema, invalid synthesized page, invalid raw note가 함께 있다.
    vault_root = tmp_path / "vault"
    _write_schema(vault_root)
    (vault_root / "concepts").mkdir()
    (vault_root / "concepts" / "bad.md").write_text(
        """---
title: Bad
created: 2026-06-10
updated: 2026-06-10
type: concept
tags: [not-in-schema]
sources: []
confidence: high
contested: false
---

# Bad
""",
        encoding="utf-8",
    )
    (vault_root / "raw" / "hermes").mkdir(parents=True)
    (vault_root / "raw" / "hermes" / "bad.md").write_text(
        """---
source_url: hermes-session:bad
ingested: 2026-06-10
sha256: bad
---

raw body
""",
        encoding="utf-8",
    )

    # When: vault 전체 schema hygiene를 검증한다.
    result = VaultSchemaService(
        note_repository=VaultNoteRepository(root=vault_root)
    ).validate_vault()

    # Then: content migration 없이 deterministic schema issue만 집계된다.
    assert result.summary.unknown_tags == 1
    assert result.summary.empty_sources == 1
    assert result.summary.raw_sha256_mismatch == 1
    assert {issue.path for issue in result.issues} == {
        "concepts/bad.md",
        "raw/hermes/bad.md",
    }
