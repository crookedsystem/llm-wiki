from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, cast

from fastapi import Depends, FastAPI, Request
from mcp.server.fastmcp import FastMCP

from personal_kb_mcp.config import Settings
from personal_kb_mcp.domain.vault.dto.response.health_response import HealthResponse
from personal_kb_mcp.domain.vault.dto.response.metrics_response import (
    MetricsResponse,
    metrics_response,
)
from personal_kb_mcp.domain.vault.dto.response.tool_response import JsonSchema, ToolResponse
from personal_kb_mcp.domain.vault.infrastructure.apis.rest_error_handler import (
    register_error_handlers,
)
from personal_kb_mcp.domain.vault.infrastructure.mcp_tools.mcp_server import create_mcp_server
from personal_kb_mcp.domain.vault.service.vault_inspection_service import VaultInspectionService
from personal_kb_mcp.runtime import Runtime, create_runtime


def get_inspection_service(request: Request) -> VaultInspectionService:
    runtime = cast(Runtime, request.app.state.runtime)
    return runtime.inspection_service


def get_mcp_server(request: Request) -> FastMCP[object]:
    return cast(FastMCP[object], request.app.state.mcp_server)


def create_fastapi_app(settings: Settings) -> FastAPI:
    runtime = create_runtime(settings)
    mcp_server = create_mcp_server(
        settings,
        write_service=runtime.write_service,
        search_service=runtime.search_service,
    )
    mcp_app = mcp_server.streamable_http_app()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        _ = app
        async with mcp_server.session_manager.run():
            yield

    app = FastAPI(
        title="personal-kb-mcp",
        description="개인 Markdown knowledge base를 MCP와 REST 문서 endpoint로 노출합니다.",
        lifespan=lifespan,
    )
    register_error_handlers(app)
    app.state.runtime = runtime
    app.state.mcp_server = mcp_server

    @app.get(
        "/health",
        response_model=HealthResponse,
        summary="Health check",
        description="서버가 실행 중인지와 MCP mount path를 확인합니다.",
    )
    def health() -> HealthResponse:
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
        mcp_tools = await mcp_server.list_tools()
        return [
            ToolResponse(
                name=tool.name,
                description=tool.description,
                inputSchema=cast(JsonSchema, tool.inputSchema),
                outputSchema=(
                    cast(JsonSchema, tool.outputSchema) if tool.outputSchema is not None else None
                ),
            )
            for tool in mcp_tools
        ]

    app.router.routes.extend(mcp_app.routes)
    return app
