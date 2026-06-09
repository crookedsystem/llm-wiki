from __future__ import annotations

import json

from agent_hooks.llm_wiki_agent_hook import (
    STOP_UPDATE_REASON,
    extract_prompt,
    format_context_block,
    format_context_error,
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
