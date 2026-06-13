---
name: llm-wiki
description: "Use llm-wiki from Hermes/Hermess, Claude Code, or Codex to search, model, and maintain an Obsidian/Markdown LLM Wiki knowledge base. Trigger for vault, KB, wiki, Obsidian, research memory, persistent note-writing, MCP context-loading hooks, and end-of-task wiki update workflows."
---

# LLM Wiki

Use the running `llm-wiki` server as the write/search bridge to a Git-backed Obsidian or Markdown vault, then maintain that vault with the LLM Wiki pattern: raw sources stay immutable, synthesized pages stay interlinked, and every durable change updates navigation and log files.

This is the single canonical skill for Hermes/Hermess, Claude Code, and Codex. The setup scripts copy this same skill into each agent's expected skill directory; only MCP config format, install path, and tool-name prefix differ by agent.

## When to use this skill

Use it when the user asks to use an Obsidian vault, Markdown KB, personal wiki, LLM Wiki, research memory, or `llm-wiki` as persistent knowledge for an agent.

Do not use it for one-off answers that should not be saved, or when the MCP server is unavailable and the user only wants a normal chat answer.

## MCP tools used by this skill

The main wiki workflow uses these tool names:

- `kb_write_note(note_path, title, type, tags, sources, body, created, updated, confidence?, contested?, if_hash?)` — write a note inside the configured vault from structured fields. `created` and `updated` must be UTC ISO datetimes with seconds and a trailing `Z` (`YYYY-MM-DDTHH:MM:SSZ`). The server renders YAML frontmatter, the top-level title heading, the body, and provenance. Existing notes require optimistic concurrency.
- `kb_search_notes(query, limit?, path_prefix?)` — search the Markdown LLM Wiki vault and return ranked paths, titles, page types, tags, content hashes, and line snippets.

Vault and graph counters are exposed as a REST API endpoint at `GET /metrics`, not as MCP tools.
Vault GitHub push is handled by the separate `$llm-wiki-push` skill and must not be called from this skill.
Agent UIs may prefix MCP tool names. If you see prefixed names, map them back to the raw tool names above.

## Vault operating model

Keep these folders conceptually separate:

- `llm-wiki` repository — server/application code such as `src/`, `tests/`, `scripts/`.
- `KB_VAULT_PATH` — the Markdown vault opened by Obsidian and read/written by MCP tools.

Inside `KB_VAULT_PATH`, use this structure:

```text
SCHEMA.md        # conventions, page thresholds, tag taxonomy
index.md         # navigational catalog of synthesized pages
log.md           # append-only audit trail
raw/             # immutable source material and assets
entities/        # people, orgs, products, models, projects, standards
concepts/        # ideas, techniques, mechanisms, topics, principles
comparisons/     # side-by-side analyses and decision records
queries/         # valuable answered questions worth preserving
```

`raw/` is source material. `entities/`, `concepts/`, `comparisons/`, and `queries/` are synthesized wiki pages owned by the agent.

## First actions in a session

1. Confirm the MCP server is connected by listing tools or calling `kb_search_notes` with a narrow orientation query such as `index`.
2. Orient before writing. If the vault is directly readable through file tools, read `SCHEMA.md`, `index.md`, and the recent tail of `log.md`. If direct file reads are unavailable, use `kb_search_notes` for `SCHEMA`, `index`, `log`, and topic-specific searches.
3. Search for existing pages before creating new ones. Avoid duplicate entity or concept pages.
4. Decide the access mode:
   - **File-readable mode:** safe to update existing notes because you can read the complete current file, preserve existing metadata/body intentionally, and pass the exact current `content_hash` as `if_hash`.
   - **MCP-only mode:** `kb_search_notes` returns snippets, not full note bodies or every frontmatter field. Do not overwrite an existing note from snippets alone. Create new notes only, or ask the user for the full current note content before updating.

## Content model and page types

Use the `type` frontmatter value to decide where a page belongs and how readers will browse it.

