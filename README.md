# LLM Wiki MCP

[English](README.md) | [한국어](README.ko.md) | [中文](README.zh.md) | [日本語](README.ja.md)

MCP server for a Git-backed Obsidian/Markdown LLM Wiki vault.

## Current capabilities

- FastAPI app serving Streamable HTTP MCP on `127.0.0.1:9999/mcp`
- Health check endpoint at `GET /health`
- FastAPI REST errors use `{code, message, timestamp}` JSON envelopes
- Safe Markdown note path resolution inside the configured vault
- Serialized writes through one `WriteQueue`
- `if_hash` optimistic concurrency for updates
- File rollback for `atomic=True` batch writes
- Source hash, content hash, and optional git commit hash in write results
- Provenance trailer on written notes
- REST `GET /metrics` endpoint combining vault and graph counters
- LLM Wiki Markdown search through the `kb_search_notes` MCP tool
- Manual vault commit/push through the `kb_push_vault` MCP tool
- Optional background vault push every random 30-60 minutes when `KB_GITHUB_PUSH_ENABLED=true`

## How to Start

### Configure `.env`

```bash
uv sync --extra dev
cp .env.example .env
```

In `.env`, set at least the vault path and the MCP server address.

```env
KB_VAULT_PATH=/home/alice/Obsidian/LLM Wiki
KB_HOST=127.0.0.1
KB_PORT=9999
KB_MCP_PATH=/mcp
KB_GITHUB_PUSH_ENABLED=false
```

`KB_VAULT_PATH` is the vault root that holds your actual Markdown knowledge documents. It must point at the folder that contains `SCHEMA.md`, `index.md`, and `log.md` — not at `llm-wiki/src` or an Obsidian `.obsidian/` settings folder.

```text
/home/alice/Obsidian/LLM Wiki/
├── SCHEMA.md
├── index.md
├── log.md
├── raw/
├── entities/
├── concepts/
├── comparisons/
└── queries/
```

The networking rule is simple. If you only use it from the same machine, keep `KB_HOST=127.0.0.1`. If a remote agent needs to connect, run the server with `KB_HOST=0.0.0.0` or a reachable bind IP, and in the agent config specify the real connection URL via `LLM_WIKI_MCP_URL=http://<server-ip-or-domain>:9999/mcp` or `--server-url`. `KB_HOST=0.0.0.0` is converted to `127.0.0.1` for same-machine client URLs, so a remote client needs the URL override.

For Obsidian, no separate connector is needed — just **Open folder as vault** and open the same folder as `KB_VAULT_PATH`. The recommended settings are to set the attachment folder to `raw/assets/` and keep Wikilinks enabled.

### Start the MCP server

```bash
uv run llm-wiki
```

The default endpoint is `http://127.0.0.1:9999/mcp`. Once the server is up you can check its status with `GET /health`, and the MCP tools expose `kb_search_notes`, `kb_write_note`, and `kb_push_vault`. Vault/graph counters are available through the REST `GET /metrics` endpoint.

### Push the vault to GitHub

`kb_push_vault` commits all pending changes in `KB_VAULT_PATH` using the UTC commit message format `YYYY-MM-DD HH:MM - vault sync`, then pushes `origin` to the current branch. The server checks GitHub CLI auth first; the actual transfer uses `git push`, and it falls back to plain `git push` when `gh` is unavailable or unauthenticated.

Use this environment variable to enable scheduled push:

```env
KB_GITHUB_PUSH_ENABLED=false
```

When `KB_GITHUB_PUSH_ENABLED=true`, the server starts a background scheduler during app lifespan and runs `kb_push_vault` at a random interval between 30 minutes and 1 hour. Keep it disabled for private vaults unless the `origin` remote is safe to publish to.

### Hook setup

With the server running, run the setup entrypoint from another terminal.

```bash
uv run python scripts/main.py                 # Hermes/Hermess, Claude Code, Codex — all
uv run python scripts/main.py --agent claude  # install a specific agent only
uv run python scripts/main.py --agent codex --server-url http://127.0.0.1:9999/mcp
```

`scripts/main.py` reads `.env` and shell export values to install the `llm-wiki` and `llm-wiki-push` skills, MCP config, and hook commands. If the same server name or URL already exists, it does not overwrite the existing MCP config.

By default, setup installs the prompt-time context hook first. When hook installation is enabled, it warns about the Stop hook and asks for uppercase `Y` or `N`: `Y` installs the Stop hook, `N` continues with only the context hook, invalid input repeats the prompt, and non-interactive stdin/EOF aborts before installation. `--dry-run` skips this interactive prompt and does not include the Stop hook in the dry-run plan.

The URL resolution order is `--server-url` -> `LLM_WIKI_MCP_URL` -> `KB_HOST`/`KB_PORT`/`KB_MCP_PATH`. The server name is resolved in the order `--server-name` -> `LLM_WIKI_MCP_SERVER_NAME` -> agent default. To turn off all hook installation, use `LLM_WIKI_INSTALL_HOOKS=false` or `--no-hooks`.

After setup, restart the agent session to reload the MCP tools, skill, and hook configuration.

## How to Work

### How hooks work

Setup creates `llm-wiki-context-hook.sh` in each agent's hook directory. It creates `llm-wiki-stop-hook.sh` only when the Stop hook prompt is answered with `Y`, and for Claude Code and Codex it merges the selected hook entries into the `UserPromptSubmit`/`Stop` hook configuration. For Hermes/Hermess it installs reusable scripts that you can wire into finalize-style hooks.

