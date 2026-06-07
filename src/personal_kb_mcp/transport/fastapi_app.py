from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from personal_kb_mcp.config import Settings
from personal_kb_mcp.runtime import create_runtime
from personal_kb_mcp.transport.errors import register_error_handlers
from personal_kb_mcp.transport.mcp_server import create_mcp_server


def create_fastapi_app(settings: Settings) -> FastAPI:
    runtime = create_runtime(settings)
    mcp_server = create_mcp_server(settings, writer=runtime.writer)
    mcp_app = mcp_server.streamable_http_app()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        _ = app
        async with mcp_server.session_manager.run():
            yield

    app = FastAPI(title="personal-kb-mcp", lifespan=lifespan)
    register_error_handlers(app)
    app.state.runtime = runtime

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "mcp_path": settings.mcp_path}

    app.router.routes.extend(mcp_app.routes)
    return app