| Type | Directory | Use for | Do not use for |
| --- | --- | --- | --- |
| `entity` | `entities/` | People, companies, products, models, projects, protocols, datasets, standards, APIs | Broad ideas or techniques |
| `concept` | `concepts/` | Techniques, principles, mechanisms, topics, terms, recurring patterns | Named organizations/products unless the page is about the abstract idea |
| `comparison` | `comparisons/` | Tradeoff analysis, A-vs-B decisions, rankings, matrices, migration choices | Simple summaries of one thing |
| `query` | `queries/` | A substantial answered question, investigation, synthesis, or research result worth reusing | Trivial lookups or temporary chat answers |
| `summary` | Usually `concepts/` or `queries/` | Cross-cutting overview pages and topic maps | Pages that can be classified more specifically |
| `raw` | `raw/` | Immutable source material and ingested references | Agent synthesis or conclusions |
| `schema` | `SCHEMA.md` | Vault-wide schema and operating conventions | Topic pages |
| `index` | `index.md` | Navigational catalog | Research notes |
| `log` | `log.md` | Append-only audit trail | Topic synthesis |

### Page creation thresholds

Create or update pages only when the content improves future retrieval:

- Create a new page when the entity/concept appears in 2+ sources, or is central to one important source.
- Update an existing page when new material changes, confirms, dates, or clarifies something already covered.
- Create a `comparison` page when the user is choosing between alternatives or the source compares alternatives on multiple dimensions.
- Create a `query` page when the answer is non-trivial enough that re-deriving it would waste time later.
- Do not create pages for passing mentions, minor side details, or out-of-domain material.
- Split pages that exceed about 200 lines into focused sub-pages and cross-link them.

### Required frontmatter

Every wiki page is written through structured fields that render YAML frontmatter:

```yaml
---
title: Page Title
created: YYYY-MM-DDTHH:MM:SSZ
updated: YYYY-MM-DDTHH:MM:SSZ
type: raw | entity | concept | comparison | query | summary | schema | index | log
tags: [tag-from-schema]
sources: [raw/articles/source-file.md]
confidence: high | medium | low
contested: false
---
```

`title`, `created`, `updated`, `type`, `tags`, `sources`, and `body` are required tool arguments. `created` and `updated` must be UTC ISO datetimes with seconds and a trailing `Z`, such as `2026-06-09T14:30:05Z`; date-only, non-UTC, offset, and sub-second values are invalid. `confidence` and `contested` are optional but useful. Use `confidence: low` for single-source, speculative, or fast-moving claims. Use `contested: true` when sources conflict and explain the conflict in the body.

Path and type must agree:

- `raw/**` uses `type: raw`.
- `entities/**` uses `type: entity`.
- `concepts/**` uses `type: concept` or `type: summary`.
- `comparisons/**` uses `type: comparison`.
- `queries/**` uses `type: query` or `type: summary`.
- `SCHEMA.md`, `index.md`, and `log.md` use `type: schema`, `type: index`, and `type: log` respectively.

### Page body pattern

Keep pages scannable. The tool renders `# Page Title`; pass only the section body. Prefer this shape unless the vault `SCHEMA.md` says otherwise:

```markdown
## Summary
One short paragraph explaining why this page matters.

## Key facts
- Dated, source-backed facts.
- Link important related pages with [[wikilinks]].

## Relationships
- [[related-page]] — why it matters.

## Open questions
- What remains uncertain or contested?

## Sources
- raw/articles/source-file.md
```

Every new synthesized page should have at least two useful outbound `[[wikilinks]]` when possible. If two links are impossible because the vault is new, create the most important link now and add a log note that back-links should be filled after more pages exist.

## SCHEMA.md bootstrap

If `SCHEMA.md` is missing or the user is creating a new vault, create it before writing topic pages. Do not rely on an external schema that does not exist. Write `SCHEMA.md` itself through `kb_write_note` with `type: schema`, then customize the domain/tags:

