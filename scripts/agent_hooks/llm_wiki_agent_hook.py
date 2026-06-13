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
from pathlib import Path
from typing import Any

# When invoked directly as a script (e.g. `python scripts/agent_hooks/llm_wiki_agent_hook.py`),
# sys.path[0] is this file's directory, so the sibling `prompts` package under `scripts/` is not
# importable. Put `scripts/` on the path so the import below works regardless of invocation.
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from prompts.agent_hook import (  # noqa: E402 - import follows the sys.path bootstrap above
    CONTEXT_BLOCK_CLOSE,
    CONTEXT_BLOCK_OPEN,
    CONTEXT_EMPTY_TEMPLATE,
    CONTEXT_ERROR_TEMPLATE,
    CONTEXT_FOOTER,
    CONTEXT_HEADER_TEMPLATE,
    CONTEXT_RESULTS_INTRO,
    STOP_UPDATE_REASON,
)

DEFAULT_LIMIT = 12

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


async def load_context(
    *,
    server_url: str,
    query: str,
    mode: str,
    limit: int,
    path_prefix: str | None,
    timeout_seconds: float,
) -> dict[str, Any]:
    try:
        return await context_notes(
            server_url=server_url,
            query=query,
            mode=mode,
            limit=limit,
            path_prefix=path_prefix,
            timeout_seconds=timeout_seconds,
        )
    except Exception:
        return await search_notes(
            server_url=server_url,
            query=query,
            limit=limit,
            path_prefix=path_prefix,
            timeout_seconds=timeout_seconds,
        )


async def context_notes(
    *,
    server_url: str,
    query: str,
    mode: str,
    limit: int,
    path_prefix: str | None,
    timeout_seconds: float,
) -> dict[str, Any]:
    arguments: dict[str, Any] = {
        "query": normalize_query(query),
        "mode": mode,
        "limit": limit,
    }
    if path_prefix:
        arguments["path_prefix"] = path_prefix
    return await call_mcp_tool(
        server_url=server_url,
        tool_name="kb_context",
        arguments=arguments,
        timeout_seconds=timeout_seconds,
    )


async def search_notes(
    *,
    server_url: str,
    query: str,
    limit: int,
    path_prefix: str | None,
    timeout_seconds: float,
) -> dict[str, Any]:
    arguments: dict[str, Any] = {"query": normalize_query(query), "limit": limit}
    if path_prefix:
        arguments["path_prefix"] = path_prefix
    return await call_mcp_tool(
        server_url=server_url,
        tool_name="kb_search_notes",
        arguments=arguments,
        timeout_seconds=timeout_seconds,
    )


