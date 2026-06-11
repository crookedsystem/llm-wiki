import asyncio
from pathlib import Path
from typing import Any, TypedDict, cast

from common.config import Settings
from common.runtime_registry import create_runtime
from vault.infrastructure.mcp_tool.mcp_server import create_mcp_server


class WriteNoteToolResult(TypedDict):
    source_hash: str
    content_hash: str


class SearchNoteToolResult(TypedDict):
    path: str
    content_hash: str


class SearchToolResult(TypedDict):
    count: int
    results: list[SearchNoteToolResult]


def test_mcp_server는_기본_http_설정을_사용한다(tmp_path: Path) -> None:
    # Given: 기본 Settings로 MCP server를 생성한다.
    app_settings = Settings(host="127.0.0.1", vault_path=tmp_path / "vault")
    runtime = create_runtime(app_settings)
    server = create_mcp_server(
        app_settings,
        runtime.write_service,
        runtime.search_service,
        runtime.schema_service,
    )

    # When: FastMCP HTTP 설정을 조회한다.
    server_settings = server.settings

    # Then: local-only host, 기본 port, streamable HTTP path가 적용된다.
    assert server_settings.host == "127.0.0.1"
    assert server_settings.port == 9999
    assert server_settings.streamable_http_path == "/mcp"


def test_mcp_server는_write와_search_tool만_노출하고_description을_제공한다(
    tmp_path: Path,
) -> None:
    async def exercise_server() -> None:
        # Given: 임시 vault를 바라보는 MCP server가 있다.
        vault_root = tmp_path / "vault"
        settings = Settings(host="127.0.0.1", vault_path=vault_root)
        runtime = create_runtime(settings)
        server = create_mcp_server(
            settings,
            runtime.write_service,
            runtime.search_service,
            runtime.schema_service,
        )

        # When: 등록된 tool 목록을 조회하고 write/search tool을 호출한다.
        tools = await server.list_tools()
        _, _schema_result = await server.call_tool(
            "kb_write_note",
            {
                "note_path": "SCHEMA.md",
                "content": """# Wiki Schema

## Frontmatter
Required fields: `title`, `created`, `updated`, `type`, `tags`, `sources`,
`confidence`, `contested`.
Allowed `type` values: `entity`, `concept`, `comparison`, `query`, `summary`.

## Tag taxonomy
- Knowledge: agent-memory
""",
            },
        )
        _, write_result = await server.call_tool(
            "kb_write_note",
            {
                "note_path": "concepts/agent-memory.md",
                "content": """---
title: Agent Memory
created: 2026-06-10
updated: 2026-06-10
type: concept
tags: [agent-memory]
sources: [raw/hermes/source.md]
confidence: medium
contested: false
---

# Agent Memory
""",
            },
        )
        await server.call_tool(
            "kb_write_note",
            {
                "note_path": "entities/hermes-agent.md",
                "content": """---
title: Hermes Agent
created: 2026-06-10
updated: 2026-06-10
type: entity
tags: [agent-memory]
sources: [raw/hermes/source.md]
confidence: medium
contested: false
---

# Hermes Agent

Related to [[concepts/agent-memory]].
""",
            },
        )
        structured_write_result = cast(WriteNoteToolResult, write_result)
        _, search_result = await server.call_tool(
            "kb_search_notes",
            {"query": "agent memory", "path_prefix": "concepts"},
        )
        structured_search_result = cast(SearchToolResult, search_result)
        _, context_result = await server.call_tool(
            "kb_wiki_context",
            {"recent_log_lines": 5},
        )
        structured_context = cast(dict[str, Any], context_result)
        _, validation_result = await server.call_tool("kb_validate_vault", {})
        structured_validation = cast(dict[str, Any], validation_result)

        # Then: MCP는 schema/write/search tool을 노출하고 각 tool description은 비어 있지 않다.
        tool_by_name = {tool.name: tool for tool in tools}
        assert set(tool_by_name) == {
            "kb_write_note",
            "kb_search_notes",
            "kb_wiki_context",
            "kb_validate_vault",
            "kb_reconcile_taxonomy",
        }
        assert "complete Markdown note" in (tool_by_name["kb_write_note"].description or "")
        assert "Search Markdown notes" in (tool_by_name["kb_search_notes"].description or "")
        assert "context bundle" in (tool_by_name["kb_wiki_context"].description or "")
        assert structured_write_result["source_hash"]
        results = structured_search_result["results"]
        assert structured_search_result["count"] == 1
        assert results[0]["path"] == "concepts/agent-memory.md"
        assert results[0]["content_hash"] == structured_write_result["content_hash"]
        assert "schema" in structured_context
        assert cast(dict[str, Any], structured_context["health"])["schema_parse_ok"] is True
        context_map = cast(dict[str, Any], structured_context["wiki_map"])
        assert context_map["pages_by_type"] == {
            "concept": ["concepts/agent-memory.md"],
            "entity": ["entities/hermes-agent.md"],
        }
        entities = cast(list[dict[str, Any]], structured_context["entities"])
        assert [entity["path"] for entity in entities] == ["entities/hermes-agent.md"]
        assert entities[0]["title"] == "Hermes Agent"
        assert "issue_candidates" in structured_context
        assert "update_suggestions" in structured_context
        assert cast(dict[str, Any], structured_validation["summary"])["issue_count"] == 0

    asyncio.run(exercise_server())


