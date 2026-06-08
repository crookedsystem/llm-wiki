from pathlib import Path

from personal_kb_mcp.vault.notes import compute_sha256
from personal_kb_mcp.vault.paths import DEFAULT_DENIED_NAMES, VaultPathError
from personal_kb_mcp.vault.search_constants import FRONTMATTER_BOUNDARY, QUERY_TOKEN_PATTERN
from personal_kb_mcp.vault.search_dto import (
    FrontmatterMetadata,
    LineMatch,
    NoteMetadata,
    NoteSearchResult,
)
from personal_kb_mcp.vault.search_score import SearchScoreService
from personal_kb_mcp.vault.search_validation import validate_search_request

_SEARCH_SCORE_SERVICE = SearchScoreService()


def search_notes(
    vault_root: Path,
    query: str,
    *,
    limit: int = 10,
    path_prefix: str | None = None,
) -> list[NoteSearchResult]:
    """Vault 안 Markdown note를 검색해 관련도순 result DTO로 반환합니다."""
    search_query = validate_search_request(query, limit)

    root = vault_root.expanduser().resolve()
    search_root = _resolve_path_prefix(root, path_prefix)
    terms = _query_terms(search_query.query)
    results: list[NoteSearchResult] = []

    for note_path in _markdown_notes(root, search_root):
        relative_path = note_path.relative_to(root).as_posix()
        content = note_path.read_text(encoding="utf-8")
        metadata = _extract_metadata(content)
        score = _SEARCH_SCORE_SERVICE.score_note(
            relative_path,
            content,
            metadata,
            search_query.query,
            terms,
        )
        if score <= 0:
            continue
        results.append(
            NoteSearchResult(
                path=relative_path,
                title=metadata.title,
                page_type=metadata.page_type,
                tags=metadata.tags,
                score=round(score, 3),
                content_hash=compute_sha256(content),
                matches=_line_matches(content, search_query.query, terms),
            )
        )

    return sorted(results, key=lambda result: (-result.score, result.path))[: search_query.limit]


def _resolve_path_prefix(root: Path, path_prefix: str | None) -> Path:
    """path_prefix를 vault 내부 검색 시작점으로 바꾸고 외부 경로 escape를 막습니다."""
    if path_prefix is None or path_prefix.strip() in {"", "."}:
        return root

    relative_prefix = Path(path_prefix)
    if relative_prefix.is_absolute():
        raise VaultPathError("path_prefix must be relative to the vault")

    resolved_prefix = (root / relative_prefix).resolve()
    try:
        resolved_prefix.relative_to(root)
    except ValueError as error:
        raise VaultPathError(f"path_prefix escapes outside vault: {resolved_prefix}") from error

    if _uses_denied_directory(root, resolved_prefix):
        raise VaultPathError("path_prefix uses denied vault directory")
    return resolved_prefix


def _markdown_notes(root: Path, search_root: Path) -> list[Path]:
    if not search_root.exists():
        return []
    if search_root.is_file():
        candidates = [search_root] if search_root.suffix == ".md" else []
    else:
        candidates = list(search_root.rglob("*.md"))
    return sorted(path for candidate in candidates if (path := _searchable_note(root, candidate)))


def _searchable_note(root: Path, candidate: Path) -> Path | None:
    if not candidate.is_file():
        return None
    resolved_candidate = candidate.resolve()
    try:
        resolved_candidate.relative_to(root)
    except ValueError:
        return None
    if _uses_denied_directory(root, resolved_candidate):
        return None
    return resolved_candidate


def _uses_denied_directory(root: Path, path: Path) -> bool:
    return any(part in DEFAULT_DENIED_NAMES for part in path.relative_to(root).parts)


def _query_terms(query: str) -> list[str]:
    terms = [token.lower() for token in QUERY_TOKEN_PATTERN.findall(query) if len(token) > 1]
    return terms or [query.lower()]


def _extract_metadata(content: str) -> NoteMetadata:
    frontmatter = _frontmatter(content)
    frontmatter_metadata = _frontmatter_metadata(frontmatter)
    headings = _headings(content)
    title = frontmatter_metadata.title or (headings[0] if headings else None)
    return NoteMetadata(
        title=title,
        page_type=frontmatter_metadata.page_type,
        tags=frontmatter_metadata.tags,
        headings=headings,
    )


def _frontmatter(content: str) -> str:
    lines = content.splitlines()
    if not lines or lines[0].strip() != FRONTMATTER_BOUNDARY:
        return ""
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == FRONTMATTER_BOUNDARY:
            return "\n".join(lines[1:index])
    return ""


def _frontmatter_metadata(frontmatter: str) -> FrontmatterMetadata:
    """지원하는 YAML front matter 필드만 DTO로 옮기고 나머지 raw 필드는 무시합니다."""
    title: str | None = None
    page_type: str | None = None
    tags: list[str] = []
    lines = frontmatter.splitlines()

    for index, line in enumerate(lines):
        key, separator, raw_value = line.partition(":")
        if not separator:
            continue
        key_name = key.strip()
        if key_name == "title" and raw_value.strip():
            title = _normalize_frontmatter_scalar(raw_value)
        elif key_name == "type" and raw_value.strip():
            page_type = _normalize_frontmatter_scalar(raw_value)
        elif key_name == "tags":
            tags = _frontmatter_tags(lines, index, raw_value)

    return FrontmatterMetadata(title=title, page_type=page_type, tags=tags)


def _frontmatter_tags(lines: list[str], index: int, raw_value: str) -> list[str]:
    stripped_value = raw_value.strip()
    if stripped_value.startswith("[") and stripped_value.endswith("]"):
        return [
            _normalize_frontmatter_scalar(part)
            for part in stripped_value[1:-1].split(",")
            if part.strip()
        ]

    tags: list[str] = []
    for following_line in lines[index + 1 :]:
        stripped_line = following_line.strip()
        if not stripped_line.startswith("-"):
            break
        tag = _normalize_frontmatter_scalar(stripped_line[1:])
        if tag:
            tags.append(tag)
    return tags


def _normalize_frontmatter_scalar(raw_value: str) -> str:
    return raw_value.strip().strip("'\"")


def _headings(content: str) -> list[str]:
    headings: list[str] = []
    for line in content.splitlines():
        stripped_line = line.strip()
        if stripped_line.startswith("#"):
            heading = stripped_line.lstrip("#").strip()
            if heading:
                headings.append(heading)
    return headings


def _line_matches(content: str, query: str, terms: list[str]) -> list[LineMatch]:
    """검색어가 걸린 줄 주변을 최대 3개 뽑아 결과 미리보기 snippet으로 제공합니다."""
    lines = content.splitlines()
    query_lower = query.lower()
    matches: list[LineMatch] = []
    for index, line in enumerate(lines):
        line_lower = line.lower()
        if query_lower in line_lower or any(term in line_lower for term in terms):
            matches.append(LineMatch(line=index + 1, snippet=_snippet(lines, index)))
        if len(matches) >= 3:
            break

    if matches:
        return matches

    for index, line in enumerate(lines):
        if line.strip():
            return [LineMatch(line=index + 1, snippet=_snippet(lines, index))]
    return []


def _snippet(lines: list[str], center_index: int) -> str:
    """중심 줄 앞뒤 한 줄을 합쳐 MCP search response에 넣을 짧은 문맥을 만듭니다."""
    start = max(0, center_index - 1)
    end = min(len(lines), center_index + 2)
    snippet = "\n".join(line.strip() for line in lines[start:end] if line.strip())
    return snippet[:500]
