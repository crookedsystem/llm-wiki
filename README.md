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
- Batch writes with `atomic=True` file rollback
- Source hash, content hash, and optional git commit hash in write results
- Provenance trailer on synthesized/meta written notes
- REST metrics endpoint at `GET /metrics` combining vault and graph counters
- LLM Wiki Markdown search through the `kb_search_notes` MCP tool
- Schema-first wiki map, link issue candidates, and update suggestions through `kb_wiki_context`
- Vault schema validation through `kb_validate_vault`
- Deterministic tag taxonomy reconciliation through `kb_reconcile_taxonomy`
- Schema-enforced writes through `kb_write_note`, including raw note metadata and body-only sha256 checks

## Local setup

```bash
uv sync --extra dev
cp .env.example .env
```

Edit `.env`, especially `KB_VAULT_PATH`.

### Configure the LLM Wiki vault

Think of `llm-wiki` as two different folders.

The `llm-wiki` repository is the program code:

```text
/home/alice/projects/llm-wiki/
├── src/        # server code
├── tests/
├── scripts/
└── ...
```

`KB_VAULT_PATH` is the Markdown vault that stores knowledge:

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

Set `.env` so `KB_VAULT_PATH` points at the second folder:

```env
KB_VAULT_PATH=/home/alice/Obsidian/LLM Wiki
KB_HOST=127.0.0.1
KB_PORT=9999
KB_MCP_PATH=/mcp
```

Do not set `KB_VAULT_PATH` to `llm-wiki/src` or to an Obsidian `.obsidian/` settings folder. It must point at the vault root that contains `SCHEMA.md`, `index.md`, and `log.md`.

Most important:

```text
llm-wiki repository src/       = server code
KB_VAULT_PATH raw/             = original/source material
KB_VAULT_PATH entities/...     = synthesized wiki pages
```

Agents should read `SCHEMA.md`, `index.md`, and recent `log.md` before writing.

### Connect Obsidian

No separate connector is needed. In Obsidian, use **Open folder as vault** and open the same folder configured as `KB_VAULT_PATH`. Obsidian and the MCP server read and write the same Markdown files.

Recommended: set Obsidian's attachment folder to `raw/assets/`, keep Wikilinks enabled, install Dataview if you need YAML frontmatter queries, and sync this same folder if you use Obsidian Sync.

## Run

```bash
uv run llm-wiki
```

Hermes MCP config example:

```yaml
mcp_servers:
  llm_wiki:
    url: "http://127.0.0.1:9999/mcp"
```

## Agent integrations for LLM Wiki workflows

This repository includes ready-to-copy MCP snippets, one canonical agent skill, and one uv-based setup entrypoint for using the server as an Obsidian/Markdown LLM Wiki bridge from Hermes/Hermess, Claude Code, and Codex.

The expected flow is:

1. Copy `.env.example` to `.env` and set `KB_VAULT_PATH`, `KB_HOST`, `KB_PORT`, and `KB_MCP_PATH` for the server you will run.
2. Run the MCP server with `uv run llm-wiki`.
3. Run the setup entrypoint. By default it installs every supported agent; pass `--agent` to install a subset. It also installs LLM Wiki input/stop hook scaffolds so prompt-time context loading and stop-time wiki update passes use the same MCP server.
4. Restart the agent session so MCP tools, skills, and any native hook/plugin configuration are reloaded.

### Files for agent integrations

| Agent | MCP snippet | Skill source | Install command |
| --- | --- | --- | --- |
| Hermes/Hermess | `mcp/hermess.yaml` | `skills/llm-wiki/` | `uv run python scripts/main.py --agent hermes` |
| Claude Code | `mcp/claude.json` | `skills/llm-wiki/` | `uv run python scripts/main.py --agent claude` |
| Codex | `mcp/codex.toml` | `skills/llm-wiki/` | `uv run python scripts/main.py --agent codex` |

The setup entrypoint is `scripts/main.py`. Run it without `--agent` to install Hermes/Hermess, Claude Code, and Codex in one pass. The reusable code lives under `scripts/setup_support/`, so env loading, MCP URL resolution, skill copying, hook installation, duplicate detection, and Codex TOML editing use the same path for every agent. The runtime hook helper lives at `scripts/agent_hooks/llm_wiki_agent_hook.py`.

