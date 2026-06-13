from mcp.server.fastmcp import FastMCP

from vault.dto.request.context_request import ContextRequest
from vault.dto.request.search_notes_request import SearchNotesRequest
from vault.dto.request.write_note_request import WriteNoteRequest
from vault.dto.response.context_response import ContextResponse, context_response
from vault.dto.response.git_push_response import GitPushResponse, git_push_response
from vault.dto.response.search_notes_response import (
    SearchNotesResponse,
    search_notes_response,
)
from vault.dto.response.write_note_response import (
    WriteNoteResponse,
    write_note_response,
)
from vault.service.command.context_command import ContextMode
from vault.service.command.write_note_command import ConfidenceLevel, WikiNoteType
from vault.service.note_timestamp import NoteTimestamp
from vault.service.vault_context_service import VaultContextService
from vault.service.vault_git_push_service import VaultGitPushService
from vault.service.vault_search_service import VaultSearchService
from vault.service.vault_write_service import VaultWriteService


def register_vault_tools(
    server: FastMCP[object],
    write_service: VaultWriteService,
    search_service: VaultSearchService,
    context_service: VaultContextService,
    git_push_service: VaultGitPushService,
) -> None:
    @server.tool(
        description=(
            "Write a Markdown wiki note from structured fields. The tool renders YAML "
            "frontmatter, title heading, body, and provenance inside the configured vault. "
            "created and updated must be UTC ISO datetimes with seconds and trailing Z "
            "(YYYY-MM-DDTHH:MM:SSZ). "
            "Existing notes require the current content_hash as if_hash."
        )
    )
    async def kb_write_note(
        note_path: str,
        title: str,
        type: WikiNoteType,
        tags: list[str],
        sources: list[str],
        body: str,
        created: NoteTimestamp,
        updated: NoteTimestamp,
        confidence: ConfidenceLevel | None = None,
        contested: bool | None = None,
        if_hash: str | None = None,
    ) -> WriteNoteResponse:
        request = WriteNoteRequest(
            note_path=note_path,
            title=title,
            type=type,
            tags=tags,
            sources=sources,
            body=body,
            created=created,
            updated=updated,
            confidence=confidence,
            contested=contested,
            if_hash=if_hash,
        )
        result = await write_service.write_note(request.to_command())
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
        result = search_service.search_notes(request.to_command())
        return search_notes_response(result)

    @server.tool(
        description=(
            "Assemble sectioned wiki context for prompt, prewrite, or stop-hook use. "
            "Returns orientation, entity candidates, project context, code conventions, "
            "domain rules, direct matches, usage guidance, and entity creation criteria."
        )
    )
    def kb_context(
        query: str,
        mode: ContextMode = "prompt",
        limit: int = 16,
        path_prefix: str | None = None,
    ) -> ContextResponse:
        request = ContextRequest(
            query=query,
            mode=mode,
            limit=limit,
            path_prefix=path_prefix,
        )
        result = context_service.context(request.to_command())
        return context_response(result)

    @server.tool(
        description=(
            "Commit all pending vault changes with a UTC "
            "'YYYY-MM-DD HH:MM - vault sync' message and push origin to the current branch. "
            "The server checks GitHub CLI auth first, then falls back to git push."
        )
    )
    async def kb_push_vault() -> GitPushResponse:
        result = await git_push_service.push_vault()
        return git_push_response(result)
