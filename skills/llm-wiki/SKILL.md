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

## MCP tools exposed by this server

The underlying server exposes these tool names:

- `kb_write_note(note_path, content, if_hash?)` — write a complete note inside the configured vault. It enforces the vault schema before writing. Existing notes require optimistic concurrency.
- `kb_search_notes(query, limit?, path_prefix?)` — search the Markdown LLM Wiki vault and return ranked paths, titles, page types, tags, content hashes, and line snippets.
- `kb_wiki_context(recent_log_lines?, include_schema_rules?, include_index?)` — return the schema-first context bundle: `SCHEMA.md`, `index.md`, recent `log.md`, parsed rules, current page/link map, explicit entity list, issue candidates, and update suggestions.
- `kb_validate_vault(include_raw?)` — validate deterministic schema hygiene across the vault: frontmatter, required fields, path/type consistency, tag taxonomy, raw metadata, and raw body hashes.
- `kb_reconcile_taxonomy(apply?, decisions?)` — dry-run or apply deterministic tag taxonomy repair. Use it for tag add/rename/remove decisions, not for content migration.

Vault and graph counters are exposed as a REST API endpoint at `GET /metrics`, not as MCP tools.
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

1. Confirm the MCP server is connected by listing tools or calling `kb_wiki_context`.
2. Start every wiki task with `kb_wiki_context` when it is available. Treat the returned `parsed_schema` as the write contract, not as background documentation, and treat `entities`, `wiki_map`, `issue_candidates`, and `update_suggestions` as the first-pass graph maintenance backlog.
3. Use `parsed_schema.required_synthesized_frontmatter`, `parsed_schema.allowed_types`, and `parsed_schema.tag_taxonomy` before creating or updating pages. Do not invent page types or tags.
4. Use `entities`, `wiki_map.pages`, `wiki_map.pages_by_type`, and `wiki_map.link_graph` to choose whether to update an existing entity/concept, add links, or create a new page.
5. Review `issue_candidates` before writing. Prefer fixing broken wikilinks, missing backlinks, orphan/underlinked pages, unindexed pages, and raw sources without synthesis when they are relevant to the user's task.
6. Use `update_suggestions` as suggested actions, not blind commands. Apply only suggestions that improve durable wiki structure.
7. Check `index` and recent `log` from `kb_wiki_context` before creating a page. Update existing pages instead of duplicating them, and avoid repeating recent work.
8. If `health` reports schema errors, fix deterministic hygiene with `kb_validate_vault`/`kb_reconcile_taxonomy` before creating new synthesized content.
9. Search for existing topic pages with `kb_search_notes` before creating new ones. Avoid duplicate entity or concept pages.
10. Decide the access mode:
   - **File-readable mode:** safe to update existing notes because you can read the complete current file, reconstruct it, and pass the exact current `content_hash` as `if_hash`.
   - **MCP-only mode:** `kb_search_notes` returns snippets, not full note bodies. Do not overwrite an existing note from snippets alone. Create new notes only, or ask the user for the full current note content before updating.

## Content model and page types

Use the `type` frontmatter value to decide where a page belongs and how readers will browse it.

| Type | Directory | Use for | Do not use for |
| --- | --- | --- | --- |
| `entity` | `entities/` | People, companies, products, models, projects, protocols, datasets, standards, APIs | Broad ideas or techniques |
| `concept` | `concepts/` | Techniques, principles, mechanisms, topics, terms, recurring patterns | Named organizations/products unless the page is about the abstract idea |
| `comparison` | `comparisons/` | Tradeoff analysis, A-vs-B decisions, rankings, matrices, migration choices | Simple summaries of one thing |
| `query` | `queries/` | A substantial answered question, investigation, synthesis, or research result worth reusing | Trivial lookups or temporary chat answers |
| `summary` | Usually `concepts/` or `queries/` | Cross-cutting overview pages and topic maps | Pages that can be classified more specifically |

### Page creation thresholds

Create or update pages only when the content improves future retrieval:

- Create a new page when the entity/concept appears in 2+ sources, or is central to one important source.
- Update an existing page when new material changes, confirms, dates, or clarifies something already covered.
- Create a `comparison` page when the user is choosing between alternatives or the source compares alternatives on multiple dimensions.
- Create a `query` page when the answer is non-trivial enough that re-deriving it would waste time later.
- Do not create pages for passing mentions, minor side details, or out-of-domain material.
- Split pages that exceed about 200 lines into focused sub-pages and cross-link them.

### Required frontmatter

Every synthesized wiki page starts with YAML frontmatter:

```yaml
---
title: Page Title
created: YYYY-MM-DD
updated: YYYY-MM-DD
type: entity | concept | comparison | query | summary
tags: [tag-from-schema]
sources: [raw/articles/source-file.md]
confidence: high | medium | low
contested: false
---
```

All listed fields are required for synthesized pages. `confidence` and `contested` are not optional: use `confidence: low` for single-source, speculative, or fast-moving claims, and use `contested: true` when sources conflict and explain the conflict in the body. `tags` must come from the current `SCHEMA.md` tag taxonomy. If a needed tag is missing, update `SCHEMA.md` first or ask the user.

### Page body pattern

Keep pages scannable. Prefer this shape unless the vault `SCHEMA.md` says otherwise:

```markdown
# Page Title

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

If `SCHEMA.md` is missing or the user is creating a new vault, create it before writing topic pages. Do not rely on an external schema that does not exist. Use this minimal schema and customize the domain/tags:

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
Required fields: `title`, `created`, `updated`, `type`, `tags`, `sources`, `confidence`, `contested`.
Allowed `type` values: `entity`, `concept`, `comparison`, `query`, `summary`.
Tags must be declared in this file before a page can use them.

## Tag taxonomy
[List 10-20 allowed tags for this domain before using them.]

## Page thresholds
- Create a page when an entity/concept appears in 2+ sources or is central to one important source.
- Do not create pages for passing mentions.
- Split pages over about 200 lines.
- Mark contradictions with `contested: true` and explain both claims with dates and sources.

## Entity update policy
- Treat `entities/` pages as canonical profiles for real-world people, orgs, products, models, projects, standards, APIs, and datasets.
- Search existing entity pages before creating a new one. Merge into the existing page when aliases, title, slug, sources, or relationships point to the same real-world entity.
- Preserve dated facts instead of silently overwriting them. If sources conflict, lower `confidence`, set `contested: true`, and explain both claims.
- Update `sources`, `## Sources`, `## Relationships`, backlinks, `index.md`, and `log.md` when the entity changes.

## Link repair policy
- On every write, use `kb_wiki_context` issue candidates to repair relevant `broken_wikilink`, `ambiguous_wikilink`, `missing_backlink`, `orphan_page`, `underlinked_page`, `unindexed_page`, `missing_raw_source`, and `duplicate_title` issues.
- Replace broken links with a canonical existing page when one exists; create a new page only when page thresholds are met; otherwise use plain text or link to a broader existing page.
- After writing, re-check context for the changed paths and fix any schema or graph damage introduced by the update.
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

`kb_write_note` appends a provenance trailer automatically after synthesized and meta note content you provide:

```markdown
<!-- kb-provenance: source_hash=<sha256-of-content-before-trailer>; operation=write_note; actor=llm-wiki -->
```

Do not hand-author that trailer in the `content` argument unless you are intentionally doing a direct-file fallback outside MCP. Hashes have different meanings:

- `source_hash` is SHA-256 of the content before the server-added trailer.
- `content_hash` is SHA-256 of the final stored file, including the provenance trailer.
- For the next update, pass `content_hash` as `if_hash`, not `source_hash`.
- When updating from direct filesystem reads, compute SHA-256 over the exact current file text, including the provenance trailer and final newline.
- Raw notes under `raw/` are the exception: `kb_write_note` does not append the provenance trailer to raw notes because the raw frontmatter `sha256` must keep matching the body-only source archive bytes.

## Raw write contract

Use the existing `kb_write_note` tool for raw notes; do not invent a separate ingest flow unless the user explicitly asks for one. Every `raw/**.md` note must include frontmatter before the body. `ingested` and body-only `sha256` are required; source metadata is optional because raw notes may contain direct research without a source URL.

