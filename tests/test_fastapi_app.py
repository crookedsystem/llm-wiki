from datetime import datetime
from pathlib import Path

from starlette.testclient import TestClient

from personal_kb_mcp.config import Settings
from personal_kb_mcp.transport.fastapi_app import create_fastapi_app


def test_fastapi_app_exposes_health_and_mounts_mcp(tmp_path: Path) -> None:
    app = create_fastapi_app(Settings(vault_path=tmp_path / "vault"))

    with TestClient(app, base_url="http://127.0.0.1:9999") as client:
        health_response = client.get("/health")
        mcp_response = client.get("/mcp")

    assert health_response.status_code == 200
    assert health_response.json() == {
        "status": "ok",
        "mcp_path": "/mcp",
    }
    assert mcp_response.status_code == 406
    assert "Client must accept text/event-stream" in mcp_response.text


def test_fastapi_app_returns_common_error_envelope_for_unknown_routes(tmp_path: Path) -> None:
    app = create_fastapi_app(Settings(vault_path=tmp_path / "vault"))

    with TestClient(app, base_url="http://127.0.0.1:9999") as client:
        response = client.get("/missing")

    assert response.status_code == 404
    assert response.json().keys() == {"code", "message", "timestamp"}
    assert response.json()["code"] == "NOT_FOUND"
    assert response.json()["message"] == "Not Found"
    assert datetime.fromisoformat(response.json()["timestamp"]).tzinfo is not None


def test_fastapi_app_returns_common_error_envelope_for_unhandled_errors(
    tmp_path: Path,
) -> None:
    app = create_fastapi_app(Settings(vault_path=tmp_path / "vault"))

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("secret internals")

    with TestClient(
        app,
        base_url="http://127.0.0.1:9999",
        raise_server_exceptions=False,
    ) as client:
        response = client.get("/boom")

    assert response.status_code == 500
    assert response.json().keys() == {"code", "message", "timestamp"}
    assert response.json()["code"] == "INTERNAL_SERVER_ERROR"
    assert response.json()["message"] == "Internal Server Error"
    assert "secret internals" not in response.text
    assert datetime.fromisoformat(response.json()["timestamp"]).tzinfo is not None
