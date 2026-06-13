import io
import sys
from pathlib import Path

from pytest import CaptureFixture, MonkeyPatch, raises
from setup_support import cli
from setup_support.codex_config import add_codex_mcp_server
from setup_support.config import (
    ResolvedConfig,
    build_server_url,
    load_env,
    resolve_config,
    stable_repo_root,
)
from setup_support.hooks import (
    install_agent_hooks,
    merge_claude_hook_settings,
    merge_codex_hook_settings,
)
from setup_support.installers import install_codex


class _TtyInput(io.StringIO):
    def isatty(self) -> bool:
        return True


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


def test_load_env는_빈_process_env가_shell_env를_무시한다(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("KB_PORT=9999\n", encoding="utf-8")
    monkeypatch.setenv("KB_PORT", "18083")
    monkeypatch.setenv("CODEX_HOME", "/opt/codex")

    values = load_env(env_file, process_env={})

    assert values["KB_PORT"] == "9999"
    assert "CODEX_HOME" not in values


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
    assert claude.install_hooks is True
    assert claude.install_stop_hook is False
    assert claude.claude_hooks_dir == Path.home() / ".claude" / "hooks" / "llm-wiki"
    assert codex.codex_hooks_dir == tmp_path / "codex" / "hooks" / "llm-wiki"


def test_resolve_config는_hook_설정을_env와_option에서_읽는다(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        f"HERMES_HOME={tmp_path / 'hermes'}\n"
        "LLM_WIKI_INSTALL_HOOKS=false\n"
        f"HERMES_LLM_WIKI_HOOKS_DIR={tmp_path / 'custom-hermes-hooks'}\n"
        f"CLAUDE_HOOKS_DIR={tmp_path / 'custom-claude-hooks'}\n"
        f"CLAUDE_SETTINGS_PATH={tmp_path / 'claude-settings.json'}\n",
        encoding="utf-8",
    )

    config = resolve_config(
        agent="hermes",
        repo_root=tmp_path,
        env_file=env_file,
        process_env={},
    )
    forced = resolve_config(
        agent="claude",
        repo_root=tmp_path,
        env_file=env_file,
        process_env={},
        install_hooks=True,
        install_stop_hook=True,
        claude_settings_path=str(tmp_path / "override-settings.json"),
    )

    assert config.install_hooks is False
    assert config.install_stop_hook is False
    assert config.hermes_hooks_dir == tmp_path / "custom-hermes-hooks"
    assert forced.install_hooks is True
    assert forced.install_stop_hook is True
    assert forced.claude_hooks_dir == tmp_path / "custom-claude-hooks"
    assert forced.claude_settings_path == tmp_path / "override-settings.json"


def test_setup_cli는_agent_옵션이_없으면_전체_agent를_설치한다(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    installed_agents: list[str] = []

    def fake_install_agent(config: ResolvedConfig) -> int:
        installed_agents.append(config.agent)
        return 0

    monkeypatch.setattr(cli, "install_agent", fake_install_agent)
    env_file = tmp_path / ".env"
    env_file.write_text("KB_PORT=18083\n", encoding="utf-8")

    result = cli.run(["--env-file", str(env_file), "--dry-run", "--no-hooks"])

    assert result == 0
    assert installed_agents == ["hermes", "claude", "codex"]


def test_setup_cli는_agent_옵션으로_일부_agent만_설치한다(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    installed_agents: list[str] = []

    def fake_install_agent(config: ResolvedConfig) -> int:
        installed_agents.append(config.agent)
        return 0

    monkeypatch.setattr(cli, "install_agent", fake_install_agent)
    env_file = tmp_path / ".env"
    env_file.write_text("KB_PORT=18083\n", encoding="utf-8")

    result = cli.run(
        [
            "--env-file",
            str(env_file),
            "--dry-run",
            "--no-hooks",
            "--agent",
            "codex",
            "--agent",
            "claude",
            "--agent",
            "codex",
        ]
    )

    assert result == 0
    assert installed_agents == ["codex", "claude"]


def test_install_codex는_llm_wiki와_push_skill을_함께_설치한다(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    (repo_root / "skills" / "llm-wiki").mkdir(parents=True)
    (repo_root / "skills" / "llm-wiki" / "SKILL.md").write_text(
        "---\nname: llm-wiki\ndescription: test\n---\n",
        encoding="utf-8",
    )
    (repo_root / "skills" / "llm-wiki-push").mkdir(parents=True)
    (repo_root / "skills" / "llm-wiki-push" / "SKILL.md").write_text(
        "---\nname: llm-wiki-push\ndescription: test\n---\n",
        encoding="utf-8",
    )
    env_file = tmp_path / ".env"
    env_file.write_text(f"CODEX_HOME={tmp_path / 'codex'}\n", encoding="utf-8")
    config = resolve_config(
        agent="codex",
        repo_root=repo_root,
        env_file=env_file,
        process_env={},
        install_hooks=False,
    )

    result = install_codex(config)

    assert result == 0
    assert (tmp_path / "codex" / "skills" / "llm-wiki" / "SKILL.md").exists()
    assert (tmp_path / "codex" / "skills" / "llm-wiki-push" / "SKILL.md").exists()


def test_setup_cli는_no_hooks와_claude_settings_option을_전달한다(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    seen_configs: list[ResolvedConfig] = []

    def fake_install_agent(config: ResolvedConfig) -> int:
        seen_configs.append(config)
        return 0

    monkeypatch.setattr(cli, "install_agent", fake_install_agent)
    env_file = tmp_path / ".env"
    env_file.write_text("KB_PORT=18083\n", encoding="utf-8")
    settings_path = tmp_path / "claude-settings.json"

    result = cli.run(
        [
            "--env-file",
            str(env_file),
            "--agent",
            "claude",
            "--no-hooks",
            "--claude-settings",
            str(settings_path),
        ]
    )

    assert result == 0
    assert len(seen_configs) == 1
    assert seen_configs[0].install_hooks is False
    assert seen_configs[0].install_stop_hook is False
    assert seen_configs[0].claude_settings_path == settings_path


def test_setup_cli는_stop_hook_Y일때만_설치를_전달한다(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    seen_configs: list[ResolvedConfig] = []

    def fake_install_agent(config: ResolvedConfig) -> int:
        seen_configs.append(config)
        return 0

    monkeypatch.setattr(cli, "install_agent", fake_install_agent)
    monkeypatch.setattr(sys, "stdin", _TtyInput("Y\n"))
    env_file = tmp_path / ".env"
    env_file.write_text("KB_PORT=18083\n", encoding="utf-8")

    result = cli.run(["--env-file", str(env_file), "--agent", "claude"])

    assert result == 0
    assert len(seen_configs) == 1
    assert seen_configs[0].install_stop_hook is True
    assert "may prevent you from receiving the LLM response correctly" in capsys.readouterr().out


def test_stop_hook_prompt는_N이면_설치하지_않는다() -> None:
    output = io.StringIO()

    result = cli.prompt_stop_hook_install(
        input_stream=_TtyInput("N\n"),
        output_stream=output,
    )

    assert result is False
    assert "Type Y or N only" in output.getvalue()


def test_stop_hook_prompt는_Y_N이_아니면_다시_묻는다() -> None:
    output = io.StringIO()

    result = cli.prompt_stop_hook_install(
        input_stream=_TtyInput("y\nN\n"),
        output_stream=output,
    )

    assert result is False
    assert "Please type exactly Y or N." in output.getvalue()
    assert output.getvalue().count("Install LLM Wiki Stop hook?") == 2


def test_stop_hook_prompt는_비대화형이면_실패한다() -> None:
    output = io.StringIO()

    with raises(cli.StopHookPromptError):
        cli.prompt_stop_hook_install(
            input_stream=io.StringIO("Y\n"),
            output_stream=output,
        )


def test_setup_cli는_stop_hook_선택을_못받으면_설치를_진행하지_않는다(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    seen_configs: list[ResolvedConfig] = []

    def fake_install_agent(config: ResolvedConfig) -> int:
        seen_configs.append(config)
        return 0

    monkeypatch.setattr(cli, "install_agent", fake_install_agent)
    monkeypatch.setattr(sys, "stdin", io.StringIO("Y\n"))
    env_file = tmp_path / ".env"
    env_file.write_text("KB_PORT=18083\n", encoding="utf-8")

    result = cli.run(["--env-file", str(env_file), "--agent", "claude"])

    assert result == 2
    assert seen_configs == []
    assert "installation did not run" in capsys.readouterr().err


def test_setup_cli는_dry_run이면_stop_hook_prompt를_건너뛴다(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    seen_configs: list[ResolvedConfig] = []

    def fake_install_agent(config: ResolvedConfig) -> int:
        seen_configs.append(config)
        return 0

    monkeypatch.setattr(cli, "install_agent", fake_install_agent)
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    env_file = tmp_path / ".env"
    env_file.write_text("KB_PORT=18083\n", encoding="utf-8")

    result = cli.run(["--env-file", str(env_file), "--dry-run", "--agent", "claude"])

    captured = capsys.readouterr()
    assert result == 0
    assert len(seen_configs) == 1
    assert seen_configs[0].install_hooks is True
    assert seen_configs[0].install_stop_hook is False
    assert "skip interactive Stop hook prompt" in captured.out
    assert "installation did not run" not in captured.err


def test_claude_hook_settings는_user_prompt와_stop_hook을_병합하고_중복하지_않는다(
    tmp_path: Path,
) -> None:
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        '{"hooks":{"Stop":[{"hooks":[{"type":"command","command":"notify","timeout":5}]}]}}',
        encoding="utf-8",
    )

    changed = merge_claude_hook_settings(
        settings_path=settings_path,
        context_command=str(tmp_path / "context.sh"),
        stop_command=str(tmp_path / "stop.sh"),
        dry_run=False,
    )
    unchanged = merge_claude_hook_settings(
        settings_path=settings_path,
        context_command=str(tmp_path / "context.sh"),
        stop_command=str(tmp_path / "stop.sh"),
        dry_run=False,
    )

    content = settings_path.read_text(encoding="utf-8")
    assert changed is True
    assert unchanged is False
    assert '"UserPromptSubmit"' in content
    assert '"Stop"' in content
    assert content.count("context.sh") == 1
    assert content.count("stop.sh") == 1
    assert "notify" in content


def test_install_agent_hooks는_claude_script와_settings를_설치한다(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    env_file = tmp_path / ".env"
    env_file.write_text(
        "KB_PORT=18083\n"
        f"CLAUDE_HOOKS_DIR={tmp_path / 'claude-hooks'}\n"
        f"CLAUDE_SETTINGS_PATH={tmp_path / 'settings.json'}\n",
        encoding="utf-8",
    )
    config = resolve_config(
        agent="claude",
        repo_root=repo_root,
        env_file=env_file,
        process_env={},
        install_stop_hook=True,
    )

    result = install_agent_hooks(config)

    assert result is not None
    assert result.context_hook.exists()
    assert result.stop_hook is not None
    assert result.stop_hook.exists()
    assert result.context_hook.stat().st_mode & 0o111
    context_script = result.context_hook.read_text(encoding="utf-8")
    stop_script = result.stop_hook.read_text(encoding="utf-8")
    settings = (tmp_path / "settings.json").read_text(encoding="utf-8")
    assert "llm_wiki_agent_hook.py" in context_script
    assert " context " in context_script
    assert "LLM_WIKI_MCP_SERVER_NAME=llm-wiki" in context_script
    assert "LLM_WIKI_MCP_URL=http://127.0.0.1:18083/mcp" in context_script
    assert "export LLM_WIKI_MCP_SERVER_NAME LLM_WIKI_MCP_URL" in context_script
    assert "llm_wiki_agent_hook.py" in stop_script
    assert " stop " in stop_script
    assert "--block-json" in stop_script
    assert "UserPromptSubmit" in settings
    assert "Stop" in settings
    # Hooks must fail open: a stale checkout or missing uv exits 0, never errors.
    for script in (context_script, stop_script):
        assert 'if [ ! -f "$LLM_WIKI_HOOK_HELPER" ]; then' in script
        assert "command -v uv" in script
        assert script.count("exit 0") >= 2


def test_install_agent_hooks는_stop_hook을_선택하지_않으면_context만_설치한다(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    env_file = tmp_path / ".env"
    env_file.write_text(
        "KB_PORT=18083\n"
        f"CLAUDE_HOOKS_DIR={tmp_path / 'claude-hooks'}\n"
        f"CLAUDE_SETTINGS_PATH={tmp_path / 'settings.json'}\n",
        encoding="utf-8",
    )
    previous_stop_hook = tmp_path / "claude-hooks" / "llm-wiki-stop-hook.sh"
    previous_stop_hook.parent.mkdir(parents=True)
    previous_stop_hook.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    (tmp_path / "settings.json").write_text(
        (
            '{"hooks":{"Stop":[{"hooks":[{"type":"command","command":"'
            f"{previous_stop_hook}"
            '","timeout":10}]}]}}'
        ),
        encoding="utf-8",
    )
    config = resolve_config(
        agent="claude",
        repo_root=repo_root,
        env_file=env_file,
        process_env={},
    )

    result = install_agent_hooks(config)

    assert result is not None
    assert result.context_hook.exists()
    assert result.stop_hook is None
    assert not previous_stop_hook.exists()
    settings = (tmp_path / "settings.json").read_text(encoding="utf-8")
    assert "UserPromptSubmit" in settings
    assert "Stop" not in settings
    hooks_readme = (tmp_path / "claude-hooks" / "README.md").read_text(encoding="utf-8")
    assert "Stop/update enforcer: not installed" in hooks_readme


def test_codex_hook_settings는_hooks_json에_병합하고_중복하지_않는다(
    tmp_path: Path,
) -> None:
    settings_path = tmp_path / "hooks.json"

    changed = merge_codex_hook_settings(
        settings_path=settings_path,
        context_command=str(tmp_path / "context.sh"),
        stop_command=str(tmp_path / "stop.sh"),
        dry_run=False,
    )
    unchanged = merge_codex_hook_settings(
        settings_path=settings_path,
        context_command=str(tmp_path / "context.sh"),
        stop_command=str(tmp_path / "stop.sh"),
        dry_run=False,
    )

    content = settings_path.read_text(encoding="utf-8")
    assert changed is True
    assert unchanged is False
    assert '"UserPromptSubmit"' in content
    assert '"Stop"' in content
    assert content.count("context.sh") == 1
    assert content.count("stop.sh") == 1


def test_install_agent_hooks는_codex_script와_hooks_json을_설치한다(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    env_file = tmp_path / ".env"
    env_file.write_text(
        "KB_PORT=18083\n"
        f"CODEX_HOME={tmp_path / 'codex'}\n"
        f"CODEX_LLM_WIKI_HOOKS_DIR={tmp_path / 'codex-hooks'}\n",
        encoding="utf-8",
    )
    config = resolve_config(
        agent="codex",
        repo_root=repo_root,
        env_file=env_file,
        process_env={},
        install_stop_hook=True,
    )

    result = install_agent_hooks(config)

    assert result is not None
    assert result.context_hook.exists()
    assert result.stop_hook is not None
    assert result.stop_hook.exists()
    stop_script = result.stop_hook.read_text(encoding="utf-8")
    assert "--block-json" in stop_script
    hooks_json = (tmp_path / "codex" / "hooks.json").read_text(encoding="utf-8")
    assert "UserPromptSubmit" in hooks_json
    assert "Stop" in hooks_json
    assert result.settings_path == tmp_path / "codex" / "hooks.json"


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


def test_생성된_hook은_helper가_사라지면_fail_open으로_exit_0한다(tmp_path: Path) -> None:
    import subprocess

    repo_root = tmp_path / "repo"
    (repo_root / "scripts" / "agent_hooks").mkdir(parents=True)
    env_file = tmp_path / ".env"
    env_file.write_text(
        f"CLAUDE_HOOKS_DIR={tmp_path / 'claude-hooks'}\n"
        f"CLAUDE_SETTINGS_PATH={tmp_path / 'settings.json'}\n",
        encoding="utf-8",
    )
    config = resolve_config(
        agent="claude",
        repo_root=repo_root,
        env_file=env_file,
        process_env={},
        install_stop_hook=True,
    )

    result = install_agent_hooks(config)
    assert result is not None
    assert result.stop_hook is not None

    # The helper checkout never existed (simulates a removed git worktree); the
    # hook must exit 0 quietly instead of erroring on every prompt.
    completed = subprocess.run(
        ["bash", str(result.stop_hook)],
        input="{}",
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0
    assert completed.stdout.strip() == ""


def test_stable_repo_root는_git이_없으면_입력_경로를_반환한다(tmp_path: Path) -> None:
    non_git = tmp_path / "plain"
    non_git.mkdir()

    assert stable_repo_root(non_git) == non_git


def test_stable_repo_root는_worktree에서_메인_worktree를_가리킨다(tmp_path: Path) -> None:
    import subprocess

    def git(*args: str, cwd: Path) -> None:
        subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)

    main = tmp_path / "main"
    main.mkdir()
    (main / "scripts" / "agent_hooks").mkdir(parents=True)
    (main / "scripts" / "agent_hooks" / "llm_wiki_agent_hook.py").write_text("", encoding="utf-8")
    git("init", "-q", cwd=main)
    git("config", "user.email", "t@example.com", cwd=main)
    git("config", "user.name", "t", cwd=main)
    git("add", "-A", cwd=main)
    git("commit", "-q", "-m", "init", cwd=main)

    worktree = tmp_path / "wt"
    git("worktree", "add", "-q", str(worktree), "-b", "feature", cwd=main)

    assert stable_repo_root(worktree).resolve() == main.resolve()


def test_worktree에서_설치하면_훅은_main경로_스킬env는_worktree경로를_쓴다(
    tmp_path: Path,
) -> None:
    import subprocess

    def git(*args: str, cwd: Path) -> None:
        subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)

    main = tmp_path / "main"
    (main / "scripts" / "agent_hooks").mkdir(parents=True)
    (main / "scripts" / "agent_hooks" / "llm_wiki_agent_hook.py").write_text("", encoding="utf-8")
    git("init", "-q", cwd=main)
    git("config", "user.email", "t@example.com", cwd=main)
    git("config", "user.name", "t", cwd=main)
    git("add", "-A", cwd=main)
    git("commit", "-q", "-m", "init", cwd=main)

    worktree = tmp_path / "wt"
    git("worktree", "add", "-q", str(worktree), "-b", "feature", cwd=main)
    # A worktree-local .env must win for skill/env sourcing.
    env_file = worktree / ".env"
    env_file.write_text(
        f"CLAUDE_HOOKS_DIR={tmp_path / 'claude-hooks'}\n"
        f"CLAUDE_SETTINGS_PATH={tmp_path / 'settings.json'}\n",
        encoding="utf-8",
    )

    config = resolve_config(
        agent="claude",
        repo_root=worktree,
        env_file=env_file,
        process_env={},
        install_stop_hook=True,
    )
    result = install_agent_hooks(config)
    assert result is not None
    assert result.stop_hook is not None

    # Hook bakes the durable main-worktree helper path (survives worktree deletion)...
    stop_script = result.stop_hook.read_text(encoding="utf-8")
    assert str(main.resolve()) in stop_script
    assert str(worktree.resolve()) not in stop_script
    # ...but skill/env sourcing stays on the invoking worktree checkout.
    assert config.repo_root == worktree
    assert config.skill_source == worktree / "skills" / "llm-wiki"
