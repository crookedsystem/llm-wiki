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
- Provenance trailer on written notes
- REST metrics endpoint at `GET /metrics` combining vault and graph counters
- LLM Wiki Markdown search through the `kb_search_notes` MCP tool

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

This repository includes ready-to-copy MCP snippets, one canonical agent skill, and uv-based setup scripts for using the server as an Obsidian/Markdown LLM Wiki bridge from Hermes/Hermess, Claude Code, and Codex.

The expected flow is:

1. Copy `.env.example` to `.env` and set `KB_VAULT_PATH`, `KB_HOST`, `KB_PORT`, and `KB_MCP_PATH` for the server you will run.
2. Run the MCP server with `uv run llm-wiki`.
3. Run the setup script for each agent you want to connect.
4. Restart the agent session so MCP tools and skills are reloaded.

### Files for agent integrations

| Agent | MCP snippet | Skill source | Setup wrapper | Python entrypoint |
| --- | --- | --- | --- | --- |
| Hermes/Hermess | `mcp/hermess.yaml` | `skills/llm-wiki/` | `scripts/setup-hermess.sh` | `uv run python scripts/setup_agents.py hermes` |
| Claude Code | `mcp/claude.json` | `skills/llm-wiki/` | `scripts/setup-claude.sh` | `uv run python scripts/setup_agents.py claude` |
| Codex | `mcp/codex.toml` | `skills/llm-wiki/` | `scripts/setup-codex.sh` | `uv run python scripts/setup_agents.py codex` |

The shell wrappers only locate the repository and call the shared Python implementation through `uv`. The reusable code lives under `scripts/setup_support/`, so env loading, MCP URL resolution, skill copying, duplicate detection, and Codex TOML editing use the same path for every agent.

The skill is intentionally single-source: all agents install the same `skills/llm-wiki/SKILL.md`. Agent-specific differences live in setup code and in the skill's "Agent-specific MCP names" section.

### Setup scripts read `.env`

The setup scripts read the repository `.env` by default and then let already-exported shell variables override it. Pass `--env-file /path/to/file` to use another dotenv file.

MCP URL resolution order:

1. `--server-url URL`
2. `LLM_WIKI_MCP_URL`
3. `LLM_WIKI_MCP_SCHEME` + `LLM_WIKI_MCP_HOST` or `KB_HOST` + `KB_PORT` + `KB_MCP_PATH`

If `KB_HOST=0.0.0.0`, setup converts it to `127.0.0.1` for local agent clients. The server may bind to all interfaces, but local agents should normally connect through loopback.

MCP server name resolution order:

1. `--server-name NAME`
2. `LLM_WIKI_MCP_SERVER_NAME`
3. Agent default: `llm_wiki` for Hermes/Codex, `llm-wiki` for Claude Code

### Existing MCP configs are not overwritten

Setup adds a server only when it is missing:

- Claude Code: checks `claude mcp get <name>` and `claude mcp list` before running `claude mcp add`.
- Hermes/Hermess: checks `hermes mcp list` for the same name or URL before running `hermes mcp add`.
- Codex: parses `${CODEX_CONFIG_PATH:-~/.codex/config.toml}` and skips when the same server name or URL already exists.

If a matching server exists, setup prints why it skipped and leaves the existing MCP config unchanged.

### Setup Hermes/Hermess

```bash
scripts/setup-hermess.sh
# or directly:
uv run python scripts/setup_agents.py hermes
```

What it does:

- Copies `skills/llm-wiki/` to `${HERMES_HOME:-~/.hermes}/skills/llm-wiki/`
- Adds `${LLM_WIKI_MCP_SERVER_NAME:-llm_wiki}` to Hermes MCP config only when missing
- Runs `hermes mcp test <server-name>` when the CLI is available

After setup, restart Hermes or use `/reload-mcp` in an existing session if available.

### Setup Claude Code

```bash
scripts/setup-claude.sh
# or directly:
uv run python scripts/setup_agents.py claude
```

What it does:

- Copies `skills/llm-wiki/` to `${CLAUDE_SKILLS_DIR:-~/.claude/skills}/llm-wiki/`
- Adds `${LLM_WIKI_MCP_SERVER_NAME:-llm-wiki}` with `claude mcp add -s ${CLAUDE_MCP_SCOPE:-user} --transport http ...` only when missing
- Runs `claude mcp get <server-name>` when the CLI is available

Claude may ask you to approve project-scoped `.mcp.json` servers the first time you open a project.

### Setup Codex

```bash
scripts/setup-codex.sh
# or directly:
uv run python scripts/setup_agents.py codex
```

What it does:

- Copies `skills/llm-wiki/` to `${CODEX_SKILLS_DIR:-${CODEX_HOME:-~/.codex}/skills}/llm-wiki/`
- Appends a new `[mcp_servers.<name>]` block to `${CODEX_CONFIG_PATH:-~/.codex/config.toml}` only when the same name or URL is absent

Restart Codex after changing `config.toml` or skill files.

### Setup script options

All setup scripts support:

```bash
--dry-run                 # print actions without writing files or changing agent config
--env-file PATH           # default: repository .env
--server-url URL          # override .env MCP URL resolution
--server-name NAME        # default: llm_wiki for Hermes/Codex, llm-wiki for Claude
```

Claude also supports `--scope local|user|project`. Codex also supports `--config /path/to/config.toml`.

### How agents should use the skill

The skill tells agents to:

- Use `kb_search_notes` to search existing Markdown wiki pages before writing.
- Orient on `SCHEMA.md`, `index.md`, and `log.md` with direct file access or `kb_search_notes` snippets.
- Write complete Markdown notes through `kb_write_note`.
- Use returned `content_hash` as the next `if_hash` for optimistic concurrency.
- Keep raw sources immutable and update `index.md` plus `log.md` for durable wiki changes.

Current MCP tools exposed by the server are `kb_write_note` and `kb_search_notes`. Vault/graph counters are exposed through the REST `GET /metrics` endpoint.

## Validate

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest --cov=src --cov-fail-under=80
```
