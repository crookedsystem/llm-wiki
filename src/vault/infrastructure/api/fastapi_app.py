from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, cast

from fastapi import Depends, FastAPI, Request
from mcp.server.fastmcp import FastMCP

from common.config import Settings
from common.runtime_registry import Runtime, get_runtime
from vault.component.github_push_scheduler import GithubPushScheduler
from vault.dto.response.health_response import HealthResponse
from vault.dto.response.metrics_response import (
    MetricsResponse,
    metrics_response,
)
from vault.dto.response.tool_response import JsonSchema, ToolResponse
from vault.infrastructure.api.rest_error_handler import (
    register_error_handlers,
)
from vault.infrastructure.mcp_tool.mcp_server import create_mcp_server
from vault.service.vault_inspection_service import VaultInspectionService


def get_app_runtime(request: Request) -> Runtime:
    return cast(Runtime, request.app.state.runtime)


def get_inspection_service(
    runtime: Annotated[Runtime, Depends(get_app_runtime)],
) -> VaultInspectionService:
    return runtime.inspection_service


def get_mcp_server(request: Request) -> FastMCP[object]:
    return cast(FastMCP[object], request.app.state.mcp_server)


def get_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def create_fastapi_app(settings: Settings) -> FastAPI:
    runtime = get_runtime(settings)
    mcp_server = create_mcp_server(
        settings,
        write_service=runtime.write_service,
        search_service=runtime.search_service,
        context_service=runtime.context_service,
        git_push_service=runtime.git_push_service,
    )
    mcp_app = mcp_server.streamable_http_app()
    github_push_scheduler = GithubPushScheduler(push_service=runtime.git_push_service)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        _ = app
        async with mcp_server.session_manager.run():
            if settings.github_push_enabled:
                github_push_scheduler.start()
            try:
                yield
            finally:
                await github_push_scheduler.stop()

    app = FastAPI(
        title="llm-wiki",
        description="개인 Markdown knowledge base를 MCP와 REST 문서 endpoint로 노출합니다.",
        lifespan=lifespan,
    )
    register_error_handlers(app)
    app.state.settings = settings
    app.state.runtime = runtime
    app.state.mcp_server = mcp_server
    app.state.github_push_scheduler = github_push_scheduler

    @app.get(
        "/health",
        response_model=HealthResponse,
        summary="Health check",
        description="서버가 실행 중인지와 MCP mount path를 확인합니다.",
    )
    def health(settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
        return HealthResponse(status="ok", mcp_path=settings.mcp_path)

    @app.get(
        "/metrics",
        response_model=MetricsResponse,
        summary="Vault metrics 조회",
        description=(
            "설정된 Markdown vault를 검사해 note 수, byte 수, wiki graph 지표를 반환합니다."
        ),
    )
    def metrics(
        inspection_service: Annotated[VaultInspectionService, Depends(get_inspection_service)],
    ) -> MetricsResponse:
        snapshot = inspection_service.inspect_vault().metrics
        return metrics_response(snapshot)

    @app.get(
        "/tools",
        response_model=list[ToolResponse],
        summary="MCP tool schema 조회",
        description=(
            "현재 등록된 MCP tool의 이름, 설명, 입력/출력 JSON schema를 "
            "Swagger용 JSON으로 반환합니다."
        ),
    )
    async def tools(
        mcp_server: Annotated[FastMCP[object], Depends(get_mcp_server)],
    ) -> list[ToolResponse]:
        registered_tools = await mcp_server.list_tools()
        return [
            ToolResponse(
                name=tool.name,
                description=tool.description,
                inputSchema=cast(JsonSchema, tool.inputSchema),
                outputSchema=(
                    cast(JsonSchema, tool.outputSchema) if tool.outputSchema is not None else None
                ),
            )
            for tool in registered_tools
        ]

    app.router.routes.extend(mcp_app.routes)
    return app