The skill is intentionally single-source: all agents install the same `skills/llm-wiki/SKILL.md`. Agent-specific differences live in setup code and in the skill's "Agent-specific MCP names" section.

### Setup entrypoint reads `.env`

The setup entrypoint reads the repository `.env` by default and then lets already-exported shell variables override it. Pass `--env-file /path/to/file` to use another dotenv file.

MCP URL resolution order:

1. `--server-url URL`
2. `LLM_WIKI_MCP_URL`
3. `LLM_WIKI_MCP_SCHEME` + `LLM_WIKI_MCP_HOST` or `KB_HOST` + `KB_PORT` + `KB_MCP_PATH`

If `KB_HOST=0.0.0.0`, setup converts it to `127.0.0.1` for local agent clients. The server may bind to all interfaces, but local agents should normally connect through loopback.

MCP server name resolution order:

1. `--server-name NAME`
2. `LLM_WIKI_MCP_SERVER_NAME`
3. Agent default: `llm_wiki` for Hermes/Codex, `llm-wiki` for Claude Code

Hook setup is enabled by default. Set `LLM_WIKI_INSTALL_HOOKS=false` or pass `--no-hooks` to skip it. The generated hook scripts run the same helper in two modes:

- user input: query `kb_search_notes` and print a compact `<llm-wiki-context>` block for the model;
- stop/completion: ask the model to do one final MCP update pass, writing only durable facts/decisions/procedures and updating `index.md`/`log.md` when content changes.

Hook locations are configurable with `HERMES_LLM_WIKI_HOOKS_DIR`, `CLAUDE_HOOKS_DIR`, `CLAUDE_SETTINGS_PATH`, `CODEX_LLM_WIKI_HOOKS_DIR`, and `CODEX_HOOKS_JSON_PATH`.

### Existing MCP configs are not overwritten

Setup adds a server only when it is missing:

- Claude Code: checks `claude mcp get <name>` and `claude mcp list` before running `claude mcp add`.
- Hermes/Hermess: checks `hermes mcp list` for the same name or URL before running `hermes mcp add`.
- Codex: parses `${CODEX_CONFIG_PATH:-~/.codex/config.toml}` and skips when the same server name or URL already exists.

If a matching server exists, setup prints why it skipped and leaves the existing MCP config unchanged.

### Setup Hermes/Hermess

```bash
uv run python scripts/main.py --agent hermes
```

What it does:

- Copies `skills/llm-wiki/` to `${HERMES_HOME:-~/.hermes}/skills/llm-wiki/`
- Installs reusable hook commands under `${HERMES_LLM_WIKI_HOOKS_DIR:-${HERMES_HOME:-~/.hermes}/hooks/llm-wiki}/`
- Adds `${LLM_WIKI_MCP_SERVER_NAME:-llm_wiki}` to Hermes MCP config only when missing
- Runs `hermes mcp test <server-name>` when the CLI is available

After setup, restart Hermes or use `/reload-mcp` in an existing session if available.

### Setup Claude Code

```bash
uv run python scripts/main.py --agent claude
```

What it does:

- Copies `skills/llm-wiki/` to `${CLAUDE_SKILLS_DIR:-~/.claude/skills}/llm-wiki/`
- Installs `llm-wiki-context-hook.sh` and `llm-wiki-stop-hook.sh` under `${CLAUDE_HOOKS_DIR:-~/.claude/hooks/llm-wiki}/`
- Merges Claude Code `UserPromptSubmit` and `Stop` hook entries into `${CLAUDE_SETTINGS_PATH:-~/.claude/settings.json}` without duplicating existing entries
- Adds `${LLM_WIKI_MCP_SERVER_NAME:-llm-wiki}` with `claude mcp add -s ${CLAUDE_MCP_SCOPE:-user} --transport http ...` only when missing
- Runs `claude mcp get <server-name>` when the CLI is available