```yaml
---
ingested: YYYY-MM-DD
sha256: "<sha256 of body only, excluding frontmatter>"
source_url: "https://example.com/source-or-hermes-session-id"
# or:
source_urls:
  - "https://example.com/source-a"
  - "https://example.com/source-b"
---
```

For Hermes sources, add enough optional metadata to identify the source without copying secrets:

```yaml
---
source_url: "hermes-session:20260609_074425_ae8639a9"
ingested: 2026-06-10
sha256: "<sha256 of body only>"
type: raw-session
source_system: hermes
profile: default
sessions:
  - 20260609_074425_ae8639a9
---
```

Raw files are source archives. Do not edit a raw body after creation. If the source changes, write a new raw note or explicitly record drift. Only repair raw frontmatter when metadata is missing, and preserve body bytes exactly.

## Write policy

- `kb_write_note` writes the full note body and validates it against the schema first. Treat schema validation errors as repair instructions: fix the content and retry; do not bypass validation.
- For updates, reconstruct the full target file and pass the current full-file hash as `if_hash`.
- Before every meaningful write, call `kb_wiki_context` and build a write set from `wiki_map`, `issue_candidates`, and `update_suggestions`: target note, related notes that need backlinks or repaired links, `index.md`, `log.md`, and `SCHEMA.md` if tags change.
- Keep raw sources under `raw/` immutable. Corrections and synthesis belong in wiki pages such as `entities/`, `concepts/`, `comparisons/`, or `queries/`.
- Every meaningful write should update `index.md` and append a concise entry to `log.md` unless the user explicitly requests a draft-only note.
- Use lowercase kebab-case note paths such as `concepts/llm-wiki.md` and `entities/anthropic.md`.
- Prefer `[[wikilinks]]` between wiki pages. New synthesized pages should have at least two useful outbound links when possible.
- Preserve YAML frontmatter on wiki pages: `title`, `created`, `updated`, `type`, `tags`, `sources`, `confidence`, and `contested`.
- After writes, rerun `kb_wiki_context` for graph health around changed paths and `kb_validate_vault` for schema/raw-hash hygiene. Fix issues introduced by the write before reporting success.
- Do not create entity/comparison/concept batches unless the user explicitly asks for content migration. Schema repair and content synthesis are different operations.

## Write-time graph maintenance

Use the new context tools to strengthen the graph while writing, not as a separate cleanup chore:

1. **Orient:** `kb_wiki_context` returns `parsed_schema`, `entities`, `wiki_map`, `issue_candidates`, and `update_suggestions`. Treat this as the current wiki graph.
2. **Resolve identity:** Use top-level `entities`, `wiki_map.pages_by_type.entity`, entity titles, slugs, sources, inbound/outbound links, and `kb_search_notes` hits to decide whether the subject already has a canonical page.
3. **Plan the write set:** Include every page whose meaning or navigation changes: the main note, reciprocal backlink targets, duplicate/alias pages to merge or disambiguate, `index.md`, `log.md`, and `SCHEMA.md` when taxonomy changes.
4. **Apply only semantic repairs:** `update_suggestions` are candidate repairs. Apply suggestions when the relationship is meaningful; skip noisy backlinks that would not help future retrieval.
5. **Verify:** Re-run `kb_wiki_context` after writing and make sure relevant `broken_wikilink`, `ambiguous_wikilink`, `missing_backlink`, `orphan_page`, `underlinked_page`, `unindexed_page`, `missing_raw_source`, and `duplicate_title` candidates were resolved or intentionally left with a log note.

## Entity update policy

Entity pages are canonical profiles, not one-source summaries. When a write mentions a person, org, product, model, project, protocol, dataset, standard, or API:

1. Search first: inspect `wiki_map.pages_by_type.entity`, `index.md`, `kb_search_notes` results, and duplicate-title candidates before creating `entities/<slug>.md`.
2. Update the existing entity when aliases, renamed products, title variants, source URLs, relationships, or surrounding pages point to the same real-world thing. Use a stable canonical slug; use display aliases like `[[entities/andrej-karpathy|Karpathy]]` when prose needs a shorter name.
3. Create a new entity only when no canonical page exists, the entity meets the page threshold, and it is not merely a passing mention.
4. Preserve history: add dated, sourced facts rather than silently replacing older facts. If a source changes an earlier claim, say what changed and cite both sources.
5. Handle conflicts explicitly: set `contested: true`, lower `confidence`, and explain competing claims with dates/sources instead of picking a winner without evidence.
6. Keep relationships current: add or prune `## Relationships` entries, update reciprocal backlinks when useful, and connect the entity to relevant concepts/comparisons/queries.
7. Keep provenance current: add new raw paths to `sources:` and `## Sources`; remove a source only if the page no longer relies on it.
8. If duplicate entity pages exist, merge or disambiguate them before adding more content. Do not spread one entity across multiple pages.
9. Always bump `updated`, refresh the `index.md` one-line summary if the entity's meaning changed, and append `log.md` with created/updated paths.

## Adding an entity page

Use this flow when the source material introduces a real-world person, organization, product, model, project, protocol, dataset, standard, or API that should become a canonical profile:

1. Read `entities` from `kb_wiki_context` before searching broadly. Treat it as the current canonical entity list, including path, title, tags, sources, links, and index status.
2. Compare the candidate against `entities`, `wiki_map.pages_by_type.entity`, `index`, duplicate-title candidates, and `kb_search_notes` results. Resolve aliases, renamed products, abbreviations, and source overlap before deciding it is new.
3. Create `entities/<stable-slug>.md` only after identity resolution shows no canonical page exists and the entity meets the page threshold.
4. Use `type: entity`, tags from `parsed_schema.allowed_tags`, and at least one reliable source in `sources:`. If the source is raw material that is not in `raw/` yet, add the raw note first or cite the external source explicitly.
5. Include `## Summary`, `## Key facts`, `## Relationships`, `## Open questions`, and `## Sources`. Link the entity to relevant concepts, comparisons, queries, or other entities with `[[wikilinks]]`.
6. Update `index.md` under `## Entities` with one line for the new canonical page, append a `log.md` create/update entry, then rerun `kb_wiki_context` and repair relevant graph issues.

Minimal entity page:

```markdown
---
title: Example Entity
created: YYYY-MM-DD
updated: YYYY-MM-DD
type: entity
tags: [tag-from-schema]
sources: [raw/articles/source-file.md]
confidence: medium
contested: false
---

# Example Entity

## Summary
One short paragraph explaining why this entity matters in the vault.

## Key facts
- Dated, source-backed fact.

## Relationships
- [[concepts/related-concept]] — why the relationship matters.

## Open questions
- What remains uncertain?

## Sources
- raw/articles/source-file.md
```

## Broken-link self-repair policy

Treat broken links as graph damage to repair during the same write when they touch the task area:

- `broken_wikilink`: if a canonical target exists, rewrite to the exact target path (`[[entities/openai]]`) or an aliased link (`[[entities/openai|OpenAI]]`). If no target exists, create one only when page thresholds are met; otherwise convert the link to plain text or link to a broader existing page.
- `ambiguous_wikilink`: replace the link with an explicit path or alias. If ambiguity reflects duplicate pages, merge or disambiguate before writing new content.
- `missing_backlink`: add a backlink only when it helps navigation or explains a durable relationship. Avoid mechanical backlinks that make pages noisy.
- `underlinked_page` / `orphan_page`: use related paths from `update_suggestions` plus source semantics to add meaningful links, or log/archive pages that should not remain active.
- `unindexed_page`: add the page to the correct `index.md` section with a one-line summary.
- `missing_raw_source`: add the missing raw note, fix the source path, or remove the citation if the page does not rely on that source.
- `duplicate_title`: merge same-entity/same-concept pages or rename them with disambiguating slugs before creating more links.

Do not use `kb_reconcile_taxonomy` for link repair; it is for tag taxonomy decisions. Use `kb_validate_vault` for schema/frontmatter/raw-hash hygiene and `kb_wiki_context` for graph/link health.

## MCP context-first workflow

When LLM Wiki MCP tools are available, start every wiki task with `kb_wiki_context` and use the returned context as the source of truth:

