# Personal KB MCP

[English](README.md) | [한국어](README.ko.md) | [中文](README.zh.md) | [日本語](README.ja.md)

Git 管理された Obsidian/Markdown ナレッジベース向けのプライベート MCP サーバーです。

## 現在の機能

- `127.0.0.1:9999/mcp` で Streamable HTTP MCP を提供する FastAPI アプリ
- `GET /health` ヘルスチェックエンドポイント
- FastAPI REST エラーは `{code, message, timestamp}` JSON envelope を使用
- 設定済み vault 内での安全な Markdown note path 解決
- 単一の `WriteQueue` によるシリアライズされた書き込み
- 更新用の `if_hash` optimistic concurrency
- `atomic=True` batch write のファイル rollback
- write 結果に含まれる source hash、content hash、任意の git commit hash
- 書き込まれた note の provenance trailer
- vault status、graph health、metrics snapshot
- `VectorIndex` と `NullVectorIndex` による Vector DB 拡張ポイント

## ローカル設定

```bash
uv sync --extra dev
cp .env.example .env
```

`.env` を編集してください。特に `KB_VAULT_PATH` を設定します。

## 実行

```bash
uv run personal-kb-mcp
```

Hermes MCP 設定例：

```yaml
mcp_servers:
  personal_kb:
    url: "http://127.0.0.1:9999/mcp"
```

## LLM Wiki workflow 用 agent integration

この repository には、Hermes/Hermess、Claude Code、Codex からこのサーバーを Obsidian/Markdown LLM Wiki bridge として使うための、コピーして使える MCP snippet、単一の canonical agent skill、setup script が含まれています。

想定 workflow は次のとおりです：

1. `uv run personal-kb-mcp` で MCP サーバーを実行します。
2. agent を `http://127.0.0.1:9999/mcp` に接続します。
3. canonical `personal-kb-llm-wiki` skill をインストールし、agent が wiki convention を理解できるようにします。
4. MCP tool と skill が再読み込みされるように agent session を再起動します。

### Agent integration 用に追加されたファイル

| Agent | MCP snippet | Skill source | Setup script |
| --- | --- | --- | --- |
| Hermes/Hermess | `mcp/hermess.yaml` | `skills/personal-kb-llm-wiki/` | `scripts/setup-hermess.sh` |
| Claude Code | `mcp/claude.json` | `skills/personal-kb-llm-wiki/` | `scripts/setup-claude.sh` |
| Codex | `mcp/codex.toml` | `skills/personal-kb-llm-wiki/` | `scripts/setup-codex.sh` |

この skill は意図的に single-source 構成です。すべての agent が同じ `skills/personal-kb-llm-wiki/SKILL.md` をインストールします。Agent-specific な違いは setup script と、skill 内の「Agent-specific MCP names」セクションにあります。

### Hermes/Hermess の設定

```bash
scripts/setup-hermess.sh
```

実行内容：

- `skills/personal-kb-llm-wiki/` を `${HERMES_HOME:-~/.hermes}/skills/personal-kb-llm-wiki/` にコピー
- `hermes mcp add personal_kb --url http://127.0.0.1:9999/mcp` を実行
- CLI が利用可能な場合は `hermes mcp test personal_kb` を実行

手動設定 equivalent：

```yaml
mcp_servers:
  personal_kb:
    url: "http://127.0.0.1:9999/mcp"
    timeout: 120
    connect_timeout: 30
```

設定後は Hermes を再起動するか、既存 session で利用可能な場合は `/reload-mcp` を使ってください。

### Claude Code の設定

```bash
scripts/setup-claude.sh
```

実行内容：

- `skills/personal-kb-llm-wiki/` を `${CLAUDE_SKILLS_DIR:-~/.claude/skills}/personal-kb-llm-wiki/` にコピー
- `claude mcp add -s user --transport http personal-kb http://127.0.0.1:9999/mcp` を実行
- CLI が利用可能な場合は `claude mcp get personal-kb` を実行

Project-scoped `.mcp.json` の手動設定 equivalent：

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

Project-scoped `.mcp.json` server を初めて開くとき、Claude が承認を求める場合があります。

### Codex の設定

```bash
scripts/setup-codex.sh
```

実行内容：

- `skills/personal-kb-llm-wiki/` を `${CODEX_SKILLS_DIR:-${CODEX_HOME:-~/.codex}/skills}/personal-kb-llm-wiki/` にコピー
- `${CODEX_CONFIG_PATH:-~/.codex/config.toml}` に idempotent な `personal-kb-mcp` block を追加

手動 `~/.codex/config.toml` 設定 equivalent：

```toml
[mcp_servers.personal_kb]
url = "http://127.0.0.1:9999/mcp"
startup_timeout_sec = 30
tool_timeout_sec = 120
default_tools_approval_mode = "prompt"
```

`config.toml` または skill file を変更した後は Codex を再起動してください。

### Setup script option

すべての setup script は次の option をサポートします：

```bash
--dry-run                 # ファイル書き込みや agent config 変更をせず、実行予定の操作を表示
--server-url URL          # デフォルト: http://127.0.0.1:9999/mcp
--server-name NAME        # デフォルト: Hermes/Codex は personal_kb、Claude は personal-kb
```

Claude は `--scope local|user|project` もサポートします。Codex は `--config /path/to/config.toml` もサポートします。

### Agent による skill の使い方

この skill は agent に次を指示します：

- 書き込み前に MCP status/health tool を呼び出す。
- vault が読める場合は `SCHEMA.md`、`index.md`、`log.md` を確認して orientation する。
- `kb_write_note` を通じて完全な Markdown note を書き込む。
- optimistic concurrency のため、返された `content_hash` を次の `if_hash` として使う。
- raw source は immutable に保ち、durable wiki 変更では `index.md` と `log.md` を更新する。

現在サーバーが公開している MCP tool は `kb_write_note`、`kb_vault_status`、`kb_graph_health`、`kb_metrics` です。

## 検証

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest --cov=personal_kb_mcp --cov-fail-under=80
```
