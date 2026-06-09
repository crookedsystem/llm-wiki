#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from collections.abc import Mapping, Sequence
from datetime import timedelta
from typing import Any

DEFAULT_LIMIT = 5

STOP_UPDATE_REASON = """Run the LLM Wiki update pass before stopping.

Use the configured llm-wiki MCP server to:
1. search `SCHEMA.md`, `index.md`, recent `log.md`, and any affected entity/concept pages;
2. write only durable facts, decisions, relationships, reusable procedures, or open questions;
3. skip content-page writes when this turn produced no durable knowledge;
4. update `index.md` and append a compact `log.md` entry for any durable wiki change;
5. use returned `content_hash` values as `if_hash` when updating existing notes.

Do not copy private transcripts wholesale into the wiki. Summarize only durable knowledge,
then stop normally.
"""


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
        "--claude-stop-json",
        action="store_true",
        help=(
            "Emit Claude Code Stop-hook JSON that blocks once and asks the model to update the wiki"
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
            search_notes(
                server_url=args.server_url,
                query=query,
                limit=max(args.limit, 1),
                path_prefix=args.path_prefix,
                timeout_seconds=max(args.timeout, 0.5),
            )
        )
    except Exception as exc:  # noqa: BLE001 - hooks must fail open instead of blocking prompts.
        print(format_context_error(args.server_name, args.server_url, exc))
        return 0

    print(format_context_block(args.server_name, args.server_url, payload))
    return 0


def run_stop_mode(args: argparse.Namespace, event: Mapping[str, Any]) -> int:
    if is_stop_hook_active(event):
        return 0

    if args.claude_stop_json:
        print(json.dumps({"decision": "block", "reason": STOP_UPDATE_REASON}, ensure_ascii=False))
    else:
        print(STOP_UPDATE_REASON)
    return 0


def is_stop_hook_active(event: Mapping[str, Any]) -> bool:
    value = event.get("stop_hook_active") or event.get("stopHookActive")
    return bool(value)


async def search_notes(
    *,
    server_url: str,
    query: str,
    limit: int,
    path_prefix: str | None,
    timeout_seconds: float,
) -> dict[str, Any]:
    from mcp.client.streamable_http import streamablehttp_client

    from mcp import ClientSession

    arguments: dict[str, Any] = {"query": normalize_query(query), "limit": limit}
    if path_prefix:
        arguments["path_prefix"] = path_prefix

    timeout = timedelta(seconds=timeout_seconds)
    async with (
        streamablehttp_client(server_url, timeout=timeout, sse_read_timeout=timeout) as (
            read_stream,
            write_stream,
            _get_session_id,
        ),
        ClientSession(read_stream, write_stream, read_timeout_seconds=timeout) as session,
    ):
        await session.initialize()
        result = await session.call_tool("kb_search_notes", arguments, read_timeout_seconds=timeout)
    return call_tool_result_to_dict(result)


def normalize_query(query: str) -> str:
    collapsed = re.sub(r"\s+", " ", query).strip()
    return collapsed[:800]


def call_tool_result_to_dict(result: Any) -> dict[str, Any]:
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, Mapping):
        return dict(structured)

    content_items = getattr(result, "content", None) or []
    for item in content_items:
        text = getattr(item, "text", None)
        if not isinstance(text, str):
            continue
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, Mapping):
            return dict(parsed)
    return {"query": "", "count": 0, "results": []}


def format_context_error(server_name: str, server_url: str, exc: Exception) -> str:
    return (
        "<llm-wiki-context>\n"
        f"LLM Wiki MCP context load failed for `{server_name}` at `{server_url}`: "
        f"{type(exc).__name__}. Continue without inventing wiki contents; "
        "use MCP tools later if needed.\n"
        "</llm-wiki-context>"
    )


def format_context_block(server_name: str, server_url: str, payload: Mapping[str, Any]) -> str:
    results = payload.get("results")
    if not isinstance(results, list) or not results:
        return (
            "<llm-wiki-context>\n"
            f"MCP server: `{server_name}` ({server_url})\n"
            "No matching LLM Wiki notes were found for this prompt. "
            "Before creating pages, search again for specific entities/concepts "
            "and follow the `llm-wiki` skill's schema/index/log rules.\n"
            "</llm-wiki-context>"
        )

    lines = [
        "<llm-wiki-context>",
        f"MCP server: `{server_name}` ({server_url})",
        "Relevant existing wiki notes from `kb_search_notes`:",
    ]
    for result in results[:DEFAULT_LIMIT]:
        if not isinstance(result, Mapping):
            continue
        path = str(result.get("path") or "(unknown)")
        title = str(result.get("title") or path)
        page_type = str(result.get("page_type") or "unknown")
        content_hash = str(result.get("content_hash") or "")
        raw_tags = result.get("tags")
        tags = raw_tags if isinstance(raw_tags, list) else []
        tag_suffix = f" tags={','.join(map(str, tags[:5]))}" if tags else ""
        hash_suffix = f" hash={content_hash[:12]}" if content_hash else ""
        lines.append(
            f"- [[{path.removesuffix('.md')}]] — {title} ({page_type}{tag_suffix}{hash_suffix})"
        )
        raw_matches = result.get("matches")
        matches = raw_matches if isinstance(raw_matches, list) else []
        for match in matches[:2]:
            if not isinstance(match, Mapping):
                continue
            snippet = str(match.get("snippet") or "").strip()
            line = match.get("line")
            if snippet:
                lines.append(f"  - L{line}: {snippet[:240]}")

    lines.extend(
        [
            "Use this as orientation only. For updates, retrieve the full current note body "
            "when available, then write complete Markdown via `kb_write_note` with `if_hash`.",
            "</llm-wiki-context>",
        ]
    )
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
