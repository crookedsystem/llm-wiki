from mcp.server.fastmcp import FastMCP

from vault.dto.request.search_notes_request import SearchNotesRequest
from vault.dto.request.write_note_request import WriteNoteRequest
from vault.dto.response.search_notes_response import (
    SearchNotesResponse,
    search_notes_response,
)
from vault.dto.response.write_note_response import (
    WriteNoteResponse,
    write_note_response,
)
from vault.service.result.schema_validation_result import VaultValidationResult
from vault.service.result.taxonomy_reconcile_result import TaxonomyReconcileResult
from vault.service.result.wiki_context_result import WikiContext
from vault.service.vault_schema_service import VaultSchemaService
from vault.service.vault_search_service import VaultSearchService
from vault.service.vault_write_service import VaultWriteService


def register_vault_tools(
    server: FastMCP[object],
    write_service: VaultWriteService,
    search_service: VaultSearchService,
    schema_service: VaultSchemaService,
) -> None:
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
            "Return a context bundle for schema-first LLM Wiki work: SCHEMA.md, index.md, "
            "recent log.md lines, parsed frontmatter/tag rules, page/link map, entity "
            "list, issue candidates, and update suggestions."
        )
    )
    def kb_wiki_context(
        recent_log_lines: int = 30,
        include_schema_rules: bool = True,
        include_index: bool = True,
    ) -> WikiContext:
        return schema_service.wiki_context(
            recent_log_lines=recent_log_lines,
            include_schema_rules=include_schema_rules,
            include_index=include_index,
        )

    @server.tool(
        description=(
            "Validate the configured LLM Wiki vault against the shared schema contract. "
            "Checks frontmatter, required fields, path/type consistency, tags, raw metadata, "
            "and raw body sha256 values."
        )
    )
    def kb_validate_vault(include_raw: bool = True) -> VaultValidationResult:
        return schema_service.validate_vault(include_raw=include_raw)

    @server.tool(
        description=(
            "Dry-run or apply deterministic tag taxonomy reconciliation. Use apply=false to "
            "inspect unknown tag usage, then pass decisions with add/rename/remove to apply."
        )
    )
    async def kb_reconcile_taxonomy(
        apply: bool = False,
        decisions: dict[str, object] | None = None,
    ) -> TaxonomyReconcileResult:
        if not apply:
            return schema_service.reconcile_taxonomy(apply=apply, decisions=decisions)

        async def operation() -> TaxonomyReconcileResult:
            return schema_service.reconcile_taxonomy(apply=apply, decisions=decisions)

        return await write_service.queue.run(operation)
