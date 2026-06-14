"""Runtime prompts and context-block templates emitted by the agent hook.

`STOP_UPDATE_REASON` is the instruction injected at stop time. The `CONTEXT_*`
templates build the `<llm-wiki-context>` block injected at prompt time. Format
placeholders carry runtime values only.
"""

from __future__ import annotations

from typing import Final

STOP_UPDATE_REASON: Final = """Before stopping, decide whether this turn produced LLM Wiki–worthy
knowledge, then act on that decision. Do not write reflexively — judge first.

Step 1 — Judge. This turn is worth recording ONLY if it produced at least one of:
- a durable fact, decision, or the rationale behind it that outlives this conversation;
- a reusable procedure, gotcha, convention, or constraint someone would want again later;
- a relationship between entities/concepts the wiki does not already capture;
- an open question worth tracking.
It is NOT worth recording when the turn was transient: a one-off question, exploration with no
conclusion, a trivial change already self-explanatory in code/git, or knowledge the wiki already
holds. When in doubt, prefer NOT writing — low-signal notes are worse than none.

Step 2 — If nothing qualifies: stop normally without writing, and say in one line that you
judged this turn as not wiki-worthy.

Step 3 — If something qualifies, use the configured llm-wiki MCP server to:
1. call `kb_context` with `mode="stop"` or `mode="prewrite"` first when available; otherwise
   search `SCHEMA.md`, `index.md`, recent `log.md`, and any affected entity/concept pages;
2. inspect returned broken_links, link_targets, and suggested_links; if a link needs textual
   evidence, run `kb_search_notes` with the returned followup_search before writing;
3. write only the durable knowledge identified in Step 1 (summarize — never copy private
   transcripts wholesale);
4. update `index.md` and append a compact `log.md` entry for any durable wiki change;
5. use returned `content_hash` values as `if_hash` when updating existing notes.
Then stop normally.
"""

CONTEXT_BLOCK_OPEN: Final = "<llm-wiki-context>"
CONTEXT_BLOCK_CLOSE: Final = "</llm-wiki-context>"

CONTEXT_ERROR_TEMPLATE: Final = (
    "<llm-wiki-context>\n"
    "LLM Wiki MCP context load failed for `{server_name}` at `{server_url}`: "
    "{error_type}. Continue without inventing wiki contents; "
    "use MCP tools later if needed.\n"
    "</llm-wiki-context>"
)

CONTEXT_EMPTY_TEMPLATE: Final = (
    "<llm-wiki-context>\n"
    "MCP server: `{server_name}` ({server_url})\n"
    "No matching LLM Wiki link context was found for this prompt. "
    "Before creating pages, search again for specific entities/concepts "
    "and follow the `llm-wiki` skill's schema/index/log rules.\n"
    "</llm-wiki-context>"
)

CONTEXT_HEADER_TEMPLATE: Final = "MCP server: `{server_name}` ({server_url})"

CONTEXT_RESULTS_INTRO: Final = "Relevant existing wiki notes from `kb_search_notes`:"

CONTEXT_FOOTER: Final = (
    "Use this as orientation only. For updates, retrieve the full current note body "
    "when available, then resubmit the complete replacement structured fields via "
    "`kb_write_note` with `if_hash`; do not pass complete Markdown."
)
