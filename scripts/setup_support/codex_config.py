from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CodexConfigResult:
    changed: bool
    reason: str


def add_codex_mcp_server(
    config_path: Path, server_name: str, server_url: str, *, dry_run: bool
) -> CodexConfigResult:
    existing = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    parsed = _parse_toml(existing, config_path)
    servers = _mcp_servers(parsed)

    if server_name in servers:
        existing_url = str(servers[server_name].get("url", ""))
        return CodexConfigResult(
            changed=False,
            reason=(
                f"Codex MCP server '{server_name}' already exists at "
                f"{existing_url or '<unknown url>'}; not overwriting."
            ),
        )

    duplicate_name = _server_name_for_url(servers, server_url)
    if duplicate_name is not None:
        return CodexConfigResult(
            changed=False,
            reason=(
                f"Codex MCP URL {server_url} already exists as '{duplicate_name}'; "
                "not adding duplicate."
            ),
        )

    block = _codex_server_block(server_name, server_url)
    if dry_run:
        return CodexConfigResult(
            changed=True,
            reason=(
                f"[dry-run] would append Codex MCP server '{server_name}' "
                f"to {config_path}:\n{block.rstrip()}"
            ),
        )

    config_path.parent.mkdir(parents=True, exist_ok=True)
    updated = f"{existing.rstrip()}\n\n{block}" if existing.strip() else block
    config_path.write_text(updated, encoding="utf-8")
    return CodexConfigResult(
        changed=True, reason=f"Added Codex MCP server '{server_name}' to {config_path}."
    )


def _parse_toml(content: str, config_path: Path) -> dict[str, Any]:
    if not content.strip():
        return {}
    try:
        parsed = tomllib.loads(content)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"Cannot parse existing Codex config {config_path}: {exc}") from exc
    return parsed


def _mcp_servers(parsed: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw_servers = parsed.get("mcp_servers", {})
    if not isinstance(raw_servers, dict):
        return {}
    return {name: value for name, value in raw_servers.items() if isinstance(value, dict)}


def _server_name_for_url(servers: dict[str, dict[str, Any]], server_url: str) -> str | None:
    for name, server_config in servers.items():
        if str(server_config.get("url", "")) == server_url:
            return name
    return None


def _codex_server_block(server_name: str, server_url: str) -> str:
    table_key = _toml_table_key(server_name)
    return f"""[mcp_servers.{table_key}]
url = {json.dumps(server_url)}
startup_timeout_sec = 30
tool_timeout_sec = 120
default_tools_approval_mode = "prompt"
"""


def _toml_table_key(server_name: str) -> str:
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", server_name):
        return server_name
    return json.dumps(server_name)
