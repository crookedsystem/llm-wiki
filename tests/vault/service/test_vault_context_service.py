from pathlib import Path

from vault.infrastructure.repository.vault_note_repository import VaultNoteRepository
from vault.service.command.context_command import ContextCommand
from vault.service.vault_context_service import VaultContextService
from vault.service.vault_search_service import VaultSearchService


def _write_note(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _context_service(vault_root: Path) -> VaultContextService:
    search_service = VaultSearchService(note_repository=VaultNoteRepository(root=vault_root))
    return VaultContextService(search_service=search_service)


def test_context는_prompt_작업에_필요한_bucket과_entity_기준을_반환한다(
    tmp_path: Path,
) -> None:
    # Given: orientation, entity, convention, domain rule note가 있는 vault가 있다.
    vault_root = tmp_path / "vault"
    _write_note(
        vault_root / "SCHEMA.md",
        "---\n"
        "title: Wiki Schema\n"
        "type: schema\n"
        "tags: [llm-wiki]\n"
        "---\n\n"
        "# Wiki Schema\n\nfanplus chat domain rule tag taxonomy\n",
    )
    _write_note(
        vault_root / "entities" / "fanplus-api.md",
        "---\n"
        "title: fanplus-api\n"
        "type: entity\n"
        "tags: [project-context, fanplus-api]\n"
        "---\n\n"
        "# fanplus-api\n\nfanplus chat service repository context\n",
    )
    _write_note(
        vault_root / "concepts" / "fanplus-api-code-conventions.md",
        "---\n"
        "title: fanplus-api code conventions\n"
        "type: concept\n"
        "tags: [code-style, maintainability, fanplus-api]\n"
        "---\n\n"
        "# fanplus-api code conventions\n\nfanplus chat code convention service style\n",
    )
    _write_note(
        vault_root / "concepts" / "fanplus-chat-domain-rules.md",
        "---\n"
        "title: fanplus chat domain rules\n"
        "type: concept\n"
        "tags: [domain-rule, architecture, fanplus-api]\n"
        "---\n\n"
        "# fanplus chat domain rules\n\nfanplus chat domain rule secret room\n",
    )

    # When: prompt mode context를 요청한다.
    result = _context_service(vault_root).context(
        ContextCommand(query="fanplus chat domain", mode="prompt", limit=8)
    )

    # Then: bucket별 note가 중복 없이 반환되고 entity 생성 기준이 함께 제공된다.
    assert result.mode == "prompt"
    assert result.count >= 4
    section_by_name = {section.name: section for section in result.sections}
    assert section_by_name["orientation"].notes[0].path == "SCHEMA.md"
    assert section_by_name["entity_candidates"].notes[0].path == "entities/fanplus-api.md"
    paths = [note.path for section in result.sections for note in section.notes]
    assert len(paths) == len(set(paths))
    assert any("named project" in criterion for criterion in result.entity_guidance.criteria)
    assert "prewrite" in " ".join(result.entity_guidance.prewrite_checks)


def test_context는_limit_안에서_중복_path를_한번만_포함한다(tmp_path: Path) -> None:
    # Given: 하나의 note가 여러 bucket query에 동시에 걸린다.
    vault_root = tmp_path / "vault"
    _write_note(
        vault_root / "entities" / "llm-wiki-mcp.md",
        "---\n"
        "title: llm-wiki-mcp\n"
        "type: entity\n"
        "tags: [project-context, repository, code-style, domain-rule]\n"
        "---\n\n"
        "# llm-wiki-mcp\n\nllm wiki mcp context tool code convention domain rule\n",
    )

    # When: 작은 limit으로 context를 요청한다.
    result = _context_service(vault_root).context(
        ContextCommand(query="llm wiki mcp context tool", mode="prewrite", limit=3)
    )

    # Then: 같은 path는 한 번만 포함되고 limit을 넘지 않는다.
    paths = [note.path for section in result.sections for note in section.notes]
    assert paths == ["entities/llm-wiki-mcp.md"]
    assert result.count == 1
    assert result.count <= 3


def test_context는_stop_orientation에_schema_index_log를_모두_포함한다(
    tmp_path: Path,
) -> None:
    # Given: end-of-turn wiki update 전에 확인해야 하는 세 orientation 파일이 모두 있다.
    vault_root = tmp_path / "vault"
    _write_note(
        vault_root / "SCHEMA.md",
        "# Wiki Schema\n\nSCHEMA index log update rules\n",
    )
    _write_note(
        vault_root / "index.md",
        "# Wiki Index\n\nSCHEMA index log page catalog\n",
    )
    _write_note(
        vault_root / "log.md",
        "# Wiki Log\n\nSCHEMA index log recent changes\n",
    )

    # When: stop mode context를 요청한다.
    result = _context_service(vault_root).context(
        ContextCommand(query="wiki update", mode="stop", limit=8)
    )

    # Then: log.md도 orientation 필수 파일로 포함된다.
    orientation = next(section for section in result.sections if section.name == "orientation")
    assert [note.path for note in orientation.notes] == ["SCHEMA.md", "index.md", "log.md"]


def test_context는_path_prefix가_있어도_orientation_explicit_path를_유지한다(
    tmp_path: Path,
) -> None:
    # Given: orientation 파일과 같은 query에 걸릴 entity note가 함께 있다.
    vault_root = tmp_path / "vault"
    _write_note(
        vault_root / "SCHEMA.md",
        "# Wiki Schema\n\nSCHEMA index log fanplus rules\n",
    )
    _write_note(
        vault_root / "index.md",
        "# Wiki Index\n\nSCHEMA index log fanplus catalog\n",
    )
    _write_note(
        vault_root / "log.md",
        "# Wiki Log\n\nSCHEMA index log fanplus recent changes\n",
    )
    _write_note(
        vault_root / "entities" / "fanplus-api.md",
        "---\n"
        "title: fanplus-api\n"
        "type: entity\n"
        "tags: [project-context, fanplus-api]\n"
        "---\n\n"
        "# fanplus-api\n\nfanplus project repository service\n",
    )

    # When: caller가 entities prefix로 일반 검색 범위를 좁힌다.
    result = _context_service(vault_root).context(
        ContextCommand(query="fanplus", mode="prompt", limit=8, path_prefix="entities")
    )

    # Then: orientation은 고정 파일을 유지하고 entity 후보는 잘못 dedupe되지 않는다.
    section_by_name = {section.name: section for section in result.sections}
    assert [note.path for note in section_by_name["orientation"].notes] == [
        "SCHEMA.md",
        "index.md",
        "log.md",
    ]
    assert [note.path for note in section_by_name["entity_candidates"].notes] == [
        "entities/fanplus-api.md"
    ]
