from __future__ import annotations

import argparse
import sys
from pathlib import Path

from setup_support.config import (
    DEFAULT_SERVER_NAMES,
    repo_root_from_script,
    resolve_config,
    stable_repo_root,
)
from setup_support.installers import install_agent

AGENTS = tuple(DEFAULT_SERVER_NAMES)


def run(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    repo_root = stable_repo_root(repo_root_from_script(__file__))
    status = 0
    for agent in selected_agents(args.agent):
        config = resolve_config(
            agent=agent,
            repo_root=repo_root,
            env_file=Path(args.env_file) if args.env_file else None,
            server_name=args.server_name,
            server_url=args.server_url,
            dry_run=args.dry_run,
            claude_scope=args.scope,
            codex_config_path=args.config,
            install_hooks=args.install_hooks,
            claude_settings_path=args.claude_settings,
        )
        print(f"== {agent} ==")
        print(f"Using env file: {config.env_file}")
        print(f"Resolved MCP server: {config.server_name} -> {config.server_url}")
        result = install_agent(config)
        if result != 0:
            status = result
    return status


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Install LLM Wiki MCP and skill configuration for Hermes/Hermess, "
            "Claude Code, and Codex."
        ),
    )
    parser.add_argument(
        "--agent",
        choices=AGENTS,
        action="append",
        help="agent integration to configure; repeatable, defaults to all agents",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print actions without writing files or changing configs",
    )
    parser.add_argument("--env-file", help="dotenv file to read; defaults to the repository .env")
    parser.add_argument(
        "--server-url", help="override LLM_WIKI_MCP_URL / KB_HOST+KB_PORT+KB_MCP_PATH"
    )
    parser.add_argument("--server-name", help="override LLM_WIKI_MCP_SERVER_NAME")
    parser.add_argument("--scope", help="Claude MCP scope; defaults to CLAUDE_MCP_SCOPE or user")
    parser.add_argument(
        "--config", help="Codex config path; defaults to CODEX_CONFIG_PATH or ~/.codex/config.toml"
    )
    parser.add_argument(
        "--no-hooks",
        dest="install_hooks",
        action="store_false",
        default=None,
        help="skip installing LLM Wiki input/stop hook scaffolds",
    )
    parser.add_argument(
        "--claude-settings",
        help=(
            "Claude settings JSON path for hook merge; defaults to "
            "CLAUDE_SETTINGS_PATH or ~/.claude/settings.json"
        ),
    )
    return parser


def selected_agents(requested_agents: list[str] | None) -> list[str]:
    if requested_agents is None:
        return list(AGENTS)
    return list(dict.fromkeys(requested_agents))


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1:]))
