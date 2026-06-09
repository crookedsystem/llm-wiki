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

This repository includes ready-to-copy MCP snippets, one canonical agent skill, and setup scripts for using the server as an Obsidian/Markdown LLM Wiki bridge from Hermes/Hermess, Claude Code, and Codex.

The expected flow is:

1. Run the MCP server with `uv run llm-wiki`.
2. Connect the agent to `http://127.0.0.1:9999/mcp`.
3. Install the canonical `llm-wiki` skill so the agent knows the wiki conventions.
4. Restart the agent session so MCP tools and skills are reloaded.

### Files added for agent integrations

| Agent | MCP snippet | Skill source | Setup script |
| --- | --- | --- | --- |
| Hermes/Hermess | `mcp/hermess.yaml` | `skills/llm-wiki/` | `scripts/setup-hermess.sh` |
| Claude Code | `mcp/claude.json` | `skills/llm-wiki/` | `scripts/setup-claude.sh` |
| Codex | `mcp/codex.toml` | `skills/llm-wiki/` | `scripts/setup-codex.sh` |

The skill is intentionally single-source: all agents install the same `skills/llm-wiki/SKILL.md`. Agent-specific differences live in setup scripts and in the skill's "Agent-specific MCP names" section.

### Setup Hermes/Hermess

```bash
scripts/setup-hermess.sh
```

What it does:

- Copies `skills/llm-wiki/` to `${HERMES_HOME:-~/.hermes}/skills/llm-wiki/`
- Runs `hermes mcp add llm_wiki --url http://127.0.0.1:9999/mcp`
- Runs `hermes mcp test llm_wiki` when the CLI is available

Manual equivalent:

```yaml
mcp_servers:
  llm_wiki:
    url: "http://127.0.0.1:9999/mcp"
    timeout: 120
    connect_timeout: 30
```

After setup, restart Hermes or use `/reload-mcp` in an existing session if available.

### Setup Claude Code

```bash
scripts/setup-claude.sh
```

What it does:

- Copies `skills/llm-wiki/` to `${CLAUDE_SKILLS_DIR:-~/.claude/skills}/llm-wiki/`
- Runs `claude mcp add -s user --transport http llm-wiki http://127.0.0.1:9999/mcp`
- Runs `claude mcp get llm-wiki` when the CLI is available

Manual project-scoped `.mcp.json` equivalent:

```json
{
  "mcpServers": {
    "llm-wiki": {
      "type": "http",
      "url": "http://127.0.0.1:9999/mcp",
      "timeout": 120000
    }
  }
}
```

Claude may ask you to approve project-scoped `.mcp.json` servers the first time you open a project.

### Setup Codex

```bash
scripts/setup-codex.sh
```

What it does:

- Copies `skills/llm-wiki/` to `${CODEX_SKILLS_DIR:-${CODEX_HOME:-~/.codex}/skills}/llm-wiki/`
- Adds an idempotent `llm-wiki` block to `${CODEX_CONFIG_PATH:-~/.codex/config.toml}`

Manual `~/.codex/config.toml` equivalent:

```toml
[mcp_servers.llm_wiki]
url = "http://127.0.0.1:9999/mcp"
startup_timeout_sec = 30
tool_timeout_sec = 120
default_tools_approval_mode = "prompt"
```

Restart Codex after changing `config.toml` or skill files.

### Setup script options

All setup scripts support:

```bash
--dry-run                 # print actions without writing files or changing agent config
--server-url URL          # default: http://127.0.0.1:9999/mcp
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
