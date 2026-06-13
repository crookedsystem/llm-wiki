---
name: llm-wiki-push
description: "Push an llm-wiki Markdown vault to GitHub through the llm_wiki MCP server. Use only when the user explicitly asks to push, sync, publish, or back up the LLM Wiki vault to GitHub, or explicitly invokes this skill. Do not use for ordinary note writing, search, wiki maintenance, stop-hook updates, or context-loading."
---

# LLM Wiki Push

Use this skill only for explicit vault GitHub sync requests. It is intentionally separate from the main `llm-wiki` skill so normal wiki writes never push without a direct user request.

## Tool Contract

The MCP server exposes:

- `kb_push_vault()` — commit all pending changes in `KB_VAULT_PATH` with a UTC `YYYY-MM-DD HH:MM - vault sync` commit message, then push `origin` to the current branch. The server checks GitHub CLI auth first, then falls back to `git push`.

Agent UIs may namespace the tool name. Examples:

- Hermes/Hermess: `mcp_llm_wiki_kb_push_vault`
- Claude Code: `mcp__llm-wiki__kb_push_vault`
- Codex: `kb_push_vault` under the configured `llm_wiki` MCP server

## Required Guardrail

Do not call `kb_push_vault()` unless the user explicitly asks for a GitHub push/sync/backup/publish of the vault or explicitly invokes `$llm-wiki-push`.

If the user is only writing/searching/updating notes, use the main `llm-wiki` skill and do not push.

## Workflow

1. Confirm the request is an explicit push/sync request.
2. Verify the `llm_wiki` MCP server exposes `kb_push_vault`.
3. Call `kb_push_vault()` once.
4. Report the result: whether a commit was created, the commit hash if present, branch, remote, and push tool/path.

Do not pass remote, branch, commit message, or interval options. The server owns those policies.
