import asyncio
from pathlib import Path
from typing import Any, cast

from personal_kb_mcp.config import Settings
from personal_kb_mcp.transport.mcp_server import create_mcp_server


def test_create_mcp_server_uses_default_http_settings(tmp_path: Path) -> None:
    server = create_mcp_server(Settings(vault_path=tmp_path / "vault"))

    assert server.settings.host == "127.0.0.1"
    assert server.settings.port == 9999
    assert server.settings.streamable_http_path == "/mcp"


def test_create_mcp_server_registers_core_tools_and_writes_notes(tmp_path: Path) -> None:
    async def exercise_server() -> None:
        server = create_mcp_server(Settings(vault_path=tmp_path / "vault"))
        tools = await server.list_tools()

        assert {tool.name for tool in tools} >= {
            "kb_write_note",
            "kb_vault_status",
            "kb_graph_health",
            "kb_metrics",
        }

        _, write_result = await server.call_tool(
            "kb_write_note",
            {"note_path": "daily/today.md", "content": "Body text"},
        )
        structured_write_result = cast(dict[str, Any], write_result)
        assert structured_write_result["source_hash"]

        _, status_result = await server.call_tool("kb_vault_status", {})
        structured_status_result = cast(dict[str, Any], status_result)
        assert structured_status_result["note_count"] == 1

    asyncio.run(exercise_server())
