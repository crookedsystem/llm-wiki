#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

# When invoked directly as a script (e.g. `python scripts/agent_hooks/llm_wiki_agent_hook.py`),
# sys.path[0] is this file's directory, so the sibling `prompts` package under `scripts/` is not
# importable. Put `scripts/` on the path so the import below works regardless of invocation.
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from prompts.agent_hook import (  # noqa: E402 - import follows the sys.path bootstrap above
    STOP_UPDATE_REASON,
)

from agent_hooks.llm_wiki_context_client import (  # noqa: E402 - import follows sys.path bootstrap
    load_context,
)
from agent_hooks.llm_wiki_context_formatter import (  # noqa: E402 - import follows sys.path bootstrap
    DEFAULT_LIMIT,
    format_context_block,
    format_context_error,
)

__all__ = [
    "STOP_UPDATE_REASON",
    "extract_prompt",
    "format_context_block",
    "format_context_error",
    "load_context",
    "main",
]


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    raw_stdin = sys.stdin.read()
    event = parse_event(raw_stdin)

    if args.mode == "context":
        query = args.query or extract_prompt(event) or raw_stdin.strip()
        if not query:
            return 0
        return run_context_mode(args, query)

    return run_stop_mode(args, event)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="LLM Wiki agent hook helper")
    parser.add_argument("mode", choices=("context", "stop"))
    parser.add_argument(
        "--server-url",
        default=os.environ.get("LLM_WIKI_MCP_URL", "http://127.0.0.1:9999/mcp"),
        help="Streamable HTTP MCP endpoint",
    )
    parser.add_argument(
        "--server-name",
        default=os.environ.get("LLM_WIKI_MCP_SERVER_NAME", "llm_wiki"),
        help="Display name used in emitted context",
    )
    parser.add_argument("--query", help="Override user prompt/query text for context mode")
    parser.add_argument(
        "--context-mode",
        choices=("prompt", "prewrite", "stop"),
        default=os.environ.get("LLM_WIKI_HOOK_CONTEXT_MODE", "prompt"),
        help="kb_context mode when the server supports link context",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=int(os.environ.get("LLM_WIKI_HOOK_SEARCH_LIMIT", str(DEFAULT_LIMIT))),
        help="Maximum search results to inject",
    )
    parser.add_argument(
        "--path-prefix",
        default=os.environ.get("LLM_WIKI_HOOK_PATH_PREFIX"),
        help="Optional kb_search_notes path_prefix filter",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.environ.get("LLM_WIKI_HOOK_TIMEOUT", "4")),
        help="MCP call timeout in seconds",
    )
    parser.add_argument(
        "--block-json",
        "--claude-stop-json",
        dest="block_json",
        action="store_true",
        help=(
            "Emit Stop-hook JSON (decision=block) that blocks once and asks the model to update "
            "the wiki. Works for Claude Code and Codex, which share the same Stop-hook schema. "
            "`--claude-stop-json` is a backward-compatible alias."
        ),
    )
    return parser


def parse_event(raw_stdin: str) -> Mapping[str, Any]:
    if not raw_stdin.strip():
        return {}
    try:
        parsed = json.loads(raw_stdin)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, Mapping) else {}


def extract_prompt(event: Mapping[str, Any]) -> str:
    preferred_keys = (
        "prompt",
        "user_prompt",
        "userPrompt",
        "message",
        "input",
        "text",
        "query",
    )
    for key in preferred_keys:
        value = event.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    nested = event.get("payload") or event.get("data")
    if isinstance(nested, Mapping):
        nested_prompt = extract_prompt(nested)
        if nested_prompt:
            return nested_prompt
    return ""


def run_context_mode(args: argparse.Namespace, query: str) -> int:
    try:
        payload = asyncio.run(
            load_context(
                server_url=args.server_url,
                query=query,
                mode=args.context_mode,
                limit=max(args.limit, 1),
                path_prefix=args.path_prefix,
                timeout_seconds=max(args.timeout, 0.5),
            )
        )
    except Exception as exc:  # noqa: BLE001 - hooks must fail open instead of blocking prompts.
        print(format_context_error(args.server_name, args.server_url, exc))
        return 0

    print(
        format_context_block(
            args.server_name,
            args.server_url,
            payload,
            max_results=max(args.limit, 1),
        )
    )
    return 0


def run_stop_mode(args: argparse.Namespace, event: Mapping[str, Any]) -> int:
    if is_stop_hook_active(event):
        return 0

    if args.block_json:
        print(json.dumps({"decision": "block", "reason": STOP_UPDATE_REASON}, ensure_ascii=False))
    else:
        print(STOP_UPDATE_REASON)
    return 0


def is_stop_hook_active(event: Mapping[str, Any]) -> bool:
    value = event.get("stop_hook_active") or event.get("stopHookActive")
    return bool(value)


if __name__ == "__main__":
    raise SystemExit(main())
