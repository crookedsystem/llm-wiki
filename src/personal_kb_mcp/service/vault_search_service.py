from dataclasses import dataclass, field
from pathlib import Path

from personal_kb_mcp.domain.vault_note import compute_sha256
from personal_kb_mcp.domain.vault_search import (
    FRONTMATTER_BOUNDARY,
    MAX_SEARCH_LIMIT,
    QUERY_TOKEN_PATTERN,
    FrontmatterMetadata,
    LineMatch,
    NoteMetadata,
    NoteSearchResult,
    SearchQuery,
)
from personal_kb_mcp.infrastructure.repositories.vault_note_repository import VaultNoteRepository
from personal_kb_mcp.service.vault_search_score_service import VaultSearchScoreService


@dataclass(frozen=True)
class VaultSearchService:
    note_repository: VaultNoteRepository
    score_service: VaultSearchScoreService = field(default_factory=VaultSearchScoreService)

    def search_notes(
        self,
        query: str,
        *,
        limit: int = 10,
        path_prefix: str | None = None,
    ) -> list[NoteSearchResult]:
        """Vault 안 Markdown note를 검색해 관련도순 result DTO로 반환합니다."""
        search_query = _validate_search_request(query, limit)
        search_root = self.note_repository.resolve_search_root(path_prefix)
        terms = _query_terms(search_query.query)
        results: list[NoteSearchResult] = []

        for note_path in self.note_repository.markdown_notes(search_root):
            relative_path = self.note_repository.relative_path(note_path)
            content = self.note_repository.read_note(note_path)
            metadata = _extract_metadata(content)
            score = self.score_service.score_note(
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

        return sorted(results, key=lambda result: (-result.score, result.path))[
            : search_query.limit
        ]


def search_notes(
    vault_root: Path,
    query: str,
    *,
    limit: int = 10,
    path_prefix: str | None = None,
) -> list[NoteSearchResult]:
    return VaultSearchService(VaultNoteRepository(vault_root)).search_notes(
        query,
        limit=limit,
        path_prefix=path_prefix,
    )


def _validate_search_request(query: str, limit: int) -> SearchQuery:
    """검색어 공백과 limit 범위를 검증해 검색 엔진이 사용할 query DTO를 만듭니다."""
    normalized_query = query.strip()
    if not normalized_query:
        raise ValueError("query must not be empty")
    if not 1 <= limit <= MAX_SEARCH_LIMIT:
        raise ValueError(f"limit must be between 1 and {MAX_SEARCH_LIMIT}")
    return SearchQuery(query=normalized_query, limit=limit)


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
