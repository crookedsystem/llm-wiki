from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, cast

from fastapi import Depends, FastAPI, Request
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from personal_kb_mcp.config import Settings
from personal_kb_mcp.runtime import Runtime, create_runtime
from personal_kb_mcp.transport.errors import register_error_handlers
from personal_kb_mcp.transport.mcp_server import create_mcp_server
from personal_kb_mcp.vault.service import VaultService

JsonSchema = dict[str, object]


class ToolDocument(BaseModel):
    name: str = Field(description="MCP tool 이름")
    description: str | None = Field(description="MCP tool이 수행하는 작업 설명")
    inputSchema: JsonSchema = Field(description="MCP tool 입력 JSON schema")
    outputSchema: JsonSchema | None = Field(description="MCP tool 출력 JSON schema")


class MetricsDocument(BaseModel):
    vault_notes_total: int = Field(ge=0, description="Vault에서 검색 가능한 Markdown note 수")
    vault_bytes_total: int = Field(ge=0, description="Vault Markdown note 파일의 총 byte 크기")
    graph_links_total: int = Field(ge=0, description="Wiki link 전체 개수")
    graph_broken_links_total: int = Field(
        ge=0, description="대상 note를 찾지 못한 broken wiki link 수"
    )
    graph_orphans_total: int = Field(ge=0, description="다른 note에서 링크되지 않은 orphan note 수")


def get_vault_service(request: Request) -> VaultService:
    runtime = cast(Runtime, request.app.state.runtime)
    return runtime.vault_service


def get_mcp_server(request: Request) -> FastMCP[object]:
    return cast(FastMCP[object], request.app.state.mcp_server)


def create_fastapi_app(settings: Settings) -> FastAPI:
    runtime = create_runtime(settings)
    mcp_server = create_mcp_server(
        settings,
        writer=runtime.writer,
        vault_service=runtime.vault_service,
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
        summary="Health check",
        description="서버가 실행 중인지와 MCP mount path를 확인합니다.",
    )
    def health() -> dict[str, str]:
        return {"status": "ok", "mcp_path": settings.mcp_path}

    @app.get(
        "/metrics",
        response_model=MetricsDocument,
        summary="Vault metrics 조회",
        description=(
            "설정된 Markdown vault를 검사해 note 수, byte 수, wiki graph 지표를 반환합니다."
        ),
    )
    def metrics(
        vault_service: Annotated[VaultService, Depends(get_vault_service)],
    ) -> MetricsDocument:
        snapshot = vault_service.inspect_vault().metrics
        return MetricsDocument(
            vault_notes_total=snapshot.vault_notes_total,
            vault_bytes_total=snapshot.vault_bytes_total,
            graph_links_total=snapshot.graph_links_total,
            graph_broken_links_total=snapshot.graph_broken_links_total,
            graph_orphans_total=snapshot.graph_orphans_total,
        )

    @app.get(
        "/tools",
        response_model=list[ToolDocument],
        summary="MCP tool schema 조회",
        description=(
            "현재 등록된 MCP tool의 이름, 설명, 입력/출력 JSON schema를 "
            "Swagger용 JSON으로 반환합니다."
        ),
    )
    async def tools(
        mcp_server: Annotated[FastMCP[object], Depends(get_mcp_server)],
    ) -> list[ToolDocument]:
        mcp_tools = await mcp_server.list_tools()
        return [
            ToolDocument(
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
