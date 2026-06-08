from typing_extensions import TypedDict

from personal_kb_mcp.domain.vault.service.result.search_notes_result import (
    NoteSearchResult,
    SearchNotesResult,
)


class LineMatchResponse(TypedDict):
    line: int
    snippet: str


class NoteSearchResultResponse(TypedDict):
    path: str
    title: str | None
    page_type: str | None
    tags: list[str]
    score: float
    content_hash: str
    matches: list[LineMatchResponse]


class SearchNotesResponse(TypedDict):
    query: str
    count: int
    results: list[NoteSearchResultResponse]


def search_notes_response(result: SearchNotesResult) -> SearchNotesResponse:
    return {
        "query": result.query,
        "count": result.count,
        "results": [_note_search_result_response(note) for note in result.results],
    }


def _note_search_result_response(result: NoteSearchResult) -> NoteSearchResultResponse:
    return {
        "path": result.path,
        "title": result.title,
        "page_type": result.page_type,
        "tags": result.tags,
        "score": result.score,
        "content_hash": result.content_hash,
        "matches": [{"line": match.line, "snippet": match.snippet} for match in result.matches],
    }