def test_mcp_reconcile_taxonomy_apply는_write_queue를_통해_직렬화된다(
    tmp_path: Path,
) -> None:
    async def exercise_server() -> None:
        # Given: unknown tag가 있는 vault와 write queue lock을 잡고 있는 작업이 있다.
        vault_root = tmp_path / "vault"
        settings = Settings(host="127.0.0.1", vault_path=vault_root)
        runtime = create_runtime(settings)
        server = create_mcp_server(
            settings,
            runtime.write_service,
            runtime.search_service,
            runtime.schema_service,
        )
        await server.call_tool(
            "kb_write_note",
            {
                "note_path": "SCHEMA.md",
                "content": """# Wiki Schema

## Frontmatter
Required fields: `title`, `created`, `updated`, `type`, `tags`, `sources`,
`confidence`, `contested`.
Allowed `type` values: `entity`, `concept`, `comparison`, `query`, `summary`.

## Tag taxonomy
- Knowledge: agent-memory
""",
            },
        )
        page_path = vault_root / "concepts" / "agent-harness.md"
        page_path.parent.mkdir(parents=True, exist_ok=True)
        page_path.write_text(
            """---
title: Agent Harness
created: 2026-06-10
updated: 2026-06-10
type: concept
tags: [agent-harness]
sources: [raw/hermes/source.md]
confidence: medium
contested: false
---

# Agent Harness
""",
            encoding="utf-8",
        )
        release_queue = asyncio.Event()
        queue_entered = asyncio.Event()

        async def blocked_write() -> None:
            queue_entered.set()
            await release_queue.wait()

        blocking_task = asyncio.create_task(runtime.write_queue.run(blocked_write))
        await queue_entered.wait()

        # When: apply=true taxonomy reconciliation을 호출한다.
        reconcile_task = asyncio.create_task(
            server.call_tool(
                "kb_reconcile_taxonomy",
                {"apply": True, "decisions": {"add": ["agent-harness"]}},
            )
        )
        await asyncio.sleep(0)

        # Then: 같은 write queue lock이 풀리기 전에는 mutate tool이 완료되지 않는다.
        assert reconcile_task.done() is False

        release_queue.set()
        await blocking_task
        _, result = await reconcile_task
        structured_result = cast(dict[str, Any], result)
        assert structured_result["changed_files"] == ["SCHEMA.md"]

    asyncio.run(exercise_server())