```markdown
# Wiki Schema

## Domain
[Define what this vault covers and what is out of scope.]

## Folder model
- `raw/`: immutable source material. Agents read it but do not edit it after ingest.
- `entities/`: people, organizations, products, models, projects, standards, APIs.
- `concepts/`: ideas, techniques, mechanisms, topics, recurring patterns.
- `comparisons/`: side-by-side analyses and decision records.
- `queries/`: durable answers to substantial questions.

## Naming
- Use lowercase kebab-case paths, for example `concepts/llm-wiki.md`.
- Use `[[wikilinks]]` for internal links.
- Add every synthesized page to `index.md`.
- Append every durable action to `log.md`.

## Frontmatter
Required fields: `title`, `created`, `updated`, `type`, `tags`, `sources`. `created` and `updated` use UTC ISO datetimes with seconds and a trailing `Z` (`YYYY-MM-DDTHH:MM:SSZ`).
Allowed `type` values: `raw`, `entity`, `concept`, `comparison`, `query`, `summary`, `schema`, `index`, `log`.

## Tag taxonomy
[List 10-20 allowed tags for this domain before using them.]

## Page thresholds
- Create a page when an entity/concept appears in 2+ sources or is central to one important source.
- Do not create pages for passing mentions.
- Split pages over about 200 lines.
- Mark contradictions with `contested: true` and explain both claims with dates and sources.
```

## index.md structure

`index.md` is the map readers use before search. Keep it sectioned by page type and alphabetized within each section.

```markdown
# Wiki Index

> Content catalog for synthesized wiki pages.
> Last updated: YYYY-MM-DD | Total pages: N

## Entities
- [[entities/example-company]] — One-line reason this page exists.

## Concepts
- [[concepts/llm-wiki]] — Agent-maintained Markdown knowledge base pattern.

## Comparisons
- [[comparisons/rag-vs-llm-wiki]] — Tradeoffs between retrieval and compiled wiki context.

## Queries
- [[queries/how-to-connect-obsidian]] — Answer on sharing KB_VAULT_PATH with Obsidian.
```

When any section grows past roughly 50 entries, split it by first letter or subdomain. When the index grows past roughly 200 entries, add `_meta/topic-map.md` for thematic browsing.

## log.md structure

`log.md` is append-only. Keep entries compact and consistent:

```markdown
# Wiki Log

> Format: `## [YYYY-MM-DD] action | subject`
> Actions: ingest, create, update, query, lint, archive, hook-sync

## [YYYY-MM-DD] create | concepts/llm-wiki
- Wrote: concepts/llm-wiki.md
- Updated: index.md
- Source: raw/articles/karpathy-llm-wiki.md
```

Rotate to `log-YYYY.md` if `log.md` becomes too large, then start a fresh `log.md` with a pointer to the rotated file.

## Provenance and hash rules

`kb_write_note` appends a provenance trailer automatically after the rendered note:

```markdown
<!-- kb-provenance: source_hash=<sha256-of-content-before-trailer>; operation=write_note; actor=llm-wiki -->
```

Do not hand-author that trailer in the `body` argument unless you are intentionally doing a direct-file fallback outside MCP. Hashes have different meanings:

- `source_hash` is SHA-256 of the rendered note before the server-added trailer.
- `content_hash` is SHA-256 of the final stored file, including the provenance trailer.
- For the next update, pass `content_hash` as `if_hash`, not `source_hash`.
- When updating from direct filesystem reads, compute SHA-256 over the exact current file text, including the provenance trailer and final newline.

## Write policy

- `kb_write_note` writes structured note fields. Do not pass a complete Markdown file. Pass `body` without YAML frontmatter, without the provenance trailer, and without a top-level `# Title` heading; the tool renders those parts.
- For updates, preserve intended existing fields/body, pass the current full-file `content_hash` as `if_hash`, and send the complete replacement field set.
- Keep raw sources under `raw/` immutable. Corrections and synthesis belong in wiki pages such as `entities/`, `concepts/`, `comparisons/`, or `queries/`.
- Every meaningful write should update `index.md` and append a concise entry to `log.md` unless the user explicitly requests a draft-only note.
- Use lowercase kebab-case note paths such as `concepts/llm-wiki.md` and `entities/anthropic.md`.
- Prefer `[[wikilinks]]` between wiki pages. New synthesized pages should have at least two useful outbound links when possible.
- Preserve YAML frontmatter fields by resubmitting structured arguments: `title`, `created`, `updated`, `type`, `tags`, and `sources`.

