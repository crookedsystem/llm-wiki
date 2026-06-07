# Personal KB MCP

Private MCP server for a Git-backed Obsidian/Markdown knowledge base.

Implementation lands through small pull requests, each kept under 200 changed lines.

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
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
cp .env.example .env
```

Edit `.env`, especially `KB_VAULT_PATH`.

## Run

```bash
.venv/bin/personal-kb-mcp
```

Hermes MCP config example:

```yaml
mcp_servers:
  personal_kb:
    url: "http://127.0.0.1:9999/mcp"
```

## Validate

```bash
.venv/bin/python -m ruff format --check .
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy src tests
.venv/bin/python -m pytest --cov=personal_kb_mcp --cov-fail-under=80
```
