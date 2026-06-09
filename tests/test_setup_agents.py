from pathlib import Path

from setup_support.codex_config import add_codex_mcp_server
from setup_support.config import build_server_url, load_env, resolve_config


def test_load_env는_dotenv를_읽고_process_env가_우선한다(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "KB_PORT=9999\nKB_MCP_PATH='/mcp'\nLLM_WIKI_MCP_URL=http://from-file:9999/mcp\n",
        encoding="utf-8",
    )

    values = load_env(
        env_file,
        {
            "KB_PORT": "18083",
            "CLAUDE_SKILLS_DIR": "/tmp/claude-skills",
        },
    )

    assert values["KB_PORT"] == "18083"
    assert values["KB_MCP_PATH"] == "/mcp"
    assert values["LLM_WIKI_MCP_URL"] == "http://from-file:9999/mcp"
    assert values["CLAUDE_SKILLS_DIR"] == "/tmp/claude-skills"


def test_build_server_url은_dotenv의_host_port_path를_사용한다() -> None:
    url = build_server_url(
        {
            "KB_HOST": "0.0.0.0",
            "KB_PORT": "18083",
            "KB_MCP_PATH": "custom-mcp",
        }
    )

    assert url == "http://127.0.0.1:18083/custom-mcp"


def test_resolve_config는_agent별_기본_server_name과_env_path를_정한다(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "KB_HOST=127.0.0.1\n"
        "KB_PORT=18083\n"
        "KB_MCP_PATH=/mcp\n"
        f"HERMES_HOME={tmp_path / 'hermes'}\n"
        f"CLAUDE_SKILLS_DIR={tmp_path / 'claude-skills'}\n"
        f"CODEX_HOME={tmp_path / 'codex'}\n",
        encoding="utf-8",
    )

    claude = resolve_config(
        agent="claude",
        repo_root=tmp_path,
        env_file=env_file,
        process_env={},
    )
    codex = resolve_config(
        agent="codex",
        repo_root=tmp_path,
        env_file=env_file,
        process_env={},
    )

    assert claude.server_name == "llm-wiki"
    assert codex.server_name == "llm_wiki"
    assert claude.server_url == "http://127.0.0.1:18083/mcp"
    assert claude.claude_skill_dest == tmp_path / "claude-skills" / "llm-wiki"
    assert codex.codex_config_path == tmp_path / "codex" / "config.toml"


def test_codex_config는_기존_server_name을_덮어쓰지_않는다(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        '[mcp_servers.llm_wiki]\nurl = "http://old.example/mcp"\n',
        encoding="utf-8",
    )

    result = add_codex_mcp_server(
        config_path,
        "llm_wiki",
        "http://new.example/mcp",
        dry_run=False,
    )

    assert result.changed is False
    assert "not overwriting" in result.reason
    assert "http://old.example/mcp" in config_path.read_text(encoding="utf-8")
    assert "http://new.example/mcp" not in config_path.read_text(encoding="utf-8")


def test_codex_config는_같은_url의_중복_server를_추가하지_않는다(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        '[mcp_servers.existing]\nurl = "http://127.0.0.1:9999/mcp"\n',
        encoding="utf-8",
    )

    result = add_codex_mcp_server(
        config_path,
        "llm_wiki",
        "http://127.0.0.1:9999/mcp",
        dry_run=False,
    )

    assert result.changed is False
    assert "not adding duplicate" in result.reason
    assert "[mcp_servers.llm_wiki]" not in config_path.read_text(encoding="utf-8")


def test_codex_config는_새_server만_append한다(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text('[profile.default]\nmodel = "gpt-5"\n', encoding="utf-8")

    result = add_codex_mcp_server(
        config_path,
        "llm_wiki",
        "http://127.0.0.1:9999/mcp",
        dry_run=False,
    )

    content = config_path.read_text(encoding="utf-8")
    assert result.changed is True
    assert '[profile.default]\nmodel = "gpt-5"' in content
    assert "[mcp_servers.llm_wiki]" in content
    assert 'url = "http://127.0.0.1:9999/mcp"' in content
