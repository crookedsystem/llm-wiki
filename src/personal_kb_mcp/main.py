import uvicorn

from personal_kb_mcp.config import Settings
from personal_kb_mcp.transport.fastapi_app import create_fastapi_app


def run_server(settings: Settings | None = None) -> None:
    resolved_settings = settings or Settings()
    uvicorn.run(
        create_fastapi_app(resolved_settings),
        host=resolved_settings.host,
        port=resolved_settings.port,
        log_level=resolved_settings.log_level,
    )


if __name__ == "__main__":
    run_server()