async def call_mcp_tool(
    *,
    server_url: str,
    tool_name: str,
    arguments: dict[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    from mcp.client.streamable_http import streamablehttp_client

    from mcp import ClientSession

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
        result = await session.call_tool(tool_name, arguments, read_timeout_seconds=timeout)
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
    return CONTEXT_ERROR_TEMPLATE.format(
        server_name=server_name,
        server_url=server_url,
        error_type=type(exc).__name__,
    )


def format_context_block(
    server_name: str,
    server_url: str,
    payload: Mapping[str, Any],
    *,
    max_results: int = DEFAULT_LIMIT,
) -> str:
    if any(
        isinstance(payload.get(key), list)
        for key in ("orientation", "broken_links", "link_targets", "suggested_links")
    ):
        return format_link_context_block(
            server_name,
            server_url,
            payload,
            max_results=max_results,
        )

    sections = payload.get("sections")
    if isinstance(sections, list):
        return format_link_context_block(
            server_name,
            server_url,
            payload,
            max_results=max_results,
        )

    results = payload.get("results")
    if not isinstance(results, list) or not results:
        return CONTEXT_EMPTY_TEMPLATE.format(server_name=server_name, server_url=server_url)

    lines = [
        CONTEXT_BLOCK_OPEN,
        CONTEXT_HEADER_TEMPLATE.format(server_name=server_name, server_url=server_url),
        CONTEXT_RESULTS_INTRO,
    ]
    for result in results[:max_results]:
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

    lines.extend([CONTEXT_FOOTER, CONTEXT_BLOCK_CLOSE])
    return "\n".join(lines)


def format_link_context_block(
    server_name: str,
    server_url: str,
    payload: Mapping[str, Any],
    *,
    max_results: int,
) -> str:
    mode = str(payload.get("mode") or "prompt")
    lines = [
        CONTEXT_BLOCK_OPEN,
        CONTEXT_HEADER_TEMPLATE.format(server_name=server_name, server_url=server_url),
        f"Wiki link context from `kb_context` (mode={mode}):",
    ]

    usage = payload.get("usage")
    if isinstance(usage, list) and usage:
        lines.append("Usage:")
        for item in usage[:3]:
            lines.append(f"- {str(item)[:240]}")

    entity_guidance = payload.get("entity_guidance")
    if isinstance(entity_guidance, Mapping):
        lines.append("Entity guidance:")
        criteria = entity_guidance.get("criteria")
        if isinstance(criteria, list):
            for criterion in criteria[:2]:
                lines.append(f"- {str(criterion)[:240]}")
        prewrite_checks = entity_guidance.get("prewrite_checks")
        if isinstance(prewrite_checks, list):
            for check in prewrite_checks[:2]:
                lines.append(f"- {str(check)[:240]}")

    printed = _append_link_context(lines, payload, max_results=max_results)
    if printed == 0:
        lines.append("No link context candidates were found; use kb_search_notes for evidence.")

    lines.extend([CONTEXT_FOOTER, CONTEXT_BLOCK_CLOSE])
    return "\n".join(lines)


def _append_link_context(
    lines: list[str],
    payload: Mapping[str, Any],
    *,
    max_results: int,
) -> int:
    printed = 0
    printed += _append_context_references(
        lines,
        "orientation",
        payload.get("orientation"),
        max_results=max_results - printed,
    )
    printed += _append_broken_links(
        lines,
        payload.get("broken_links"),
        max_results=max_results - printed,
    )
    printed += _append_context_references(
        lines,
        "link_targets",
        payload.get("link_targets"),
        max_results=max_results - printed,
    )
    printed += _append_suggested_links(
        lines,
        payload.get("suggested_links"),
        max_results=max_results - printed,
    )
    if printed > 0:
        return printed
    return _append_legacy_sections(lines, payload, max_results=max_results)


def _append_context_references(
    lines: list[str],
    label: str,
    value: object,
    *,
    max_results: int,
) -> int:
    if max_results <= 0:
        return 0
    references = value if isinstance(value, list) else []
    if not references:
        return 0
    lines.append(label)
    printed = 0
    for reference in references:
        if printed >= max_results or not isinstance(reference, Mapping):
            break
        lines.extend(_format_context_reference(reference))
        printed += 1
    return printed


def _append_broken_links(
    lines: list[str],
    value: object,
    *,
    max_results: int,
) -> int:
    if max_results <= 0:
        return 0
    broken_links = value if isinstance(value, list) else []
    if not broken_links:
        return 0
    lines.append("broken_links")
    printed = 0
    for link in broken_links:
        if printed >= max_results or not isinstance(link, Mapping):
            break
        lines.extend(_format_broken_link(link))
        printed += 1
    return printed


def _append_suggested_links(
    lines: list[str],
    value: object,
    *,
    max_results: int,
) -> int:
    if max_results <= 0:
        return 0
    suggested_links = value if isinstance(value, list) else []
    if not suggested_links:
        return 0
    lines.append("suggested_links")
    printed = 0
    for link in suggested_links:
        if printed >= max_results or not isinstance(link, Mapping):
            break
        lines.extend(_format_suggested_link(link))
        printed += 1
    return printed


def _append_legacy_sections(
    lines: list[str],
    payload: Mapping[str, Any],
    *,
    max_results: int,
) -> int:
    printed = 0
    raw_sections = payload.get("sections")
    sections = raw_sections if isinstance(raw_sections, list) else []
    for section in sections:
        if printed >= max_results or not isinstance(section, Mapping):
            continue
        raw_notes = section.get("notes")
        notes = raw_notes if isinstance(raw_notes, list) else []
        if not notes:
            continue
        section_name = str(section.get("name") or "context")
        purpose = str(section.get("purpose") or "").strip()
        suffix = f" — {purpose[:180]}" if purpose else ""
        lines.append(f"{section_name}{suffix}")
        for note in notes:
            if printed >= max_results or not isinstance(note, Mapping):
                break
            lines.extend(_format_context_note(note))
            printed += 1
    return printed


def _format_context_reference(reference: Mapping[str, Any]) -> list[str]:
    path = str(reference.get("path") or "(unknown)")
    title = str(reference.get("title") or path)
    page_type = str(reference.get("page_type") or "unknown")
    relation = str(reference.get("relation") or "reference")
    content_hash = str(reference.get("content_hash") or "")
    raw_tags = reference.get("tags")
    tags = raw_tags if isinstance(raw_tags, list) else []
    tag_suffix = f" tags={','.join(map(str, tags[:5]))}" if tags else ""
    hash_suffix = f" hash={content_hash[:12]}" if content_hash else ""
    lines = [
        f"- [[{path.removesuffix('.md')}]] — {title} "
        f"({relation}; {page_type}{tag_suffix}{hash_suffix})"
    ]
    followup_search = str(reference.get("followup_search") or "").strip()
    if followup_search:
        lines.append(f"  - verify: kb_search_notes query={followup_search[:200]}")
    return lines


def _format_broken_link(link: Mapping[str, Any]) -> list[str]:
    source_path = str(link.get("source_path") or "(unknown)")
    source_hash = str(link.get("source_content_hash") or "")
    target = str(link.get("normalized_target") or link.get("target") or "(unknown)")
    occurrences = link.get("occurrences") or 1
    suggested_path = str(link.get("suggested_path") or "")
    hash_suffix = f" hash={source_hash[:12]}" if source_hash else ""
    lines = [
        f"- [[{source_path.removesuffix('.md')}]] -> [[{target}]] "
        f"(missing x{occurrences}{hash_suffix})"
    ]
    if suggested_path:
        lines.append(f"  - suggested_path: {suggested_path}")
    followup_search = str(link.get("followup_search") or "").strip()
    if followup_search:
        lines.append(f"  - verify: kb_search_notes query={followup_search[:200]}")
    return lines


def _format_suggested_link(link: Mapping[str, Any]) -> list[str]:
    source_path = str(link.get("source_path") or "(unknown)")
    source_hash = str(link.get("source_content_hash") or "")
    target_path = str(link.get("target_path") or "(unknown)")
    relation = str(link.get("relation") or "add_link")
    reason = str(link.get("reason") or "").strip()
    hash_suffix = f" hash={source_hash[:12]}" if source_hash else ""
    lines = [
        f"- [[{source_path.removesuffix('.md')}]] -> "
        f"[[{target_path.removesuffix('.md')}]] ({relation}{hash_suffix})"
    ]
    if reason:
        lines.append(f"  - why: {reason[:240]}")
    followup_search = str(link.get("followup_search") or "").strip()
    if followup_search:
        lines.append(f"  - verify: kb_search_notes query={followup_search[:200]}")
    return lines


def _format_context_note(note: Mapping[str, Any]) -> list[str]:
    path = str(note.get("path") or "(unknown)")
    title = str(note.get("title") or path)
    page_type = str(note.get("page_type") or "unknown")
    content_hash = str(note.get("content_hash") or "")
    raw_tags = note.get("tags")
    tags = raw_tags if isinstance(raw_tags, list) else []
    tag_suffix = f" tags={','.join(map(str, tags[:5]))}" if tags else ""
    hash_suffix = f" hash={content_hash[:12]}" if content_hash else ""
    lines = [f"- [[{path.removesuffix('.md')}]] — {title} ({page_type}{tag_suffix}{hash_suffix})"]
    why_included = str(note.get("why_included") or "").strip()
    if why_included:
        lines.append(f"  - why: {why_included[:240]}")
    raw_matches = note.get("matches")
    matches = raw_matches if isinstance(raw_matches, list) else []
    for match in matches[:2]:
        if not isinstance(match, Mapping):
            continue
        snippet = str(match.get("snippet") or "").strip()
        line = match.get("line")
        if snippet:
            lines.append(f"  - L{line}: {snippet[:240]}")
    return lines


if __name__ == "__main__":
    raise SystemExit(main())
