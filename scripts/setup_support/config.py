from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

DEFAULT_SERVER_NAMES = {
    "hermes": "llm_wiki",
    "claude": "llm-wiki",
    "codex": "llm_wiki",
}


@dataclass(frozen=True)
class ResolvedConfig:
    repo_root: Path
    env_file: Path
    env: Mapping[str, str]
    agent: str
    server_name: str
    server_url: str
    dry_run: bool
    claude_scope: str
    hermes_home: Path
    claude_skills_dir: Path
    codex_home: Path
    codex_skills_dir: Path
    codex_config_path: Path
    install_hooks: bool
    hermes_hooks_dir: Path
    claude_hooks_dir: Path
    claude_settings_path: Path
    codex_hooks_dir: Path
    codex_hooks_json_path: Path

    @property
    def skill_source(self) -> Path:
        return self.repo_root / "skills" / "llm-wiki"

    @property
    def hermes_skill_dest(self) -> Path:
        return self.hermes_home / "skills" / "llm-wiki"

    @property
    def claude_skill_dest(self) -> Path:
        return self.claude_skills_dir / "llm-wiki"

    @property
    def codex_skill_dest(self) -> Path:
        return self.codex_skills_dir / "llm-wiki"


def repo_root_from_script(script_file: str) -> Path:
    return Path(script_file).resolve().parents[2]


def stable_repo_root(repo_root: Path) -> Path:
    """Resolve to the main git worktree so generated hooks survive worktree churn.

    Installed hooks bake an absolute checkout path (`uv --project <root>` plus the
    helper script path). When setup runs from an ephemeral git worktree that is
    later removed, every hook invocation fails with "No such file or directory".
    The main worktree lives for the repository's lifetime, so prefer it. Falls
    back to the given root when git is unavailable or the layout is unexpected.
    """
    try:
        completed = subprocess.run(
            [
                "git",
                "-C",
                str(repo_root),
                "rev-parse",
                "--path-format=absolute",
                "--git-common-dir",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return repo_root

    common_dir = completed.stdout.strip()
    if not common_dir:
        return repo_root

    main_worktree = Path(common_dir).parent
    if (main_worktree / "scripts" / "agent_hooks").is_dir():
        return main_worktree
    return repo_root


def parse_env_file(env_file: Path) -> dict[str, str]:
    if not env_file.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").strip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = _clean_env_value(value.strip())
        if key:
            values[key] = value
    return values


def _clean_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    if " #" in value:
        value = value.split(" #", 1)[0].rstrip()
    return value


def load_env(env_file: Path, process_env: Mapping[str, str] | None = None) -> dict[str, str]:
    merged = parse_env_file(env_file)
    merged.update(dict(os.environ if process_env is None else process_env))
    return merged


def resolve_config(
    *,
    agent: str,
    repo_root: Path,
    env_file: Path | None,
    process_env: Mapping[str, str] | None = None,
    server_name: str | None = None,
    server_url: str | None = None,
    dry_run: bool = False,
    claude_scope: str | None = None,
    codex_config_path: str | None = None,
    install_hooks: bool | None = None,
    claude_settings_path: str | None = None,
) -> ResolvedConfig:
    effective_env_file = (env_file or repo_root / ".env").expanduser().resolve()
    env = load_env(effective_env_file, process_env)
    default_server_name = DEFAULT_SERVER_NAMES[agent]
    resolved_server_name = server_name or env.get("LLM_WIKI_MCP_SERVER_NAME") or default_server_name
    resolved_server_url = server_url or env.get("LLM_WIKI_MCP_URL") or build_server_url(env)

    hermes_home = Path(env.get("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser()
    claude_skills_dir = Path(
        env.get("CLAUDE_SKILLS_DIR", str(Path.home() / ".claude" / "skills"))
    ).expanduser()
    codex_home = Path(env.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser()
    codex_skills_dir = Path(env.get("CODEX_SKILLS_DIR", str(codex_home / "skills"))).expanduser()
    resolved_codex_config_path = Path(
        codex_config_path or env.get("CODEX_CONFIG_PATH", str(codex_home / "config.toml"))
    ).expanduser()
    resolved_install_hooks = (
        parse_bool(env.get("LLM_WIKI_INSTALL_HOOKS"), default=True)
        if install_hooks is None
        else install_hooks
    )
    hermes_hooks_dir = Path(
        env.get("HERMES_LLM_WIKI_HOOKS_DIR", str(hermes_home / "hooks" / "llm-wiki"))
    ).expanduser()
    claude_hooks_dir = Path(
        env.get("CLAUDE_HOOKS_DIR", str(Path.home() / ".claude" / "hooks" / "llm-wiki"))
    ).expanduser()
    resolved_claude_settings_path = Path(
        claude_settings_path
        or env.get("CLAUDE_SETTINGS_PATH", str(Path.home() / ".claude" / "settings.json"))
    ).expanduser()
    codex_hooks_dir = Path(
        env.get("CODEX_LLM_WIKI_HOOKS_DIR", str(codex_home / "hooks" / "llm-wiki"))
    ).expanduser()
    codex_hooks_json_path = Path(
        env.get("CODEX_HOOKS_JSON_PATH", str(codex_home / "hooks.json"))
    ).expanduser()

    return ResolvedConfig(
        repo_root=repo_root,
        env_file=effective_env_file,
        env=env,
        agent=agent,
        server_name=resolved_server_name,
        server_url=resolved_server_url,
        dry_run=dry_run,
        claude_scope=claude_scope or env.get("CLAUDE_MCP_SCOPE", "user"),
        hermes_home=hermes_home,
        claude_skills_dir=claude_skills_dir,
        codex_home=codex_home,
        codex_skills_dir=codex_skills_dir,
        codex_config_path=resolved_codex_config_path,
        install_hooks=resolved_install_hooks,
        hermes_hooks_dir=hermes_hooks_dir,
        claude_hooks_dir=claude_hooks_dir,
        claude_settings_path=resolved_claude_settings_path,
        codex_hooks_dir=codex_hooks_dir,
        codex_hooks_json_path=codex_hooks_json_path,
    )


def build_server_url(env: Mapping[str, str]) -> str:
    scheme = env.get("LLM_WIKI_MCP_SCHEME", "http")
    host = env.get("LLM_WIKI_MCP_HOST") or env.get("KB_HOST", "127.0.0.1")
    port = env.get("KB_PORT", "9999")
    path = env.get("KB_MCP_PATH", "/mcp")
    if host == "0.0.0.0":
        host = "127.0.0.1"
    if path and not path.startswith("/"):
        path = f"/{path}"
    display_host = host if host.startswith("[") or ":" not in host else f"[{host}]"
    return f"{scheme}://{display_host}:{port}{path}"


def parse_bool(value: str | None, *, default: bool) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}
