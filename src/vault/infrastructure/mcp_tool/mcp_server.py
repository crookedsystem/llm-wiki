from typing import Literal, cast

from mcp.server.fastmcp import FastMCP

from common.config import Settings
from vault.infrastructure.mcp_tool.tool_registry import register_vault_tools
from vault.service.vault_context_service import VaultContextService
from vault.service.vault_git_push_service import VaultGitPushService
from vault.service.vault_search_service import VaultSearchService
from vault.service.vault_write_service import VaultWriteService

McpLogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def _mcp_log_level(settings: Settings) -> McpLogLevel:
    return cast(McpLogLevel, settings.log_level.upper())


def create_mcp_server(
    settings: Settings,
    write_service: VaultWriteService,
    search_service: VaultSearchService,
    context_service: VaultContextService,
    git_push_service: VaultGitPushService,
) -> FastMCP[object]:
    server: FastMCP[object] = FastMCP(
        "llm-wiki",
        host=settings.host,
        port=settings.port,
        streamable_http_path=settings.mcp_path,
        log_level=_mcp_log_level(settings),
    )
    register_vault_tools(
        server,
        write_service,
        search_service,
        context_service,
        git_push_service,
    )
    return server
