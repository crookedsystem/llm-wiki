import asyncio
import subprocess
from pathlib import Path
from typing import TypedDict, cast

from pytest import MonkeyPatch

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


class PushToolResult(TypedDict):
    committed: bool
    commit_hash: str
    pushed: bool
    push_tool: str
    push_command: str


def test_mcp_server는_기본_http_설정을_사용한다(tmp_path: Path) -> None:
    # Given: 기본 Settings로 MCP server를 생성한다.
    app_settings = Settings(host="127.0.0.1", vault_path=tmp_path / "vault")
    runtime = create_runtime(app_settings)
    server = create_mcp_server(
        app_settings,
        runtime.write_service,
        runtime.search_service,
        runtime.git_push_service,
    )

    # When: FastMCP HTTP 설정을 조회한다.
    server_settings = server.settings

    # Then: local-only host, 기본 port, streamable HTTP path가 적용된다.
    assert server_settings.host == "127.0.0.1"
    assert server_settings.port == 9999
    assert server_settings.streamable_http_path == "/mcp"


def test_mcp_server는_write_search_push_tool을_노출하고_description을_제공한다(
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
            runtime.git_push_service,
        )

        # When: 등록된 tool 목록을 조회하고 write/search tool을 호출한다.
        tools = await server.list_tools()
        _, write_result = await server.call_tool(
            "kb_write_note",
            {
                "note_path": "concepts/agent-memory.md",
                "title": "Agent Memory",
                "type": "concept",
                "tags": ["agent-memory"],
                "sources": ["raw/articles/source.md"],
                "body": "## Summary\nAgent memory keeps durable context.",
                "created": "2026-06-12",
                "updated": "2026-06-12",
                "confidence": "medium",
                "contested": False,
            },
        )
        structured_write_result = cast(WriteNoteToolResult, write_result)
        _, search_result = await server.call_tool("kb_search_notes", {"query": "agent memory"})
        structured_search_result = cast(SearchToolResult, search_result)

        # Then: MCP는 쓰기/검색/push tool을 노출하고 각 tool description은 비어 있지 않다.
        tool_by_name = {tool.name: tool for tool in tools}
        assert set(tool_by_name) == {"kb_write_note", "kb_search_notes", "kb_push_vault"}
        assert "structured fields" in (tool_by_name["kb_write_note"].description or "")
        assert "Search Markdown notes" in (tool_by_name["kb_search_notes"].description or "")
        assert "push origin to the current branch" in (
            tool_by_name["kb_push_vault"].description or ""
        )
        assert structured_write_result["source_hash"]
        results = structured_search_result["results"]
        assert structured_search_result["count"] == 1
        assert results[0]["path"] == "concepts/agent-memory.md"
        assert results[0]["content_hash"] == structured_write_result["content_hash"]

    asyncio.run(exercise_server())


def test_mcp_push_tool은_vault_변경사항을_commit하고_push한다(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    async def exercise_server() -> None:
        # Given: 원격 bare repository가 연결된 vault MCP server가 있다.
        vault_root = tmp_path / "vault"
        remote_root = tmp_path / "remote.git"
        vault_root.mkdir()
        subprocess.run(["git", "init"], cwd=vault_root, check=True, capture_output=True)
        subprocess.run(
            ["git", "checkout", "-b", "main"],
            cwd=vault_root,
            check=True,
            capture_output=True,
        )
        subprocess.run(["git", "init", "--bare", remote_root], check=True, capture_output=True)
        subprocess.run(
            ["git", "remote", "add", "origin", str(remote_root)],
            cwd=vault_root,
            check=True,
            capture_output=True,
        )
        (vault_root / "concepts").mkdir()
        (vault_root / "concepts" / "agent-memory.md").write_text(
            "# Agent Memory\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(
            "vault.infrastructure.repository.git_repository.shutil.which",
            lambda _: None,
        )
        settings = Settings(host="127.0.0.1", vault_path=vault_root)
        runtime = create_runtime(settings)
        server = create_mcp_server(
            settings,
            runtime.write_service,
            runtime.search_service,
            runtime.git_push_service,
        )

        # When: kb_push_vault tool을 호출한다.
        _, push_result = await server.call_tool("kb_push_vault", {})
        structured_push_result = cast(PushToolResult, push_result)

        # Then: 변경사항이 commit되고 원격 main branch로 push된다.
        assert structured_push_result["committed"] is True
        assert structured_push_result["pushed"] is True
        assert structured_push_result["push_tool"] == "git"
        assert structured_push_result["push_command"] == "git push origin main"
        assert len(structured_push_result["commit_hash"]) == 40

    asyncio.run(exercise_server())