## LLM Wiki page flow

1. Capture or identify the source material.
2. Decide whether it belongs in `raw/` as immutable source, a synthesized page, or both.
3. Check existing pages from `index.md` and direct search when available.
4. Create or update only the pages that meet the page thresholds above or the vault `SCHEMA.md` thresholds.
5. Update navigation (`index.md`) and audit trail (`log.md`).
6. Report the exact note paths written and the returned hashes.

## Exploration flow

Use the wiki as a graph, not just a text search index:

1. Start with `index.md` and recent `log.md` to understand the current map and recent changes.
2. Search with multiple terms: the user's wording, likely synonyms, entity names, and tag names.
3. Use `path_prefix` to narrow searches: `entities`, `concepts`, `comparisons`, `queries`, or `raw`.
4. Follow `[[wikilinks]]` from relevant pages. Read linked pages before answering if they may change the synthesis.
5. Prefer pages with higher confidence, newer dates, and multiple sources. Surface low-confidence or contested pages explicitly.
6. If the answer becomes a reusable synthesis, file it as a `queries/` or `comparisons/` page and update `index.md` and `log.md`.

Example search plan:

```text
kb_search_notes(query="llm wiki obsidian vault", limit=5)
kb_search_notes(query="KB_VAULT_PATH", limit=5)
kb_search_notes(query="context hook", limit=5, path_prefix="concepts")
```

## Concrete examples

### Structured synthesized note call

These are the fields you pass to `kb_write_note`; the server renders frontmatter, `# LLM Wiki`, and the provenance trailer.

```json
{
  "note_path": "concepts/llm-wiki.md",
  "title": "LLM Wiki",
  "type": "concept",
  "tags": ["knowledge-base", "agent-memory"],
  "sources": ["raw/articles/karpathy-llm-wiki.md"],
  "created": "2026-06-09T14:30:05Z",
  "updated": "2026-06-09T14:45:12Z",
  "confidence": "medium",
  "contested": false,
  "body": "## Summary\nAn LLM Wiki is an agent-maintained Markdown knowledge base where raw sources stay immutable and synthesized pages accumulate durable context for future work.\n\n## Key facts\n- It differs from one-shot RAG because synthesis is saved once and reused later.\n- A useful vault separates `raw/` source material from synthesized pages such as [[concepts/agent-memory]] and [[comparisons/rag-vs-llm-wiki]].\n\n## Relationships\n- [[concepts/agent-memory]] — persistent context strategy for agents.\n- [[comparisons/rag-vs-llm-wiki]] — tradeoffs between retrieval and compiled wiki context.\n\n## Open questions\n- Which updates should be automatic at task stop time versus manually reviewed?\n\n## Sources\n- raw/articles/karpathy-llm-wiki.md"
}
```

The rendered note begins like this before the provenance trailer:

```markdown
---
title: LLM Wiki
created: "2026-06-09T14:30:05Z"
updated: "2026-06-09T14:45:12Z"
type: concept
tags:
  - knowledge-base
  - agent-memory
sources:
  - raw/articles/karpathy-llm-wiki.md
confidence: medium
contested: false
---

# LLM Wiki

## Summary
An LLM Wiki is an agent-maintained Markdown knowledge base where raw sources stay immutable and synthesized pages accumulate durable context for future work.

## Key facts
- It differs from one-shot RAG because synthesis is saved once and reused later.
- A useful vault separates `raw/` source material from synthesized pages such as [[concepts/agent-memory]] and [[comparisons/rag-vs-llm-wiki]].

## Relationships
- [[concepts/agent-memory]] — persistent context strategy for agents.
- [[comparisons/rag-vs-llm-wiki]] — tradeoffs between retrieval and compiled wiki context.

## Open questions
- Which updates should be automatic at task stop time versus manually reviewed?

## Sources
- raw/articles/karpathy-llm-wiki.md
```

### Matching index entry

```markdown
- [[concepts/llm-wiki]] — Agent-maintained Markdown knowledge base pattern for durable context.
```

### Matching log entry

```markdown
## [2026-06-09] create | concepts/llm-wiki
- Wrote: concepts/llm-wiki.md
- Updated: index.md
- Source: raw/articles/karpathy-llm-wiki.md
```

