from pydantic import Field

from common.helper.note_metadata_helper import extract_note_metadata
from common.model import FrozenModel
from vault.constant.search import (
    MAX_SEARCH_LIMIT,
    QUERY_TOKEN_PATTERN,
)
from vault.entity.vault_note import compute_sha256
from vault.infrastructure.repository.vault_note_repository import (
    VaultNoteRepository,
)
from vault.service.command.search_notes_command import SearchNotesCommand
from vault.service.result.search_notes_result import (
    LineMatch,
    NoteSearchResult,
    SearchNotesResult,
)
from vault.service.vault_search_score_service import (
    VaultSearchScoreService,
)


class VaultSearchService(FrozenModel):
    note_repository: VaultNoteRepository
    score_service: VaultSearchScoreService = Field(default_factory=VaultSearchScoreService)

    def search_notes(self, command: SearchNotesCommand) -> SearchNotesResult:
        """Vault 안 Markdown note를 검색해 관련도순 result DTO로 반환합니다."""
        search_command = _validate_search_command(command)
        search_root = self.note_repository.resolve_search_root(search_command.path_prefix)
        terms = _query_terms(search_command.query)
        notes: list[NoteSearchResult] = []

        for note_path in self.note_repository.markdown_notes(search_root):
            relative_path = self.note_repository.relative_path(note_path)
            content = self.note_repository.read_note(note_path)
            metadata = extract_note_metadata(content)
            score = self.score_service.score_note(
                relative_path,
                content,
                metadata,
                search_command.query,
                terms,
            )
            if score <= 0:
                continue
            notes.append(
                NoteSearchResult(
                    path=relative_path,
                    title=metadata.title,
                    page_type=metadata.page_type,
                    tags=metadata.tags,
                    score=round(score, 3),
                    content_hash=compute_sha256(content),
                    matches=_line_matches(content, search_command.query, terms),
                )
            )

        results = sorted(notes, key=lambda result: (-result.score, result.path))[
            : search_command.limit
        ]
        return SearchNotesResult(query=search_command.query, count=len(results), results=results)


def _validate_search_command(command: SearchNotesCommand) -> SearchNotesCommand:
    """검색어 공백과 limit 범위를 검증해 service layer command DTO를 정규화합니다."""
    normalized_query = command.query.strip()
    if not normalized_query:
        raise ValueError("query must not be empty")
    if not 1 <= command.limit <= MAX_SEARCH_LIMIT:
        raise ValueError(f"limit must be between 1 and {MAX_SEARCH_LIMIT}")
    return SearchNotesCommand(
        query=normalized_query,
        limit=command.limit,
        path_prefix=command.path_prefix,
    )


def _query_terms(query: str) -> list[str]:
    terms = [token.lower() for token in QUERY_TOKEN_PATTERN.findall(query) if len(token) > 1]
    return terms or [query.lower()]


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
