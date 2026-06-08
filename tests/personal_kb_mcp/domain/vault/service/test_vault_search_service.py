from pathlib import Path

import pytest

from personal_kb_mcp.domain.vault.entity.vault_path import VaultPathError
from personal_kb_mcp.domain.vault.service.vault_search_service import search_notes


def test_search_notes는_llm_wiki_구조를_반영해_synthesized_page를_우선한다(
    tmp_path: Path,
) -> None:
    # Given: index, synthesized concept page, raw source가 있는 Markdown LLM Wiki vault가 있다.
    vault_root = tmp_path / "vault"
    (vault_root / "concepts").mkdir(parents=True)
    (vault_root / "raw" / "articles").mkdir(parents=True)
    (vault_root / "index.md").write_text(
        "# Wiki Index\n\n- [[agent-memory]] — agent memory overview\n",
        encoding="utf-8",
    )
    (vault_root / "concepts" / "agent-memory.md").write_text(
        "---\n"
        "title: Agent Memory\n"
        "type: concept\n"
        "tags: [agent, memory, llm-wiki]\n"
        "sources: [raw/articles/agent-memory.md]\n"
        "---\n\n"
        "# Agent Memory\n\n"
        "LLM Wiki pages compound agent memory through linked Markdown notes.\n"
        "Related: [[retrieval]]\n",
        encoding="utf-8",
    )
    (vault_root / "raw" / "articles" / "agent-memory.md").write_text(
        "# Source\n\nagent memory raw transcript\n",
        encoding="utf-8",
    )

    # When: agent memory를 검색한다.
    results = search_notes(vault_root, "agent memory", limit=5)

    # Then: raw보다 synthesized concept page가 먼저 나오고 update용 hash/snippet도 제공된다.
    assert [result.path for result in results.results][:3] == [
        "concepts/agent-memory.md",
        "index.md",
        "raw/articles/agent-memory.md",
    ]
    concept = results.results[0]
    assert concept.title == "Agent Memory"
    assert concept.page_type == "concept"
    assert concept.tags == ["agent", "memory", "llm-wiki"]
    assert len(concept.content_hash) == 64
    assert concept.matches[0].line == 2
    assert "title: Agent Memory" in concept.matches[0].snippet


def test_search_notes는_frontmatter_tags_yaml_list_형식도_읽는다(tmp_path: Path) -> None:
    # Given: tags가 YAML list 형식으로 작성된 Markdown note가 있다.
    vault_root = tmp_path / "vault"
    (vault_root / "concepts").mkdir(parents=True)
    (vault_root / "concepts" / "agent-memory.md").write_text(
        "---\n"
        "title: Agent Memory\n"
        "type: concept\n"
        "tags:\n"
        "  - agent\n"
        "  - memory\n"
        "---\n\n"
        "# Agent Memory\n",
        encoding="utf-8",
    )

    # When: title로 검색한다.
    results = search_notes(vault_root, "agent memory")

    # Then: inline list가 아니어도 schema에 있는 tags DTO만 결과에 반영된다.
    assert results.results[0].tags == ["agent", "memory"]


def test_search_notes는_path_prefix와_거부된_디렉터리를_적용한다(tmp_path: Path) -> None:
    # Given: 검색 가능한 concepts note와 거부된 .obsidian note가 있다.
    vault_root = tmp_path / "vault"
    (vault_root / "concepts").mkdir(parents=True)
    (vault_root / ".obsidian").mkdir(parents=True)
    (vault_root / "concepts" / "retrieval.md").write_text(
        "# Retrieval\n\nSearch compiled wiki pages.\n",
        encoding="utf-8",
    )
    (vault_root / ".obsidian" / "hidden.md").write_text(
        "# Retrieval private config\n",
        encoding="utf-8",
    )

    # When: concepts prefix로 검색한다.
    results = search_notes(vault_root, "retrieval", path_prefix="concepts")

    # Then: prefix 안의 markdown만 반환되고 denied directory는 노출되지 않는다.
    assert [result.path for result in results.results] == ["concepts/retrieval.md"]


def test_search_notes는_query_match가_없으면_structure_boost만으로_결과를_만들지_않는다(
    tmp_path: Path,
) -> None:
    # Given: 구조상 boost 대상인 index와 synthesized page만 있는 vault가 있다.
    vault_root = tmp_path / "vault"
    (vault_root / "concepts").mkdir(parents=True)
    (vault_root / "index.md").write_text("# Wiki Index\n", encoding="utf-8")
    (vault_root / "concepts" / "agent-memory.md").write_text(
        "# Agent Memory\n\nRelevant agent page.\n",
        encoding="utf-8",
    )

    # When: 어느 note에도 없는 query로 검색한다.
    results = search_notes(vault_root, "nomatch")

    # Then: index/concepts boost만으로 관련 없는 결과를 반환하지 않는다.
    assert results.results == []


def test_search_notes는_vault_밖을_가리키는_markdown_symlink를_건너뛴다(
    tmp_path: Path,
) -> None:
    # Given: vault 내부에 외부 Markdown 파일을 가리키는 symlink가 있다.
    vault_root = tmp_path / "vault"
    vault_root.mkdir()
    outside_note = tmp_path / "outside.md"
    outside_note.write_text("# External\n\nexternal-only term\n", encoding="utf-8")
    symlink_path = vault_root / "external.md"
    try:
        symlink_path.symlink_to(outside_note)
    except (NotImplementedError, OSError):
        pytest.skip("filesystem does not support symlinks")

    # When: symlink target에만 있는 query로 검색한다.
    results = search_notes(vault_root, "external-only")

    # Then: vault 밖 파일은 검색하지 않고 전체 search도 실패하지 않는다.
    assert results.results == []


@pytest.mark.parametrize("limit", [0, 51])
def test_search_notes는_limit_범위를_검증한다(tmp_path: Path, limit: int) -> None:
    # Given: 빈 vault가 있다.
    vault_root = tmp_path / "vault"

    # When / Then: 범위를 벗어난 limit은 명확한 오류를 낸다.
    with pytest.raises(ValueError, match="limit must be between"):
        search_notes(vault_root, "query", limit=limit)


def test_search_notes는_빈_query를_거부한다(tmp_path: Path) -> None:
    # Given: 빈 vault가 있다.
    vault_root = tmp_path / "vault"

    # When / Then: 공백뿐인 query는 검색 전에 명확한 오류를 낸다.
    with pytest.raises(ValueError, match="query must not be empty"):
        search_notes(vault_root, "  \n\t  ")


def test_search_notes는_vault_밖_prefix를_거부한다(tmp_path: Path) -> None:
    # Given: vault root가 있다.
    vault_root = tmp_path / "vault"

    # When / Then: path_prefix는 vault 밖으로 escape할 수 없다.
    with pytest.raises(VaultPathError, match="escapes outside vault"):
        search_notes(vault_root, "query", path_prefix="../outside")
