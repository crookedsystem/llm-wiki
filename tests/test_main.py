from pathlib import Path

from fastapi import FastAPI
from pytest import MonkeyPatch

from personal_kb_mcp import main as main_module
from personal_kb_mcp.config import Settings


def test_run_server는_settings로_fastapi_app을_생성하고_uvicorn을_실행한다(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    # Given: FastAPI app factory와 uvicorn.run을 관찰할 수 있도록 대체한다.
    fake_app = FastAPI()
    calls: dict[str, object] = {}

    def fake_create_fastapi_app(settings: Settings) -> FastAPI:
        assert settings.port == 9999
        return fake_app

    def fake_uvicorn_run(app: FastAPI, **kwargs: object) -> None:
        calls["app"] = app
        calls.update(kwargs)

    monkeypatch.setattr(main_module, "create_fastapi_app", fake_create_fastapi_app)
    monkeypatch.setattr("personal_kb_mcp.main.uvicorn.run", fake_uvicorn_run)

    # When: 명시 Settings로 서버 실행 진입점을 호출한다.
    main_module.run_server(Settings(host="127.0.0.1", vault_path=tmp_path / "vault"))

    # Then: 생성된 app과 설정의 host/port/log level이 uvicorn에 전달된다.
    assert calls == {
        "app": fake_app,
        "host": "127.0.0.1",
        "port": 9999,
        "log_level": "info",
    }
