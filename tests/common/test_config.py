from pathlib import Path

from pytest import MonkeyPatch

from common.config import Settings


def test_설정은_명시하지_않은_값에_안전한_기본값을_사용한다(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    # Given: 기본값 검증에 영향을 주는 KB_ 환경변수가 없다.
    for env_name in (
        "KB_HOST",
        "KB_PORT",
        "KB_MCP_PATH",
        "KB_LOG_LEVEL",
        "KB_VAULT_PATH",
        "KB_GITHUB_PUSH_ENABLED",
    ):
        monkeypatch.delenv(env_name, raising=False)
    monkeypatch.chdir(tmp_path)
    settings = Settings(vault_path=tmp_path / "vault")

    # When: 서버와 vault 기본값을 조회한다.
    observed_defaults = {
        "host": settings.host,
        "port": settings.port,
        "mcp_path": settings.mcp_path,
        "log_level": settings.log_level,
        "vault_path": settings.vault_path,
        "github_push_enabled": settings.github_push_enabled,
    }

    # Then: 외부 노출을 피하는 서버 기본값, 명시 vault path, safe push 기본값이 적용된다.
    assert observed_defaults == {
        "host": "127.0.0.1",
        "port": 9999,
        "mcp_path": "/mcp",
        "log_level": "info",
        "vault_path": tmp_path / "vault",
        "github_push_enabled": False,
    }


def test_설정은_kb_환경변수로_명시한_값을_우선한다(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    # Given: KB_ prefix 환경변수로 port, vault, log level이 지정되어 있다.
    monkeypatch.setenv("KB_PORT", "10000")
    monkeypatch.setenv("KB_VAULT_PATH", str(tmp_path / "env-vault"))
    monkeypatch.setenv("KB_LOG_LEVEL", "debug")
    monkeypatch.setenv("KB_GITHUB_PUSH_ENABLED", "true")

    # When: Settings를 환경변수에서 생성한다.
    settings = Settings()

    # Then: 환경변수 값이 기본값보다 우선 적용된다.
    assert settings.port == 10000
    assert settings.vault_path == tmp_path / "env-vault"
    assert settings.log_level == "debug"
    assert settings.github_push_enabled is True


def test_설정은_삭제된_미사용_env를_무시한다(monkeypatch: MonkeyPatch) -> None:
    # Given: 이전 .env.example에 있던 미사용 설정이 잘못된 값으로 남아 있다.
    monkeypatch.setenv("KB_MAX_NOTE_BYTES", "not-an-int")
    monkeypatch.setenv("KB_ENABLE_WRITES", "maybe")
    monkeypatch.setenv("KB_VECTOR_ENABLED", "maybe")

    # When: Settings를 생성한다.
    settings = Settings()

    # Then: 현재 런타임에서 쓰는 설정만 모델 필드로 유지된다.
    assert not hasattr(settings, "max_note_bytes")
    assert not hasattr(settings, "enable_writes")
    assert not hasattr(settings, "vector_enabled")
