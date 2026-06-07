# Personal KB MCP

[English](README.md) | [한국어](README.ko.md) | [中文](README.zh.md) | [日本語](README.ja.md)

Private MCP server for a Git-backed Obsidian/Markdown knowledge base.

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
- Vault status, graph health, and metrics snapshots
- Vector DB extension point via `VectorIndex` and `NullVectorIndex`

## Local setup

```bash
uv sync --extra dev
cp .env.example .env
```

Edit `.env`, especially `KB_VAULT_PATH`.

## Run

```bash
uv run personal-kb-mcp
```

Hermes MCP config example:

```yaml
mcp_servers:
  personal_kb:
    url: "http://127.0.0.1:9999/mcp"
```

## Agent integrations for LLM Wiki workflows

This repository includes ready-to-copy MCP snippets, one canonical agent skill, and setup scripts for using the server as an Obsidian/Markdown LLM Wiki bridge from Hermes/Hermess, Claude Code, and Codex.

The expected flow is:

1. Run the MCP server with `uv run personal-kb-mcp`.
2. Connect the agent to `http://127.0.0.1:9999/mcp`.
3. Install the canonical `personal-kb-llm-wiki` skill so the agent knows the wiki conventions.
4. Restart the agent session so MCP tools and skills are reloaded.

### Files added for agent integrations

| Agent | MCP snippet | Skill source | Setup script |
| --- | --- | --- | --- |
| Hermes/Hermess | `mcp/hermess.yaml` | `skills/personal-kb-llm-wiki/` | `scripts/setup-hermess.sh` |
| Claude Code | `mcp/claude.json` | `skills/personal-kb-llm-wiki/` | `scripts/setup-claude.sh` |
| Codex | `mcp/codex.toml` | `skills/personal-kb-llm-wiki/` | `scripts/setup-codex.sh` |

The skill is intentionally single-source: all agents install the same `skills/personal-kb-llm-wiki/SKILL.md`. Agent-specific differences live in setup scripts and in the skill's "Agent-specific MCP names" section.

### Setup Hermes/Hermess

```bash
scripts/setup-hermess.sh
```

What it does:

- Copies `skills/personal-kb-llm-wiki/` to `${HERMES_HOME:-~/.hermes}/skills/personal-kb-llm-wiki/`
- Runs `hermes mcp add personal_kb --url http://127.0.0.1:9999/mcp`
- Runs `hermes mcp test personal_kb` when the CLI is available

Manual equivalent:

```yaml
mcp_servers:
  personal_kb:
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

- Copies `skills/personal-kb-llm-wiki/` to `${CLAUDE_SKILLS_DIR:-~/.claude/skills}/personal-kb-llm-wiki/`
- Runs `claude mcp add -s user --transport http personal-kb http://127.0.0.1:9999/mcp`
- Runs `claude mcp get personal-kb` when the CLI is available

Manual project-scoped `.mcp.json` equivalent:

```json
{
  "mcpServers": {
    "personal-kb": {
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

- Copies `skills/personal-kb-llm-wiki/` to `${CODEX_SKILLS_DIR:-${CODEX_HOME:-~/.codex}/skills}/personal-kb-llm-wiki/`
- Adds an idempotent `personal-kb-mcp` block to `${CODEX_CONFIG_PATH:-~/.codex/config.toml}`

Manual `~/.codex/config.toml` equivalent:

```toml
[mcp_servers.personal_kb]
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
--server-name NAME        # default: personal_kb for Hermes/Codex, personal-kb for Claude
```

Claude also supports `--scope local|user|project`. Codex also supports `--config /path/to/config.toml`.

### How agents should use the skill

The skill tells agents to:

- Call MCP status/health tools before writing.
- Orient on `SCHEMA.md`, `index.md`, and `log.md` when the vault is readable.
- Write complete Markdown notes through `kb_write_note`.
- Use returned `content_hash` as the next `if_hash` for optimistic concurrency.
- Keep raw sources immutable and update `index.md` plus `log.md` for durable wiki changes.

Current MCP tools exposed by the server are `kb_write_note`, `kb_vault_status`, `kb_graph_health`, and `kb_metrics`.

## Validate

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest --cov=personal_kb_mcp --cov-fail-under=80
```