## Hook-driven always-on usage

Use hooks or wrappers to make LLM Wiki context part of every agent turn. The repository setup script installs reusable context hook commands by default (`uv run python scripts/main.py`, or per-agent with `--agent`). Pass `--no-hooks` or set `LLM_WIKI_INSTALL_HOOKS=false` only when you want to wire hooks manually. During setup, the Stop hook is opt-in: the installer warns that it may prevent the LLM response from being delivered correctly, then waits until the operator enters uppercase `Y` or `N`. `Y` installs the Stop hook, `N` continues with only the context hook, invalid input repeats the prompt, and non-interactive stdin/EOF aborts before installation.

When both hooks are installed, the generated scripts call `scripts/agent_hooks/llm_wiki_agent_hook.py` in two modes:

- **User-input hook:** search the wiki through `kb_search_notes` at prompt time and inject a compact `<llm-wiki-context>` block before the model starts working.
- **Stop hook:** after the model finishes, force one final wiki update pass that records durable discoveries, decisions, and changed context through MCP.

The hook should run every time, but it should not create noisy pages every time. If the task produced no durable knowledge, either write no content page or append only a compact `hook-sync` log entry if the operator wants a full audit trail.

### Claude Code hook shape

Claude Code supports project/user hook events such as `UserPromptSubmit` and `Stop`. Setup installs `llm-wiki-context-hook.sh` under `${CLAUDE_HOOKS_DIR:-~/.claude/hooks/llm-wiki}/`; it installs `llm-wiki-stop-hook.sh` and merges the `Stop` entry only when the setup prompt is answered with uppercase `Y`. A project-local `.claude/settings.json` can use the same shape if you prefer project hooks:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/llm-wiki-context-hook.sh",
            "timeout": 5
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/llm-wiki-stop-hook.sh",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

`llm-wiki-context-hook.sh` should read the incoming prompt metadata from stdin when the agent provides it, query `kb_search_notes` or a local helper for `SCHEMA.md`, `index.md`, recent `log.md`, and topic matches, then print a compact context block to stdout. Keep it short enough that it helps rather than flooding the prompt.

`llm-wiki-stop-hook.sh` should read the session/transcript metadata available to the hook, decide what durable knowledge changed, then use `kb_search_notes` plus `kb_write_note` to update pages, `index.md`, and `log.md` with optimistic concurrency. When selected during setup, the Claude/Codex stop hook emits a one-time `decision=block` response so the agent performs that update pass before its final stop; it must not block again when `stop_hook_active=true`.

The two architectures for stop-time updates — **in-loop** (re-prompt the same session via `decision=block`) versus **out-of-loop** (a stop hook spawns a separate headless writer such as `claude -p` / `codex exec`) — and their trade-offs are compared in the vault concept page `[[concepts/agent-stop-hook-self-update]]`. When selected during setup, this skill installs the in-loop variant for Claude Code and Codex; see the headless fallback note below for unattended setups.

### Codex enforcement pattern (native hooks)

Codex (2026+) shares Claude Code's hook JSON schema: the same `hooks` object, the same `UserPromptSubmit`/`Stop` event names, the same `{type, command, timeout}` shape, the same stdin payload (`transcript_path`, `stop_hook_active`, `last_assistant_message`), and the same `decision=block` + `reason` Stop semantics. So the Claude hook JSON ports directly — only the destination file differs.