1. Read `parsed_schema.required_synthesized_frontmatter` before creating or updating synthesized pages.
2. Choose `type` from `parsed_schema.allowed_types`; do not invent page types.
3. Choose tags only from `parsed_schema.tag_taxonomy` / `parsed_schema.allowed_tags`.
4. Read top-level `entities`, `wiki_map.pages_by_type`, and `wiki_map.link_graph` as the current entity/concept map. Use it to decide whether the task should update an existing page, create a new page, or only add links.
5. Inspect `issue_candidates` for relevant graph/consistency problems:
   - `broken_wikilink` / `ambiguous_wikilink` — repair link target spelling or create/disambiguate pages.
   - `missing_backlink` — add bidirectional navigation when the relationship is meaningful.
   - `orphan_page` / `underlinked_page` — connect useful pages to related pages, or archive stale pages.
   - `unindexed_page` — add missing synthesized pages to `index.md`.
   - `raw_source_without_synthesis` / `missing_raw_source` — synthesize/link useful raw sources or repair bad citations.
   - `duplicate_title` — merge or disambiguate pages before adding more content.
6. Treat `update_suggestions` as AI guidance. Apply them only when they are relevant and semantically correct; do not mechanically execute every suggestion.
7. If a needed tag is missing, update `SCHEMA.md` first, run/dry-run `kb_reconcile_taxonomy`, or ask the user.
8. Check `index` before creating a page; update existing pages instead of duplicating them.
9. Check `recent_log` to avoid repeating work.
10. If `health` reports schema errors, fix deterministic hygiene before creating new content.
11. When writing raw notes, compute body-only `sha256` and use `kb_write_note`; do not invent a separate raw ingest flow.
12. If `kb_write_note` returns schema errors, fix the content and retry. Do not bypass validation.

`SCHEMA.md` is not documentation; it is the write contract that MCP enforces.

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

### Complete synthesized note content

This is the `content` you pass to `kb_write_note`; the server appends the provenance trailer after the final line.

