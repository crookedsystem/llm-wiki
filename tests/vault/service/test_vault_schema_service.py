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


def _write_synthesized_note(
    path: Path,
    *,
    title: str,
    page_type: str,
    tags: list[str],
    sources: list[str],
    body: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tags_text = ", ".join(tags)
    sources_text = ", ".join(sources)
    path.write_text(
        f"""---
title: {title}
created: 2026-06-10
updated: 2026-06-10
type: {page_type}
tags: [{tags_text}]
sources: [{sources_text}]
confidence: medium
contested: false
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


def test_wiki_context_returns_schema_index_recent_log_and_health(tmp_path: Path) -> None:
    # Given: SCHEMA, index, log가 있는 vault가 있다.
    vault_root = tmp_path / "vault"
    _write_schema(vault_root)
    (vault_root / "index.md").write_text("# Wiki Index\n\n## Concepts\n", encoding="utf-8")
    (vault_root / "log.md").write_text(
        "# Wiki Log\n\n## [2026-06-08] create | old\n## [2026-06-10] lint | recent\n",
        encoding="utf-8",
    )

    # When: MCP context-first workflow용 context를 만든다.
    context = VaultSchemaService(note_repository=VaultNoteRepository(root=vault_root)).wiki_context(
        recent_log_lines=1
    )

    # Then: LLM은 별도 파일 읽기 없이 schema/index/log/health를 확인할 수 있다.
    assert "## Tag taxonomy" in context.schema_text
    assert "# Wiki Index" in context.index
    assert context.recent_log == "## [2026-06-10] lint | recent"
    assert context.parsed_schema.allowed_tags == [
        "agent-memory",
        "knowledge-base",
        "mcp",
        "verification",
    ]
    assert context.health.schema_parse_ok is True
    assert context.health.unknown_tag_count == 0


def test_wiki_context_can_omit_schema_rules_from_payload(tmp_path: Path) -> None:
    # Given: SCHEMA.md가 있는 vault가 있다.
    vault_root = tmp_path / "vault"
    _write_schema(vault_root)

    # When: schema/rules payload를 제외해 context 크기를 줄인다.
    context = VaultSchemaService(note_repository=VaultNoteRepository(root=vault_root)).wiki_context(
        include_schema_rules=False
    )

    # Then: health 계산은 실제 schema 기준이지만 응답 payload의 schema/rule 필드는 비운다.
    assert context.schema_text == ""
    assert context.parsed_schema.schema_parse_ok is False
    assert context.parsed_schema.allowed_tags == []
    assert context.health.schema_parse_ok is True


def test_wiki_context_recent_log_skips_provenance_trailer(tmp_path: Path) -> None:
    # Given: log.md 끝에 write provenance trailer가 붙어 있다.
    vault_root = tmp_path / "vault"
    _write_schema(vault_root)
    (vault_root / "log.md").write_text(
        (
            "# Wiki Log\n\n"
            "## [2026-06-08] create | old\n"
            "## [2026-06-10] lint | recent\n"
            "<!-- kb-provenance: source_hash=abc; operation=write_note; actor=test -->\n"
        ),
        encoding="utf-8",
    )

    # When: 최근 log 1줄만 요청한다.
    context = VaultSchemaService(note_repository=VaultNoteRepository(root=vault_root)).wiki_context(
        recent_log_lines=1
    )

    # Then: provenance comment가 아니라 실제 최신 durable log entry를 반환한다.
    assert context.recent_log == "## [2026-06-10] lint | recent"


def test_wiki_context_omits_unindexed_guidance_when_index_is_excluded(
    tmp_path: Path,
) -> None:
    # Given: index.md에 아직 없는 synthesized page가 있다.
    vault_root = tmp_path / "vault"
    _write_schema(vault_root)
    _write_raw_note(vault_root / "raw" / "articles" / "source.md", "Source body\n")
    _write_synthesized_note(
        vault_root / "concepts" / "agent-memory.md",
        title="Agent Memory",
        page_type="concept",
        tags=["agent-memory"],
        sources=["raw/articles/source.md"],
        body="# Agent Memory\n\nNo index context requested.\n",
    )

    # When: context payload 절감을 위해 index를 제외한다.
    context = VaultSchemaService(note_repository=VaultNoteRepository(root=vault_root)).wiki_context(
        include_index=False
    )

    # Then: 빈 index 문자열 때문에 unindexed backlog를 만들지 않는다.
    assert "unindexed_page" not in {issue.code for issue in context.issue_candidates}
    assert "add_index_entry" not in {suggestion.action for suggestion in context.update_suggestions}


def test_wiki_context_requires_real_index_link_or_path_match(tmp_path: Path) -> None:
    # Given: page stem이 index.md의 일반 단어 일부로만 등장한다.
    vault_root = tmp_path / "vault"
    _write_schema(vault_root)
    (vault_root / "index.md").write_text(
        (
            "# Wiki Index\n\n"
            "This daily chain mentions ai as plain text only.\n"
            "Also mentions concepts/aiology but not the actual AI page.\n"
        ),
        encoding="utf-8",
    )
    _write_raw_note(vault_root / "raw" / "articles" / "source.md", "Source body\n")
    _write_synthesized_note(
        vault_root / "concepts" / "ai.md",
        title="AI",
        page_type="concept",
        tags=["agent-memory"],
        sources=["raw/articles/source.md"],
        body="# AI\n\nNo explicit index entry.\n",
    )

    # When: wiki context를 만든다.
    context = VaultSchemaService(
        note_repository=VaultNoteRepository(root=vault_root)
    ).wiki_context()

    # Then: 임의 substring이 아니라 실제 path/link가 있어야 indexed로 본다.
    page = next(page for page in context.wiki_map.pages if page.path == "concepts/ai.md")
    assert page.indexed is False
    assert "unindexed_page" in {issue.code for issue in context.issue_candidates}


def test_wiki_context_treats_title_wikilink_in_index_as_indexed(tmp_path: Path) -> None:
    # Given: index.md가 file path 대신 Obsidian title wikilink로 page를 나열한다.
    vault_root = tmp_path / "vault"
    _write_schema(vault_root)
    (vault_root / "index.md").write_text(
        "# Wiki Index\n\n## Concepts\n- [[Agent Memory]]\n",
        encoding="utf-8",
    )
    _write_raw_note(vault_root / "raw" / "articles" / "source.md", "Source body\n")
    _write_synthesized_note(
        vault_root / "concepts" / "agent-memory.md",
        title="Agent Memory",
        page_type="concept",
        tags=["agent-memory"],
        sources=["raw/articles/source.md"],
        body="# Agent Memory\n\nTitle link in index.\n",
    )

    # When: wiki context를 만든다.
    context = VaultSchemaService(
        note_repository=VaultNoteRepository(root=vault_root)
    ).wiki_context()

    # Then: title wikilink가 단일 page로 해석되면 indexed로 본다.
    page = next(page for page in context.wiki_map.pages if page.path == "concepts/agent-memory.md")
    assert page.indexed is True
    assert "unindexed_page" not in {issue.code for issue in context.issue_candidates}


def test_wiki_context_does_not_index_ambiguous_title_wikilink(
    tmp_path: Path,
) -> None:
    # Given: 같은 title을 가진 page가 둘 있고 index.md는 title만 링크한다.
    vault_root = tmp_path / "vault"
    _write_schema(vault_root)
    (vault_root / "index.md").write_text("- [[Agent Memory]]\n", encoding="utf-8")
    _write_raw_note(vault_root / "raw" / "articles" / "source.md", "Source body\n")
    _write_synthesized_note(
        vault_root / "concepts" / "agent-memory.md",
        title="Agent Memory",
        page_type="concept",
        tags=["agent-memory"],
        sources=["raw/articles/source.md"],
        body="# Agent Memory\n",
    )
    _write_synthesized_note(
        vault_root / "concepts" / "agent-memory-alt.md",
        title="Agent Memory",
        page_type="concept",
        tags=["agent-memory"],
        sources=["raw/articles/source.md"],
        body="# Agent Memory\n",
    )

    # When: wiki context를 만든다.
    context = VaultSchemaService(
        note_repository=VaultNoteRepository(root=vault_root)
    ).wiki_context()

    # Then: title이 여러 page에 매칭되면 특정 page가 indexed라고 단정하지 않는다.
    pages = {page.path: page for page in context.wiki_map.pages}
    assert pages["concepts/agent-memory.md"].indexed is False
    assert pages["concepts/agent-memory-alt.md"].indexed is False


def test_wiki_context_surfaces_map_link_issues_and_update_suggestions(
    tmp_path: Path,
) -> None:
    # Given: 연결이 일부 끊긴 synthesized page들과 미반영 raw source가 있는 vault가 있다.
    vault_root = tmp_path / "vault"
    _write_schema(vault_root)
    (vault_root / "index.md").write_text(
        "# Wiki Index\n\n## Concepts\n- [[agent-memory]] - Agent memory overview\n",
        encoding="utf-8",
    )
    (vault_root / "log.md").write_text("# Wiki Log\n", encoding="utf-8")
    _write_raw_note(vault_root / "raw" / "articles" / "karpathy.md", "Karpathy body\n")
    _write_raw_note(vault_root / "raw" / "articles" / "unused.md", "Unused raw body\n")
    _write_synthesized_note(
        vault_root / "concepts" / "agent-memory.md",
        title="Agent Memory",
        page_type="concept",
        tags=["agent-memory"],
        sources=["raw/articles/karpathy.md"],
        body="# Agent Memory\n\nConnects to [[hermes-agent]] and [[missing-page]].\n",
    )
    _write_synthesized_note(
        vault_root / "entities" / "hermes-agent.md",
        title="Hermes Agent",
        page_type="entity",
        tags=["mcp"],
        sources=["raw/articles/karpathy.md"],
        body="# Hermes Agent\n\nNo backlink yet.\n",
    )
    _write_synthesized_note(
        vault_root / "concepts" / "orphan-topic.md",
        title="Orphan Topic",
        page_type="concept",
        tags=["verification"],
        sources=["raw/articles/karpathy.md"],
        body="# Orphan Topic\n\nNo cross-links yet.\n",
    )

    # When: MCP context-first workflow용 context를 만든다.
    context = VaultSchemaService(
        note_repository=VaultNoteRepository(root=vault_root)
    ).wiki_context()

    # Then: LLM은 현재 page map, link/consistency issue 후보, 업데이트 제안을 함께 받는다.
    assert context.wiki_map.pages_by_type == {
        "concept": ["concepts/agent-memory.md", "concepts/orphan-topic.md"],
        "entity": ["entities/hermes-agent.md"],
    }
    assert context.wiki_map.raw_sources == [
        "raw/articles/karpathy.md",
        "raw/articles/unused.md",
    ]
    pages = {page.path: page for page in context.wiki_map.pages}
    assert pages["concepts/agent-memory.md"].outbound_links == ["entities/hermes-agent.md"]
    assert pages["entities/hermes-agent.md"].inbound_links == ["concepts/agent-memory.md"]
    assert [entity.path for entity in context.entities] == ["entities/hermes-agent.md"]
    assert context.entities[0].title == "Hermes Agent"
    assert context.entities[0].inbound_links == ["concepts/agent-memory.md"]
    issue_codes = {issue.code for issue in context.issue_candidates}
    assert {
        "broken_wikilink",
        "missing_backlink",
        "orphan_page",
        "underlinked_page",
        "unindexed_page",
        "raw_source_without_synthesis",
    }.issubset(issue_codes)
    suggestions = {
        (suggestion.action, suggestion.path) for suggestion in context.update_suggestions
    }
    assert ("repair_wikilink", "concepts/agent-memory.md") in suggestions
    assert ("add_backlink", "entities/hermes-agent.md") in suggestions
    assert ("connect_or_archive_page", "concepts/orphan-topic.md") in suggestions
    assert ("add_index_entry", "entities/hermes-agent.md") in suggestions
    assert ("synthesize_or_link_raw_source", "raw/articles/unused.md") in suggestions


def test_wiki_context_resolves_wikilinks_by_page_title(tmp_path: Path) -> None:
    # Given: 다른 note가 path stem이 아닌 frontmatter title로 wikilink를 건다.
    vault_root = tmp_path / "vault"
    _write_schema(vault_root)
    (vault_root / "index.md").write_text("# Wiki Index\n", encoding="utf-8")
    _write_raw_note(vault_root / "raw" / "articles" / "source.md", "Source body\n")
    _write_synthesized_note(
        vault_root / "concepts" / "agent-memory.md",
        title="Agent Memory",
        page_type="concept",
        tags=["agent-memory"],
        sources=["raw/articles/source.md"],
        body="# Agent Memory\n\nTarget page.\n",
    )
    _write_synthesized_note(
        vault_root / "concepts" / "working-memory.md",
        title="Working Memory",
        page_type="concept",
        tags=["agent-memory"],
        sources=["raw/articles/source.md"],
        body="# Working Memory\n\nLinks to [[Agent Memory]].\n",
    )

    # When: wiki context를 만든다.
    context = VaultSchemaService(
        note_repository=VaultNoteRepository(root=vault_root)
    ).wiki_context()

    # Then: title-based Obsidian link를 broken link로 보고하지 않는다.
    pages = {page.path: page for page in context.wiki_map.pages}
    assert pages["concepts/working-memory.md"].outbound_links == ["concepts/agent-memory.md"]
    assert "broken_wikilink" not in {issue.code for issue in context.issue_candidates}


def test_wiki_context_counts_raw_source_url_as_referenced(tmp_path: Path) -> None:
    # Given: synthesized page가 raw path 대신 source URL을 sources에 사용한다.
    vault_root = tmp_path / "vault"
    _write_schema(vault_root)
    raw_body = "Source body\n"
    raw_path = vault_root / "raw" / "articles" / "source.md"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(
        f"""---
source_url: https://example.com/source
ingested: 2026-06-10
sha256: {compute_sha256(raw_body)}
---
{raw_body}""",
        encoding="utf-8",
    )
    _write_synthesized_note(
        vault_root / "concepts" / "agent-memory.md",
        title="Agent Memory",
        page_type="concept",
        tags=["agent-memory"],
        sources=["https://example.com/source"],
        body="# Agent Memory\n\nURL backed source.\n",
    )

    # When: wiki context를 만든다.
    context = VaultSchemaService(note_repository=VaultNoteRepository(root=vault_root)).wiki_context(
        include_index=False
    )

    # Then: URL이 raw source metadata와 일치하면 미사용 raw source로 보지 않는다.
    assert not any(
        issue.code == "raw_source_without_synthesis" and issue.path == "raw/articles/source.md"
        for issue in context.issue_candidates
    )


def test_reconcile_taxonomy_supports_dry_run_then_schema_apply(tmp_path: Path) -> None:
    # Given: page가 SCHEMA.md에 없는 tag를 사용 중이다.
    vault_root = tmp_path / "vault"
    _write_schema(vault_root)
    (vault_root / "concepts").mkdir()
    page_path = vault_root / "concepts" / "agent-harness.md"
    page_path.write_text(
        """---
title: Agent Harness
created: 2026-06-10
updated: 2026-06-10
type: concept
tags: [agent-harness]
sources: [raw/hermes/source.md]
confidence: medium
contested: false
---

# Agent Harness

Body that must not change.
""",
        encoding="utf-8",
    )
    schema_service = VaultSchemaService(note_repository=VaultNoteRepository(root=vault_root))
    before_page = page_path.read_text(encoding="utf-8")

    # When: dry-run 후 add decision을 apply한다.
    dry_run = schema_service.reconcile_taxonomy(apply=False)
    applied = schema_service.reconcile_taxonomy(
        apply=True,
        decisions={"add": ["agent-harness"]},
    )

    # Then: dry-run은 변경하지 않고, apply는 SCHEMA.md만 보정해 unknown tag를 제거한다.
    assert dry_run.dry_run is True
    assert dry_run.unknown_tags == ["agent-harness"]
    assert page_path.read_text(encoding="utf-8") == before_page
    assert applied.changed_files == ["SCHEMA.md"]
    assert "agent-harness" in (vault_root / "SCHEMA.md").read_text(encoding="utf-8")
    assert schema_service.validate_vault().summary.unknown_tags == 0


def test_reconcile_taxonomy_recomputes_unknown_tags_after_rename_apply(
    tmp_path: Path,
) -> None:
    # Given: page가 SCHEMA.md에 없는 tag를 사용 중이고 rename 대상은 schema에 있다.
    vault_root = tmp_path / "vault"
    _write_schema(vault_root)
    page_path = vault_root / "concepts" / "agent-harness.md"
    _write_synthesized_note(
        page_path,
        title="Agent Harness",
        page_type="concept",
        tags=["agent-harness"],
        sources=["raw/hermes/source.md"],
        body="# Agent Harness\n",
    )
    schema_service = VaultSchemaService(note_repository=VaultNoteRepository(root=vault_root))

    # When: unknown tag를 schema에 이미 있는 tag로 rename apply한다.
    applied = schema_service.reconcile_taxonomy(
        apply=True,
        decisions={"rename": {"agent-harness": "agent-memory"}},
    )

    # Then: apply 이전 tag_usage 때문에 이전 tag를 unresolved로 남기지 않는다.
    assert applied.unknown_tags == []
    assert applied.tag_usage_counts == {"agent-memory": 1}
    assert schema_service.validate_vault().summary.unknown_tags == 0


def test_reconcile_taxonomy_does_not_treat_invalid_add_tags_as_allowed(
    tmp_path: Path,
) -> None:
    # Given: page가 TAG_PATTERN에 맞지 않는 tag를 사용 중이다.
    vault_root = tmp_path / "vault"
    _write_schema(vault_root)
    _write_synthesized_note(
        vault_root / "concepts" / "agent-review.md",
        title="Agent Review",
        page_type="concept",
        tags=["needs review"],
        sources=["raw/hermes/source.md"],
        body="# Agent Review\n",
    )
    schema_service = VaultSchemaService(note_repository=VaultNoteRepository(root=vault_root))

    # When: invalid tag를 add decision으로 전달한다.
    applied = schema_service.reconcile_taxonomy(
        apply=True,
        decisions={"add": ["needs review"]},
    )

    # Then: schema에 실제로 추가되지 않는 tag를 resolved로 취급하지 않는다.
    assert applied.unknown_tags == ["needs review"]
    assert applied.changed_files == []
    assert "needs review" not in (vault_root / "SCHEMA.md").read_text(encoding="utf-8")


def test_reconcile_taxonomy_does_not_add_unused_rename_target(
    tmp_path: Path,
) -> None:
    # Given: rename old tag가 어떤 page에서도 사용되지 않는다.
    vault_root = tmp_path / "vault"
    _write_schema(vault_root)
    _write_synthesized_note(
        vault_root / "concepts" / "agent-memory.md",
        title="Agent Memory",
        page_type="concept",
        tags=["agent-memory"],
        sources=["raw/hermes/source.md"],
        body="# Agent Memory\n",
    )
    schema_service = VaultSchemaService(note_repository=VaultNoteRepository(root=vault_root))

    # When: 사용되지 않는 old tag에 대한 rename decision을 apply한다.
    applied = schema_service.reconcile_taxonomy(
        apply=True,
        decisions={"rename": {"typo-old": "unused-target"}},
    )

    # Then: note rewrite가 없는 rename target을 taxonomy에 추가하지 않는다.
    assert applied.changed_files == []
    assert "unused-target" not in (vault_root / "SCHEMA.md").read_text(encoding="utf-8")


def test_reconcile_taxonomy_apply_does_not_crash_when_schema_is_missing(
    tmp_path: Path,
) -> None:
    # Given: SCHEMA.md 없이 synthesized page만 있는 vault가 있다.
    vault_root = tmp_path / "vault"
    _write_synthesized_note(
        vault_root / "concepts" / "agent-memory.md",
        title="Agent Memory",
        page_type="concept",
        tags=["agent-memory"],
        sources=["raw/hermes/source.md"],
        body="# Agent Memory\n",
    )
    schema_service = VaultSchemaService(note_repository=VaultNoteRepository(root=vault_root))

    # When: missing schema 상태에서 add decision을 apply한다.
    applied = schema_service.reconcile_taxonomy(
        apply=True,
        decisions={"add": ["agent-memory"]},
    )

    # Then: 임의 SCHEMA.md를 생성하지 않고 미해결 tag를 응답으로 유지한다.
    assert applied.changed_files == []
    assert applied.unknown_tags == ["agent-memory"]
    assert not (vault_root / "SCHEMA.md").exists()