Setup installs this skill under `$CODEX_HOME/skills/llm-wiki/`, configures `[mcp_servers.llm_wiki]`, writes the context script under `${CODEX_LLM_WIKI_HOOKS_DIR:-${CODEX_HOME:-~/.codex}/hooks/llm-wiki}/`, and merges the `UserPromptSubmit` entry into `${CODEX_HOOKS_JSON_PATH:-~/.codex/hooks.json}`. When the setup prompt is answered with uppercase `Y`, it also writes the stop script and merges the `Stop` entry. Codex also accepts an inline `[hooks]` table in `config.toml`. Equivalent `hooks.json` when Stop hook is enabled:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      { "hooks": [ { "type": "command", "command": "~/.codex/hooks/llm-wiki/llm-wiki-context-hook.sh", "timeout": 5 } ] }
    ],
    "Stop": [
      { "hooks": [ { "type": "command", "command": "~/.codex/hooks/llm-wiki/llm-wiki-stop-hook.sh", "timeout": 10 } ] }
    ]
  }
}
```

### Hermes/Hermess enforcement pattern (out-of-loop)

Hermes exposes only finalize-style session hooks (`on_session_start`/`on_session_end`/`on_session_finalize`/`subagent_stop`, plus `pre/post_tool_call`) declared in `cli-config.yaml`; it pipes a JSON payload to the hook on stdin and reads stdout JSON back. These finalize hooks do **not** support Claude-style `decision=block` re-prompting, so the in-loop pattern does not apply — use the **out-of-loop** model: a finalize hook triggers a separate update pass rather than re-running the same session.

Setup installs this skill, configures the `llm_wiki` MCP server, and writes reusable hook commands under `${HERMES_LLM_WIKI_HOOKS_DIR:-${HERMES_HOME:-~/.hermes}/hooks/llm-wiki}/`. The minimum reliable setup is to start sessions with the skill loaded or call `/skill llm-wiki`; for automation, wire the generated context script and optional stop script into a Hermes plugin, wrapper command, or finalize hook. Non-interactive runs (gateway, cron) must allow hooks with `--accept-hooks`, `HERMES_ACCEPT_HOOKS=1`, or the `hooks_auto_accept` config key.

### Headless fallback (any client, unattended)

When you must guarantee the update runs unattended, a stop/finalize hook can spawn a separate headless writer (`claude -p` or `codex exec`) instead of re-prompting in-loop. Three things are mandatory, or it silently no-ops: (1) the headless agent has no memory of the turn, so feed it the hook payload's `transcript_path`; (2) `claude -p --bare` skips the project MCP config and OAuth, so pass `--mcp-config` for `llm-wiki` plus a credential (`ANTHROPIC_API_KEY`/`apiKeyHelper`) or it will not have `kb_write_note`; (3) fully detach the process (`setsid`/`nohup`), since background tasks started during a `-p` run are killed shortly after it returns. See `[[concepts/agent-stop-hook-self-update]]` for the full comparison.

## Safety rules

- Do not invent existing vault contents. If you cannot read a page, say so and ask for it or create a clearly named draft note instead of overwriting.
- Do not hard-delete notes through this workflow.
- Do not overwrite existing notes in MCP-only mode from snippets alone.
- Do not call `kb_push_vault` from this skill. Use `$llm-wiki-push` for explicit vault GitHub push requests.
- Treat the MCP endpoint as local by default: `http://127.0.0.1:9999/mcp`.
- If the server later enables bearer auth, add the authorization header in the agent MCP config before using write tools.
- Do not write raw, private transcripts wholesale into the wiki. Summarize durable decisions, facts, and relationships.

## Agent-specific MCP names

### Hermes/Hermess

Hermes prefixes native MCP tools as `mcp_<server>_<tool>`. With the default `llm_wiki` server name, look for:

- `mcp_llm_wiki_kb_write_note`
- `mcp_llm_wiki_kb_search_notes`

If these tools do not appear, run `hermes mcp list`, `hermes mcp test llm_wiki`, then restart the Hermes session or gateway. In an existing session, use `/reload-mcp` if available.

### Claude Code

Claude Code usually displays MCP tools with a server namespace such as `mcp__llm-wiki__kb_write_note`. With the default setup, look for the `llm-wiki` MCP server in `/mcp` or `claude mcp list`.

If project-scoped `.mcp.json` is used, Claude may ask you to approve the server the first time it sees the project. Approve only after confirming the endpoint is the expected local URL.

### Codex

Codex reads installed skills from `$CODEX_HOME/skills` (default `$HOME/.codex/skills`). The default MCP server id is `llm_wiki`; check Codex MCP startup/status output if the tools are not visible.

Install this skill under `$CODEX_HOME/skills/llm-wiki/`, or set `CODEX_SKILLS_DIR` only when your Codex installation explicitly loads another skill directory.