The Claude `UserPromptSubmit` hook prints wiki context before the model starts. The `Stop` hook emits a one-time block decision asking Claude to update LLM Wiki through MCP before it finishes; Claude sets `stop_hook_active=true` on the follow-up stop event, so the hook does not loop forever.

Claude may ask you to approve project-scoped `.mcp.json` servers the first time you open a project.

### Setup Codex

```bash
uv run python scripts/main.py --agent codex
```

What it does:

- Copies `skills/llm-wiki/` to `${CODEX_SKILLS_DIR:-${CODEX_HOME:-~/.codex}/skills}/llm-wiki/`
- Installs `llm-wiki-context-hook.sh` and `llm-wiki-stop-hook.sh` under `${CODEX_LLM_WIKI_HOOKS_DIR:-${CODEX_HOME:-~/.codex}/hooks/llm-wiki}/`
- Merges Codex `UserPromptSubmit` and `Stop` hook entries into `${CODEX_HOOKS_JSON_PATH:-~/.codex/hooks.json}` without duplicating existing entries
- Appends a new `[mcp_servers.<name>]` block to `${CODEX_CONFIG_PATH:-~/.codex/config.toml}` only when the same name or URL is absent

Codex (2026+) shares Claude Code's hook JSON schema, so its `Stop` hook also emits a one-time `decision=block` asking the agent to update LLM Wiki before it finishes; the helper skips re-blocking once `stop_hook_active=true`, so the hook does not loop. Restart Codex after changing `config.toml`, `hooks.json`, or skill files.

### Setup entrypoint options

Install all supported agents:

```bash
uv run python scripts/main.py
```

Install selected agents by passing `--agent` one or more times:

```bash
uv run python scripts/main.py --agent claude
uv run python scripts/main.py --agent claude --agent codex
```

The setup entrypoint supports:

```bash
--agent {hermes,claude,codex}  # repeatable; omit to install all agents
--dry-run                 # print actions without writing files or changing agent config
--env-file PATH           # default: repository .env
--server-url URL          # override .env MCP URL resolution
--server-name NAME        # default: llm_wiki for Hermes/Codex, llm-wiki for Claude
--no-hooks                # skip input/stop hook scaffold installation
--claude-settings PATH    # Claude settings JSON to merge hooks into
```

Claude also supports `--scope local|user|project`. Codex also supports `--config /path/to/config.toml`.

### How agents should use the skill

The skill tells agents to:

- Use `kb_search_notes` to search existing Markdown wiki pages before writing.
- Orient on `SCHEMA.md`, `index.md`, and `log.md` with direct file access or `kb_search_notes` snippets.
- Apply the skill's built-in schema, page-type, index, log, and provenance guidance when a new vault does not have `SCHEMA.md` yet.
- Treat `kb_search_notes` as snippets, not full file reads. Agents should not update existing notes in MCP-only mode unless they have the complete current note body.
- Write complete Markdown notes through `kb_write_note`; the server rejects schema violations before writing.
- Start wiki work with `kb_wiki_context` so allowed tags, page types, index, recent log, and schema health are visible before drafting.
- Use `kb_validate_vault` and `kb_reconcile_taxonomy` for deterministic schema hygiene and tag taxonomy repair.
- Use returned `content_hash` as the next `if_hash` for optimistic concurrency.
- Keep raw sources immutable and update `index.md` plus `log.md` for durable wiki changes.
- Use the installed hook commands with native hooks, plugins, or wrappers: load compact wiki context at user-input time and run a stop-time update pass after the agent finishes. Claude Code and Codex are wired automatically by setup because they share the same `UserPromptSubmit`/`Stop` hook schema (in-loop `decision=block` re-prompt). Hermes/Hermess exposes only finalize-style session hooks, so it gets reusable scripts to wire into a plugin/wrapper or finalize hook for an out-of-loop update pass.

Current MCP tools exposed by the server are `kb_write_note`, `kb_search_notes`, `kb_wiki_context`, `kb_validate_vault`, and `kb_reconcile_taxonomy`. Vault/graph counters are exposed through the REST `GET /metrics` endpoint.

## Validate

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest --cov=src --cov-fail-under=80
```
