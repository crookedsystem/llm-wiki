from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

from setup_support.codex_config import add_codex_mcp_server
from setup_support.config import ResolvedConfig
from setup_support.hooks import install_agent_hooks
from setup_support.runner import CommandRunner, copy_directory

SKILL_NAMES = ("llm-wiki", "llm-wiki-push")


def install_agent(config: ResolvedConfig) -> int:
    installers: dict[str, Callable[[ResolvedConfig], int]] = {
        "hermes": install_hermes,
        "claude": install_claude,
        "codex": install_codex,
    }
    return installers[config.agent](config)


def install_hermes(config: ResolvedConfig) -> int:
    runner = CommandRunner(dry_run=config.dry_run)
    _install_skills(config, config.hermes_home / "skills", "Hermes/Hermess")
    install_agent_hooks(config)

    if not runner.command_exists("hermes"):
        print(
            "hermes CLI not found. Add mcp/hermess.yaml manually or run this script "
            "where Hermes is installed."
        )
        return 0

    existing = runner.run(["hermes", "mcp", "list"], check=False, capture=True)
    if _has_duplicate(existing.stdout, config.server_name, config.server_url):
        return 0

    runner.run(["hermes", "mcp", "add", config.server_name, "--url", config.server_url])
    runner.run(["hermes", "mcp", "test", config.server_name], check=False)
    print(f"Hermes/Hermess MCP server '{config.server_name}' points to {config.server_url}.")
    print("Restart Hermes or use /reload-mcp if needed.")
    return 0


def install_claude(config: ResolvedConfig) -> int:
    runner = CommandRunner(dry_run=config.dry_run)
    _install_skills(config, config.claude_skills_dir, "Claude")
    install_agent_hooks(config)

    if not runner.command_exists("claude"):
        print(
            "claude CLI not found. Copy mcp/claude.json into a project .mcp.json "
            "or use Claude's --mcp-config."
        )
        return 0

    existing_by_name = runner.run(
        ["claude", "mcp", "get", config.server_name], check=False, capture=True
    )
    if not config.dry_run and existing_by_name.returncode == 0:
        print(f"Claude MCP server '{config.server_name}' already exists; not overwriting.")
        return 0

    existing = runner.run(["claude", "mcp", "list"], check=False, capture=True)
    if _has_duplicate(existing.stdout, config.server_name, config.server_url):
        return 0

    runner.run(
        [
            "claude",
            "mcp",
            "add",
            "-s",
            config.claude_scope,
            "--transport",
            "http",
            config.server_name,
            config.server_url,
        ]
    )
    runner.run(["claude", "mcp", "get", config.server_name], check=False)
    print(f"Claude MCP server '{config.server_name}' points to {config.server_url}.")
    print("Restart Claude Code if needed.")
    return 0


def install_codex(config: ResolvedConfig) -> int:
    _install_skills(config, config.codex_skills_dir, "Codex")
    install_agent_hooks(config)
    result = add_codex_mcp_server(
        config.codex_config_path,
        config.server_name,
        config.server_url,
        dry_run=config.dry_run,
    )
    print(result.reason)
    if result.changed and not config.dry_run:
        print("Restart Codex so it reloads config and skills.")
    return 0


def _install_skills(config: ResolvedConfig, destination_root: Path, agent_label: str) -> None:
    for skill_name in SKILL_NAMES:
        source = config.repo_root / "skills" / skill_name
        destination = destination_root / skill_name
        copy_directory(source, destination, dry_run=config.dry_run)
        print(f"Installed {agent_label} skill: {destination}")


def _has_duplicate(output: str, server_name: str, server_url: str) -> bool:
    if not output.strip():
        return False
    if _contains_token(output, server_name):
        print(f"MCP server '{server_name}' already exists; not overwriting.")
        return True
    if server_url in output:
        print(
            f"MCP URL {server_url} is already configured under another name; not adding duplicate."
        )
        return True
    return False


def _contains_token(output: str, token: str) -> bool:
    return re.search(rf"(^|[^A-Za-z0-9_-]){re.escape(token)}([^A-Za-z0-9_-]|$)", output) is not None