```markdown
---
title: LLM Wiki
created: 2026-06-09
updated: 2026-06-09
type: concept
tags: [knowledge-base, agent-memory]
sources: [raw/articles/karpathy-llm-wiki.md]
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

Use hooks or wrappers to make LLM Wiki context part of every agent turn. The repository setup script installs reusable hook commands by default (`uv run python scripts/main.py`, or per-agent with `--agent`). Pass `--no-hooks` or set `LLM_WIKI_INSTALL_HOOKS=false` only when you want to wire hooks manually.

The generated scripts call `scripts/agent_hooks/llm_wiki_agent_hook.py` in two modes:

- **User-input hook:** search the wiki through `kb_search_notes` at prompt time and inject a compact `<llm-wiki-context>` block before the model starts working.
- **Stop hook:** after the model finishes, force one final wiki update pass that records durable discoveries, decisions, and changed context through MCP.

The hook should run every time, but it should not create noisy pages every time. If the task produced no durable knowledge, either write no content page or append only a compact `hook-sync` log entry if the operator wants a full audit trail.

### Claude Code hook shape

Claude Code supports project/user hook events such as `UserPromptSubmit` and `Stop`. Setup installs `llm-wiki-context-hook.sh` and `llm-wiki-stop-hook.sh` under `${CLAUDE_HOOKS_DIR:-~/.claude/hooks/llm-wiki}/` and merges equivalent entries into `${CLAUDE_SETTINGS_PATH:-~/.claude/settings.json}`. A project-local `.claude/settings.json` can use the same shape if you prefer project hooks:

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

`llm-wiki-stop-hook.sh` should read the session/transcript metadata available to the hook, decide what durable knowledge changed, then use `kb_search_notes` plus `kb_write_note` to update pages, `index.md`, and `log.md` with optimistic concurrency. The installed Claude/Codex stop hook emits a one-time `decision=block` response so the agent performs that update pass before its final stop; it must not block again when `stop_hook_active=true`.

The two architectures for stop-time updates — **in-loop** (re-prompt the same session via `decision=block`) versus **out-of-loop** (a stop hook spawns a separate headless writer such as `claude -p` / `codex exec`) — and their trade-offs are compared in the vault concept page `[[concepts/agent-stop-hook-self-update]]`. This skill installs the in-loop variant for Claude Code and Codex; see the headless fallback note below for unattended setups.

### Codex enforcement pattern (native hooks)

Codex (2026+) shares Claude Code's hook JSON schema: the same `hooks` object, the same `UserPromptSubmit`/`Stop` event names, the same `{type, command, timeout}` shape, the same stdin payload (`transcript_path`, `stop_hook_active`, `last_assistant_message`), and the same `decision=block` + `reason` Stop semantics. So the Claude hook JSON ports directly — only the destination file differs.

Setup installs this skill under `$CODEX_HOME/skills/llm-wiki/`, configures `[mcp_servers.llm_wiki]`, writes the context/stop scripts under `${CODEX_LLM_WIKI_HOOKS_DIR:-${CODEX_HOME:-~/.codex}/hooks/llm-wiki}/`, and merges `UserPromptSubmit`/`Stop` entries into `${CODEX_HOOKS_JSON_PATH:-~/.codex/hooks.json}`. Codex also accepts an inline `[hooks]` table in `config.toml`. Equivalent `hooks.json`:

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

Setup installs this skill, configures the `llm_wiki` MCP server, and writes reusable hook commands under `${HERMES_LLM_WIKI_HOOKS_DIR:-${HERMES_HOME:-~/.hermes}/hooks/llm-wiki}/`. The minimum reliable setup is to start sessions with the skill loaded or call `/skill llm-wiki`; for automation, wire the generated context/stop scripts into a Hermes plugin, wrapper command, or finalize hook. Non-interactive runs (gateway, cron) must allow hooks with `--accept-hooks`, `HERMES_ACCEPT_HOOKS=1`, or the `hooks_auto_accept` config key.

### Headless fallback (any client, unattended)

When you must guarantee the update runs unattended, a stop/finalize hook can spawn a separate headless writer (`claude -p` or `codex exec`) instead of re-prompting in-loop. Three things are mandatory, or it silently no-ops: (1) the headless agent has no memory of the turn, so feed it the hook payload's `transcript_path`; (2) `claude -p --bare` skips the project MCP config and OAuth, so pass `--mcp-config` for `llm-wiki` plus a credential (`ANTHROPIC_API_KEY`/`apiKeyHelper`) or it will not have `kb_write_note`; (3) fully detach the process (`setsid`/`nohup`), since background tasks started during a `-p` run are killed shortly after it returns. See `[[concepts/agent-stop-hook-self-update]]` for the full comparison.

## Safety rules

- Do not invent existing vault contents. If you cannot read a page, say so and ask for it or create a clearly named draft note instead of overwriting.
- Do not hard-delete notes through this workflow.
- Do not overwrite existing notes in MCP-only mode from snippets alone.
- Treat the MCP endpoint as local by default: `http://127.0.0.1:9999/mcp`.
- If the server later enables bearer auth, add the authorization header in the agent MCP config before using write tools.
- Do not write raw, private transcripts wholesale into the wiki. Summarize durable decisions, facts, and relationships.

## Agent-specific MCP names

### Hermes/Hermess

Hermes prefixes native MCP tools as `mcp_<server>_<tool>`. With the default `llm_wiki` server name, look for:

- `mcp_llm_wiki_kb_write_note`
- `mcp_llm_wiki_kb_search_notes`
- `mcp_llm_wiki_kb_wiki_context`
- `mcp_llm_wiki_kb_validate_vault`
- `mcp_llm_wiki_kb_reconcile_taxonomy`

If these tools do not appear, run `hermes mcp list`, `hermes mcp test llm_wiki`, then restart the Hermes session or gateway. In an existing session, use `/reload-mcp` if available.

### Claude Code

Claude Code usually displays MCP tools with a server namespace such as `mcp__llm-wiki__kb_write_note`. With the default setup, look for the `llm-wiki` MCP server in `/mcp` or `claude mcp list`.

If project-scoped `.mcp.json` is used, Claude may ask you to approve the server the first time it sees the project. Approve only after confirming the endpoint is the expected local URL.

### Codex

Codex reads installed skills from `$CODEX_HOME/skills` (default `$HOME/.codex/skills`). The default MCP server id is `llm_wiki`; check Codex MCP startup/status output if the tools are not visible.

Install this skill under `$CODEX_HOME/skills/llm-wiki/`, or set `CODEX_SKILLS_DIR` only when your Codex installation explicitly loads another skill directory.
