from __future__ import annotations

import json
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from setup_support.config import ResolvedConfig

CONTEXT_HOOK_NAME = "llm-wiki-context-hook.sh"
STOP_HOOK_NAME = "llm-wiki-stop-hook.sh"


@dataclass(frozen=True)
class HookInstallResult:
    context_hook: Path
    stop_hook: Path
    settings_path: Path | None = None
    settings_changed: bool = False


def install_agent_hooks(config: ResolvedConfig) -> HookInstallResult | None:
    if not config.install_hooks:
        print("LLM Wiki hook setup disabled; skipping agent hook installation.")
        return None

    hooks_dir = hooks_dir_for_agent(config)
    context_hook = hooks_dir / CONTEXT_HOOK_NAME
    stop_hook = hooks_dir / STOP_HOOK_NAME
    if config.dry_run:
        print(f"[dry-run] install LLM Wiki hooks into {hooks_dir}")
    else:
        hooks_dir.mkdir(parents=True, exist_ok=True)
        context_hook.write_text(render_hook_script(config, mode="context"), encoding="utf-8")
        stop_hook.write_text(
            render_hook_script(
                config,
                mode="stop",
                extra_args=["--claude-stop-json"] if config.agent == "claude" else [],
            ),
            encoding="utf-8",
        )
        context_hook.chmod(0o755)
        stop_hook.chmod(0o755)
        write_hooks_readme(config, hooks_dir, context_hook, stop_hook)

    settings_changed = False
    settings_path: Path | None = None
    if config.agent == "claude":
        settings_path = config.claude_settings_path
        settings_changed = merge_claude_hook_settings(
            settings_path=settings_path,
            context_command=str(context_hook),
            stop_command=str(stop_hook),
            dry_run=config.dry_run,
        )
    elif config.agent in {"hermes", "codex"}:
        print(
            f"Installed reusable LLM Wiki hook commands for {config.agent}. "
            "Wire them into that client's native hook/plugin/wrapper mechanism if available."
        )

    return HookInstallResult(
        context_hook=context_hook,
        stop_hook=stop_hook,
        settings_path=settings_path,
        settings_changed=settings_changed,
    )


def hooks_dir_for_agent(config: ResolvedConfig) -> Path:
    if config.agent == "claude":
        return config.claude_hooks_dir
    if config.agent == "codex":
        return config.codex_hooks_dir
    return config.hermes_hooks_dir


def render_hook_script(
    config: ResolvedConfig,
    *,
    mode: str,
    extra_args: list[str] | None = None,
) -> str:
    helper = config.repo_root / "scripts" / "agent_hooks" / "llm_wiki_agent_hook.py"
    quoted_repo = shlex.quote(str(config.repo_root))
    quoted_helper = shlex.quote(str(helper))
    quoted_server_name = shlex.quote(config.server_name)
    quoted_server_url = shlex.quote(config.server_url)
    quoted_mode = shlex.quote(mode)
    rendered_extra = " ".join(shlex.quote(arg) for arg in (extra_args or []))
    if rendered_extra:
        rendered_extra = f" {rendered_extra}"

    return f"""#!/usr/bin/env bash
set -euo pipefail

if [ -z "${{LLM_WIKI_MCP_SERVER_NAME:-}}" ]; then
  LLM_WIKI_MCP_SERVER_NAME={quoted_server_name}
fi
if [ -z "${{LLM_WIKI_MCP_URL:-}}" ]; then
  LLM_WIKI_MCP_URL={quoted_server_url}
fi
export LLM_WIKI_MCP_SERVER_NAME LLM_WIKI_MCP_URL

exec uv --project {quoted_repo} run python {quoted_helper} {quoted_mode} \\
  --server-name "$LLM_WIKI_MCP_SERVER_NAME" \\
  --server-url "$LLM_WIKI_MCP_URL"{rendered_extra} "$@"
"""


def write_hooks_readme(
    config: ResolvedConfig,
    hooks_dir: Path,
    context_hook: Path,
    stop_hook: Path,
) -> None:
    readme = hooks_dir / "README.md"
    readme.write_text(
        f"""# LLM Wiki agent hooks

Installed by `uv run python scripts/main.py --agent {config.agent}` from:

`{config.repo_root}`

## Commands

- User input context loader: `{context_hook}`
- Stop/update enforcer: `{stop_hook}`

The context hook queries `{config.server_name}` at `{config.server_url}` with `kb_search_notes`
and prints a compact orientation block.

The stop hook asks the agent to run a final LLM Wiki update pass through MCP before it finishes.
It should write only durable facts/decisions/procedures, update `index.md`/`log.md` when
content changes, and use `content_hash` as `if_hash` for safe updates.

Claude Code user-level setup is merged into `{config.claude_settings_path}` when `--agent claude`
is used. Hermes/Hermess and Codex do not share Claude's JSON hook schema; wire these scripts into
the client's native hook/plugin/wrapper mechanism when available.
""",
        encoding="utf-8",
    )


def merge_claude_hook_settings(
    *,
    settings_path: Path,
    context_command: str,
    stop_command: str,
    dry_run: bool,
) -> bool:
    settings = load_json_object(settings_path)
    hooks = settings.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        hooks = {}
        settings["hooks"] = hooks

    changed = False
    changed |= ensure_claude_hook_command(
        hooks,
        event="UserPromptSubmit",
        command=context_command,
        timeout=5,
    )
    changed |= ensure_claude_hook_command(
        hooks,
        event="Stop",
        command=stop_command,
        timeout=10,
    )

    if changed:
        if dry_run:
            print(f"[dry-run] merge Claude LLM Wiki hooks into {settings_path}")
        else:
            settings_path.parent.mkdir(parents=True, exist_ok=True)
            settings_path.write_text(
                json.dumps(settings, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(f"Merged Claude LLM Wiki hooks into {settings_path}.")
    else:
        print(f"Claude LLM Wiki hooks already exist in {settings_path}; not duplicating.")
    return changed


def load_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Cannot parse Claude settings JSON: {path}") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"Claude settings must be a JSON object: {path}")
    return parsed


def ensure_claude_hook_command(
    hooks: dict[str, Any],
    *,
    event: str,
    command: str,
    timeout: int,
) -> bool:
    event_entries = hooks.setdefault(event, [])
    if not isinstance(event_entries, list):
        event_entries = []
        hooks[event] = event_entries

    if claude_hook_command_exists(event_entries, command):
        return False

    event_entries.append(
        {
            "hooks": [
                {
                    "type": "command",
                    "command": command,
                    "timeout": timeout,
                }
            ]
        }
    )
    return True


def claude_hook_command_exists(entries: list[Any], command: str) -> bool:
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        hook_items = entry.get("hooks")
        if not isinstance(hook_items, list):
            continue
        for hook in hook_items:
            if isinstance(hook, dict) and hook.get("command") == command:
                return True
    return False
