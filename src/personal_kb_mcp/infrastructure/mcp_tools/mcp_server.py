from typing import Literal, cast

from mcp.server.fastmcp import FastMCP
from typing_extensions import TypedDict

from personal_kb_mcp.config import Settings
from personal_kb_mcp.domain.vault_search import NoteSearchResult
from personal_kb_mcp.runtime import create_runtime
from personal_kb_mcp.service.vault_search_service import VaultSearchService
from personal_kb_mcp.service.vault_write_service import VaultWriteService

McpLogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class WriteNoteToolResponse(TypedDict):
    path: str
    source_hash: str
    content_hash: str
    commit_hash: str | None


class LineMatchDocument(TypedDict):
    line: int
    snippet: str


class NoteSearchResultDocument(TypedDict):
    path: str
    title: str | None
    page_type: str | None
    tags: list[str]
    score: float
    content_hash: str
    matches: list[LineMatchDocument]


class SearchNotesToolResponse(TypedDict):
    query: str
    count: int
    results: list[NoteSearchResultDocument]


def create_mcp_server(
    settings: Settings,
    write_service: VaultWriteService | None = None,
    search_service: VaultSearchService | None = None,
) -> FastMCP[object]:
    if write_service is None or search_service is None:
        runtime = create_runtime(settings)
        resolved_write_service = write_service or runtime.write_service
        resolved_search_service = search_service or runtime.search_service
    else:
        resolved_write_service = write_service
        resolved_search_service = search_service

    server: FastMCP[object] = FastMCP(
        "personal-kb-mcp",
        host=settings.host,
        port=settings.port,
        streamable_http_path=settings.mcp_path,
        log_level=cast(McpLogLevel, settings.log_level.upper()),
    )

    @server.tool(
        description=(
            "Write a complete Markdown note inside the configured vault. "
            "Existing notes require the current content_hash as if_hash so agents do not "
            "overwrite a newer wiki revision by accident."
        )
    )
    async def kb_write_note(
        note_path: str,
        content: str,
        if_hash: str | None = None,
    ) -> WriteNoteToolResponse:
        result = await resolved_write_service.write_note(note_path, content, if_hash=if_hash)
        return {
            "path": result.path.as_posix(),
            "source_hash": result.source_hash,
            "content_hash": result.content_hash,
            "commit_hash": result.commit_hash,
        }

    @server.tool(
        description=(
            "Search Markdown notes in the configured LLM Wiki vault. Returns ranked note "
            "paths, titles, page types, tags, content_hash values for safe follow-up writes, "
            "and line snippets from matching wiki pages."
        )
    )
    def kb_search_notes(
        query: str,
        limit: int = 10,
        path_prefix: str | None = None,
    ) -> SearchNotesToolResponse:
        results = resolved_search_service.search_notes(
            query,
            limit=limit,
            path_prefix=path_prefix,
        )
        return {
            "query": query,
            "count": len(results),
            "results": [_note_search_result_document(result) for result in results],
        }

    return server


def _note_search_result_document(result: NoteSearchResult) -> NoteSearchResultDocument:
    return {
        "path": result.path,
        "title": result.title,
        "page_type": result.page_type,
        "tags": result.tags,
        "score": result.score,
        "content_hash": result.content_hash,
        "matches": [{"line": match.line, "snippet": match.snippet} for match in result.matches],
    }
