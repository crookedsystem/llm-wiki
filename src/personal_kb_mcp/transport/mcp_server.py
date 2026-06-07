from dataclasses import asdict
from typing import Any, Literal, cast

from mcp.server.fastmcp import FastMCP

from personal_kb_mcp.config import Settings
from personal_kb_mcp.runtime import create_runtime
from personal_kb_mcp.status.health import inspect_vault
from personal_kb_mcp.writes.writer import VaultWriter

McpLogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def create_mcp_server(settings: Settings, writer: VaultWriter | None = None) -> FastMCP[Any]:
    resolved_writer = writer or create_runtime(settings).writer
    server = FastMCP(
        "personal-kb-mcp",
        host=settings.host,
        port=settings.port,
        streamable_http_path=settings.mcp_path,
        log_level=cast(McpLogLevel, settings.log_level.upper()),
    )

    @server.tool()
    async def kb_write_note(
        note_path: str,
        content: str,
        if_hash: str | None = None,
    ) -> dict[str, str | None]:
        result = await resolved_writer.write_note(note_path, content, if_hash=if_hash)
        return {
            "path": result.path.as_posix(),
            "source_hash": result.source_hash,
            "content_hash": result.content_hash,
            "commit_hash": result.commit_hash,
        }

    @server.tool()
    def kb_vault_status() -> dict[str, object]:
        return asdict(inspect_vault(settings.vault_path).status)

    @server.tool()
    def kb_graph_health() -> dict[str, object]:
        return asdict(inspect_vault(settings.vault_path).graph)

    @server.tool()
    def kb_metrics() -> dict[str, object]:
        return asdict(inspect_vault(settings.vault_path).metrics)

    return server
