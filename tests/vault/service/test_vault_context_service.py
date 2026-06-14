from pathlib import Path

from vault.infrastructure.repository.vault_note_repository import VaultNoteRepository
from vault.service.command.context_command import ContextCommand
from vault.service.vault_context_service import VaultContextService


def _write_note(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _context_service(vault_root: Path) -> VaultContextService:
    return VaultContextService(note_repository=VaultNoteRepository(root=vault_root))


def test_context는_깨진_link와_연결대상과_근거검색어를_반환한다(
    tmp_path: Path,
) -> None:
    # Given: orientation 파일, entity anchor, domain rule, 깨진 wikilink가 있는 vault가 있다.
    vault_root = tmp_path / "vault"
    _write_note(
        vault_root / "SCHEMA.md",
        "---\n"
        "title: Wiki Schema\n"
        "type: schema\n"
        "tags: [llm-wiki]\n"
        "---\n\n"
        "# Wiki Schema\n\nlink rules\n",
    )
    _write_note(vault_root / "index.md", "# Wiki Index\n\nsample catalog\n")
    _write_note(vault_root / "log.md", "# Wiki Log\n\nrecent sample changes\n")
    _write_note(
        vault_root / "entities" / "sample-api.md",
        "---\n"
        "title: sample-api\n"
        "type: entity\n"
        "tags: [project-context, sample-api]\n"
        "---\n\n"
        "# sample-api\n\nsample chat service repository context\n",
    )
    _write_note(
        vault_root / "concepts" / "sample-chat-domain-rules.md",
        "---\n"
        "title: sample chat domain rules\n"
        "type: concept\n"
        "tags: [domain-rule, sample-api]\n"
        "---\n\n"
        "# sample chat domain rules\n\nsample chat secret room rule\n",
    )
    _write_note(
        vault_root / "queries" / "sample-chat.md",
        "---\n"
        "title: sample chat investigation\n"
        "type: query\n"
        "tags: [sample-api]\n"
        "---\n\n"
        "# sample chat investigation\n\nRelated: [[missing-room-rule]]\n",
    )

    # When: prompt mode context를 요청한다.
    result = _context_service(vault_root).context(
        ContextCommand(query="sample chat domain", mode="prompt", limit=10)
    )

    # Then: context는 snippet이 아닌 연결 작업용 최소 metadata를 반환한다.
    assert result.mode == "prompt"
    assert [reference.path for reference in result.orientation] == [
        "SCHEMA.md",
        "index.md",
        "log.md",
    ]
    assert result.broken_links[0].source_path == "queries/sample-chat.md"
    assert result.broken_links[0].normalized_target == "missing-room-rule"
    assert result.broken_links[0].suggested_path == "concepts/missing-room-rule.md"
    assert result.broken_links[0].followup_search == "missing-room-rule"
    target_by_path = {target.path: target for target in result.link_targets}
    assert target_by_path["entities/sample-api.md"].relation == "entity_anchor"
    assert target_by_path["concepts/sample-chat-domain-rules.md"].relation == "domain_rule"
    assert all(target.followup_search for target in result.link_targets)
    assert any("kb_search_notes" in usage for usage in result.usage)
    assert any("stable link anchors" in criterion for criterion in result.entity_guidance.criteria)


def test_context는_이미_연결되지_않은_관련_note_link를_제안한다(tmp_path: Path) -> None:
    # Given: query note와 entity note가 같은 tag를 공유하지만 아직 wikilink로 연결되지 않았다.
    vault_root = tmp_path / "vault"
    _write_note(
        vault_root / "entities" / "llm-wiki-mcp.md",
        "---\n"
        "title: llm-wiki-mcp\n"
        "type: entity\n"
        "tags: [llm-wiki-mcp]\n"
        "---\n\n"
        "# llm-wiki-mcp\n\ncontext graph tool\n",
    )
    _write_note(
        vault_root / "queries" / "context-tool.md",
        "---\n"
        "title: context tool design\n"
        "type: query\n"
        "tags: [llm-wiki-mcp]\n"
        "---\n\n"
        "# context tool design\n\ncontext graph tool should expose link candidates\n",
    )

    # When: prewrite mode context를 요청한다.
    result = _context_service(vault_root).context(
        ContextCommand(query="llm wiki mcp context graph", mode="prewrite", limit=5)
    )

    # Then: source hash와 target path를 포함한 연결 제안이 나온다.
    assert result.broken_links == []
    assert result.suggested_links
    suggestion = result.suggested_links[0]
    assert suggestion.source_path == "queries/context-tool.md"
    assert suggestion.target_path == "entities/llm-wiki-mcp.md"
    assert suggestion.relation == "add_link_to_entity_anchor"
    assert "shared tags" in suggestion.reason
    assert suggestion.source_content_hash
    assert suggestion.followup_search


def test_context는_기존_wikilink가_있으면_중복_연결을_제안하지_않는다(
    tmp_path: Path,
) -> None:
    # Given: query note가 이미 entity note를 wikilink로 참조한다.
    vault_root = tmp_path / "vault"
    _write_note(
        vault_root / "entities" / "llm-wiki-mcp.md",
        "---\ntitle: llm-wiki-mcp\ntype: entity\ntags: [llm-wiki-mcp]\n---\n\n# llm-wiki-mcp\n",
    )
    _write_note(
        vault_root / "queries" / "context-tool.md",
        "---\n"
        "title: context tool design\n"
        "type: query\n"
        "tags: [llm-wiki-mcp]\n"
        "---\n\n"
        "# context tool design\n\nSee [[entities/llm-wiki-mcp]].\n",
    )

    # When: context를 요청한다.
    result = _context_service(vault_root).context(
        ContextCommand(query="llm wiki mcp context graph", mode="prewrite", limit=5)
    )

    # Then: 이미 존재하는 link는 중복 제안하지 않는다.
    assert result.suggested_links == []


def test_context는_path_prefix로_연결_source와_target을_좁히되_orientation은_유지한다(
    tmp_path: Path,
) -> None:
    # Given: orientation 파일과 entities 안의 target, concepts 안의 별도 note가 있다.
    vault_root = tmp_path / "vault"
    _write_note(vault_root / "SCHEMA.md", "# Wiki Schema\n\nsample schema\n")
    _write_note(vault_root / "index.md", "# Wiki Index\n\nsample index\n")
    _write_note(vault_root / "log.md", "# Wiki Log\n\nsample log\n")
    _write_note(
        vault_root / "entities" / "sample-api.md",
        "---\n"
        "title: sample-api\n"
        "type: entity\n"
        "tags: [sample-api]\n"
        "---\n\n"
        "# sample-api\n\nsample project repository service\n",
    )
    _write_note(
        vault_root / "concepts" / "sample-domain.md",
        "---\n"
        "title: sample domain\n"
        "type: concept\n"
        "tags: [sample-api]\n"
        "---\n\n"
        "# sample domain\n\nsample project repository service\n",
    )

    # When: caller가 entities prefix로 context graph 범위를 좁힌다.
    result = _context_service(vault_root).context(
        ContextCommand(query="sample", mode="prompt", limit=8, path_prefix="entities")
    )

    # Then: orientation은 유지되고 link target은 prefix 안 note만 반환된다.
    assert [reference.path for reference in result.orientation] == [
        "SCHEMA.md",
        "index.md",
        "log.md",
    ]
    assert [target.path for target in result.link_targets] == ["entities/sample-api.md"]
