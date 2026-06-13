from __future__ import annotations

import asyncio
import json

from agent_hooks.llm_wiki_agent_hook import (
    STOP_UPDATE_REASON,
    extract_prompt,
    format_context_block,
    format_context_error,
    load_context,
    main,
)
from pytest import CaptureFixture, MonkeyPatch


def test_extract_prompt는_hook_payload에서_prompt를_찾는다() -> None:
    assert extract_prompt({"prompt": "  hello wiki  "}) == "hello wiki"
    assert extract_prompt({"payload": {"userPrompt": "nested prompt"}}) == "nested prompt"
    assert extract_prompt({"payload": {"missing": "value"}}) == ""


def test_format_context_block은_search_결과를_compact_context로_만든다() -> None:
    payload = {
        "query": "llm wiki",
        "count": 1,
        "results": [
            {
                "path": "concepts/llm-wiki.md",
                "title": "LLM Wiki",
                "page_type": "concept",
                "tags": ["llm-wiki", "mcp"],
                "content_hash": "abcdef1234567890",
                "matches": [
                    {"line": 7, "snippet": "SCHEMA.md defines page taxonomy."},
                    {"line": 9, "snippet": "index.md and log.md are updated together."},
                ],
            }
        ],
    }

    block = format_context_block("llm_wiki", "http://127.0.0.1:9999/mcp", payload)

    assert "<llm-wiki-context>" in block
    assert "[[concepts/llm-wiki]]" in block
    assert "hash=abcdef123456" in block
    assert "SCHEMA.md defines page taxonomy" in block
    assert "kb_write_note" in block
    assert "structured fields" in block
    assert "do not pass complete Markdown" in block
    assert "write complete Markdown" not in block


def test_format_context_block은_link_context를_연결후보별로_출력한다() -> None:
    payload = {
        "query": "fanplus chat",
        "mode": "prompt",
        "count": 3,
        "usage": ["Use kb_context as a link/navigation map, not as evidence text."],
        "entity_guidance": {
            "criteria": ["Create an entity for a named project or service."],
            "preferred_paths": ["entities/{project}.md"],
            "prewrite_checks": ["prewrite: run kb_search_notes with followup_search."],
        },
        "orientation": [],
        "broken_links": [
            {
                "source_path": "queries/fanplus-chat.md",
                "source_content_hash": "feedface123456",
                "target": "missing-room-rule",
                "normalized_target": "missing-room-rule",
                "occurrences": 1,
                "suggested_path": "concepts/missing-room-rule.md",
                "followup_search": "missing-room-rule",
            }
        ],
        "link_targets": [
            {
                "path": "entities/fanplus-api.md",
                "title": "fanplus-api",
                "page_type": "entity",
                "tags": ["project-context"],
                "content_hash": "123456abcdef",
                "relation": "entity_anchor",
                "followup_search": "fanplus chat fanplus-api",
            }
        ],
        "suggested_links": [],
    }

    block = format_context_block("llm_wiki", "http://127.0.0.1:9999/mcp", payload)

    assert "Wiki link context from `kb_context`" in block
    assert "mode=prompt" in block
    assert "broken_links" in block
    assert "link_targets" in block
    assert "[[entities/fanplus-api]]" in block
    assert "[[queries/fanplus-chat]] -> [[missing-room-rule]]" in block
    assert "kb_search_notes query=missing-room-rule" in block
    assert "Create an entity for a named project or service" in block
    assert "prewrite: run kb_search_notes with followup_search" in block
    assert "fanplus chat service" not in block


def test_load_context는_kb_context_실패시_search_notes로_fallback한다(
    monkeypatch: MonkeyPatch,
) -> None:
    async def fake_context_notes(**kwargs: object) -> dict[str, object]:
        raise RuntimeError("unknown tool")

    async def fake_search_notes(**kwargs: object) -> dict[str, object]:
        return {"query": "fallback", "count": 0, "results": []}

    monkeypatch.setattr("agent_hooks.llm_wiki_agent_hook.context_notes", fake_context_notes)
    monkeypatch.setattr("agent_hooks.llm_wiki_agent_hook.search_notes", fake_search_notes)

    payload = asyncio.run(
        load_context(
            server_url="http://127.0.0.1:9999/mcp",
            query="fanplus chat",
            mode="prompt",
            limit=12,
            path_prefix=None,
            timeout_seconds=1.0,
        )
    )

    assert payload == {"query": "fallback", "count": 0, "results": []}


def test_format_context_error는_fail_open_안내를_출력한다() -> None:
    block = format_context_error("llm_wiki", "http://127.0.0.1:9999/mcp", RuntimeError("boom"))

    assert "context load failed" in block
    assert "Continue without inventing wiki contents" in block


def test_stop_mode는_claude_block_json을_출력하고_재진입을_막는다(
    capsys: CaptureFixture[str],
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "sys.stdin",
        type("FakeStdin", (), {"read": lambda self: json.dumps({"stop_hook_active": False})})(),
    )

    result = main(["stop", "--claude-stop-json"])

    output = json.loads(capsys.readouterr().out)
    assert result == 0
    assert output["decision"] == "block"
    assert STOP_UPDATE_REASON.strip() in output["reason"]

    monkeypatch.setattr(
        "sys.stdin",
        type("FakeStdin", (), {"read": lambda self: json.dumps({"stop_hook_active": True})})(),
    )
    result = main(["stop", "--claude-stop-json"])

    assert result == 0
    assert capsys.readouterr().out == ""


def test_stop_mode는_block_json_canonical_flag도_지원한다(
    capsys: CaptureFixture[str],
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "sys.stdin",
        type("FakeStdin", (), {"read": lambda self: json.dumps({"stop_hook_active": False})})(),
    )

    result = main(["stop", "--block-json"])

    output = json.loads(capsys.readouterr().out)
    assert result == 0
    assert output["decision"] == "block"
    assert STOP_UPDATE_REASON.strip() in output["reason"]
