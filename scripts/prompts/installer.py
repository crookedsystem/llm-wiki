"""Content templates rendered by the hook installer.

`HOOK_SCRIPT_TEMPLATE` is the generated bash wrapper; `HOOKS_README_TEMPLATE` is
the operator-facing README. Both use `.format` placeholders for runtime values.
Literal shell braces are escaped as `{{` / `}}`.
"""

from __future__ import annotations

from typing import Final

HOOK_SCRIPT_TEMPLATE: Final = """#!/usr/bin/env bash
set -euo pipefail

if [ -z "${{LLM_WIKI_MCP_SERVER_NAME:-}}" ]; then
  LLM_WIKI_MCP_SERVER_NAME={server_name}
fi
if [ -z "${{LLM_WIKI_MCP_URL:-}}" ]; then
  LLM_WIKI_MCP_URL={server_url}
fi
export LLM_WIKI_MCP_SERVER_NAME LLM_WIKI_MCP_URL

LLM_WIKI_HOOK_HELPER={helper}

# Fail open: a hook must never break the agent loop. If the helper checkout was
# moved or removed (e.g. an ephemeral git worktree deleted after install) or `uv`
# is not on PATH, exit quietly instead of erroring on every prompt/stop.
if [ ! -f "$LLM_WIKI_HOOK_HELPER" ]; then
  exit 0
fi
if ! command -v uv >/dev/null 2>&1; then
  exit 0
fi

exec uv --project {repo_root} run python "$LLM_WIKI_HOOK_HELPER" {mode} \\
  --server-name "$LLM_WIKI_MCP_SERVER_NAME" \\
  --server-url "$LLM_WIKI_MCP_URL"{extra} "$@"
"""

HOOKS_README_TEMPLATE: Final = """# LLM Wiki agent hooks

Installed by `uv run python scripts/main.py --agent {agent}` from:

`{repo_root}`

## Commands

- User input context loader: `{context_hook}`
- Stop/update enforcer: `{stop_hook}`

The context hook queries `{server_name}` at `{server_url}` with `kb_search_notes`
and prints a compact orientation block.

The stop hook asks the agent to run a final LLM Wiki update pass through MCP before it finishes.
It should write only durable facts/decisions/procedures, update `index.md`/`log.md` when
content changes, and use `content_hash` as `if_hash` for safe updates.

Claude Code user-level setup is merged into `{claude_settings_path}` when `--agent claude`
is used. Codex shares Claude Code's hook JSON schema (UserPromptSubmit/Stop, decision=block),
so `--agent codex` merges equivalent entries into `~/.codex/hooks.json` automatically.

Hermes/Hermess exposes only finalize-style session hooks (no Claude-style Stop re-prompt), so
wire these scripts into a Hermes plugin/wrapper or finalize hook for an out-of-loop update pass.
"""