The context hook calls `kb_search_notes` at user-input time and prepends relevant wiki snippets in front of the model. When selected, the Stop hook requests an update pass right before completion, asking the model to record only wiki-worthy knowledge. Claude Code and Codex re-invoke the model once with `decision=block`, and they do not block again once `stop_hook_active=true`, avoiding a loop. If the hook helper or `uv` is missing, the hook exits quietly so it does not interfere with the agent run.

### How agents use the skill

The skill instructs the agent to:

- Search existing Markdown wiki pages with `kb_search_notes` before writing
- Orient on `SCHEMA.md`, `index.md`, and `log.md` via direct file access or `kb_search_notes` snippets
- Initialize a new vault from the skill's built-in schema, page-type, index, log, and provenance guidance when it does not have `SCHEMA.md` yet
- Treat `kb_search_notes` as snippet search rather than full file reads, so in MCP-only mode it does not update an existing note without the complete current note body
- Write complete Markdown notes through `kb_write_note`
- Use `$llm-wiki-push` for explicit GitHub vault sync requests. The main `llm-wiki` skill must not call `kb_push_vault`
- Use the returned `content_hash` as the next `if_hash` for optimistic concurrency
- Keep raw sources immutable and update `index.md` and `log.md` for durable wiki changes
- Use the installed hook commands together with native hooks, plugins, or wrappers: load compact wiki context at user-input time and, when selected during setup, run a stop-time update pass when the agent finishes. Claude Code and Codex share the same `UserPromptSubmit`/`Stop` hook schema (in-loop `decision=block` re-prompt), so setup can wire them when selected. Hermes/Hermess exposes only finalize-style session hooks, so it gets reusable scripts to wire into a plugin/wrapper or finalize hook for an out-of-loop update pass.

The MCP tools the server currently exposes are `kb_write_note`, `kb_search_notes`, and `kb_push_vault`. Vault/graph counters are provided through the REST `GET /metrics` endpoint.

## Vault Structure

The vault that `KB_VAULT_PATH` points at is not just a bag of folders — it is a graph the write skill (`kb_write_note`) fills by consistent rules. This section describes what the write skill records in each folder and how the AI finds it again.

### Folder Tree

```text
KB_VAULT_PATH/
├── SCHEMA.md        # vault conventions, page thresholds, tag taxonomy
├── index.md         # navigational catalog of synthesized pages
├── log.md           # append-only audit trail of changes
├── raw/             # immutable source material and assets (raw/assets/)
├── entities/        # people, orgs, products, models, projects, standards, APIs
├── concepts/        # ideas, techniques, mechanisms, topics, principles
├── comparisons/     # side-by-side analyses and decision records
└── queries/         # answered questions / research worth preserving
```

`raw/` is source material; `entities/`, `concepts/`, `comparisons/`, and `queries/` are synthesized wiki pages owned by the AI.

### What gets written to each folder

The write skill uses the frontmatter `type` value to decide which folder a page belongs to.

| Folder | `type` | Records | Not for |
| --- | --- | --- | --- |
| `entities/` | `entity` | People, companies, products, models, projects, protocols, datasets, standards, APIs | Broad ideas or techniques |
| `concepts/` | `concept` | Techniques, principles, mechanisms, topics, terms, recurring patterns | Named orgs/products unless the page is about the abstract idea |
| `comparisons/` | `comparison` | Tradeoff analysis, A-vs-B decisions, rankings, matrices, migration choices | A simple summary of one thing |
| `queries/` | `query` | A substantial, well-answered question, investigation, or synthesis worth reusing | Trivial lookups or one-off chat answers |
| `concepts/` or `queries/` | `summary` | Cross-cutting overviews and topic maps | Pages that can be classified more specifically |

Every synthesized page follows these rules:

- **Frontmatter:** `title`, `created`, `updated`, `type`, `tags`, `sources` are required; `created` and `updated` must be UTC ISO datetimes with seconds and a trailing `Z` (`YYYY-MM-DDTHH:MM:SSZ`); `confidence` (high/medium/low) and `contested` (true/false) are optional.
- **Body shape:** `# Title` followed by `## Summary`, `## Key facts`, `## Relationships`, `## Open questions`, `## Sources`.
- **Paths:** lowercase kebab-case (`concepts/llm-wiki.md`, `entities/anthropic.md`).
- **Links:** `[[wikilinks]]` between pages; new pages should have at least two useful outbound links when possible.
- **Thresholds:** create a page only when an entity/concept appears in 2+ sources or is central to one important source; split pages over ~200 lines.

The write skill automatically appends a provenance trailer (`<!-- kb-provenance: ... -->`) after the body, and updates `index.md` (navigation) and `log.md` (audit trail) on every meaningful write. Sources under `raw/` stay immutable; corrections and synthesis go into the wiki pages.

### How the AI explores it

The AI treats the vault as a graph, not just a text-search index.

1. Start with `index.md` and recent `log.md` to understand the current map and latest changes.
2. Search `kb_search_notes` with multiple terms: the user's wording, synonyms, entity names, and tags.
3. Narrow with `path_prefix` (`entities`, `concepts`, `comparisons`, `queries`, `raw`).
4. Follow `[[wikilinks]]` from relevant pages, reading linked pages when they may change the synthesis.
5. Prefer pages with higher confidence, newer dates, and multiple sources; surface low-confidence or contested pages explicitly.
6. When an answer becomes a reusable synthesis, file it as a `queries/` or `comparisons/` page and update `index.md` and `log.md`.

Because `kb_search_notes` returns snippets rather than whole files, in MCP-only mode the AI does not overwrite an existing note without the complete current note body.
