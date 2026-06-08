from typing import Literal, cast

from mcp.server.fastmcp import FastMCP

from personal_kb_mcp.config import Settings
from personal_kb_mcp.domain.vault.dto.request.search_notes_request import SearchNotesRequest
from personal_kb_mcp.domain.vault.dto.request.write_note_request import WriteNoteRequest
from personal_kb_mcp.domain.vault.dto.response.search_notes_response import (
    SearchNotesResponse,
    search_notes_response,
)
from personal_kb_mcp.domain.vault.dto.response.write_note_response import (
    WriteNoteResponse,
    write_note_response,
)
from personal_kb_mcp.domain.vault.service.vault_search_service import VaultSearchService
from personal_kb_mcp.domain.vault.service.vault_write_service import VaultWriteService
from personal_kb_mcp.runtime import create_runtime

McpLogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


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
    ) -> WriteNoteResponse:
        request = WriteNoteRequest(note_path=note_path, content=content, if_hash=if_hash)
        result = await resolved_write_service.write_note(request.to_command())
        return write_note_response(result)

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
    ) -> SearchNotesResponse:
        request = SearchNotesRequest(query=query, limit=limit, path_prefix=path_prefix)
        result = resolved_search_service.search_notes(request.to_command())
        return search_notes_response(result)

    return server
