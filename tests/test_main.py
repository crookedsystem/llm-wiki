from pathlib import Path
from typing import Any, cast

from fastapi import FastAPI
from pytest import MonkeyPatch

from personal_kb_mcp import main as main_module
from personal_kb_mcp.config import Settings


def test_run_server_starts_fastapi_app_with_uvicorn(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_app = FastAPI()
    calls: dict[str, Any] = {}

    def fake_create_fastapi_app(settings: Settings) -> FastAPI:
        assert settings.port == 9999
        return fake_app

    def fake_uvicorn_run(app: FastAPI, **kwargs: Any) -> None:
        calls["app"] = app
        calls.update(kwargs)

    monkeypatch.setattr(main_module, "create_fastapi_app", fake_create_fastapi_app)
    monkeypatch.setattr(cast(Any, main_module).uvicorn, "run", fake_uvicorn_run)

    main_module.run_server(Settings(vault_path=tmp_path / "vault"))

    assert calls == {
        "app": fake_app,
        "host": "127.0.0.1",
        "port": 9999,
        "log_level": "info",
    }
