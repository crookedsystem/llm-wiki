# LLM Wiki MCP

[English](README.md) | [한국어](README.ko.md) | [中文](README.zh.md) | [日本語](README.ja.md)

Git 管理された Obsidian/Markdown LLM Wiki vault 向けの MCP サーバーです。

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
- `GET /metrics` REST endpoint で vault と graph counters を統合して提供
- `kb_search_notes` MCP tool による LLM Wiki Markdown 検索

## ローカル設定

```bash
uv sync --extra dev
cp .env.example .env
```

`.env` を編集してください。特に `KB_VAULT_PATH` を設定します。

### LLM Wiki vault の設定

`llm-wiki` では 2 つのフォルダを分けて考えてください。

`llm-wiki` repository はプログラムコードを置く Git repo です:

```text
/home/alice/projects/llm-wiki/
├── src/        # server code
├── tests/
├── scripts/
└── ...
```

`KB_VAULT_PATH` は実際の知識文書を保存する Markdown vault です:

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

`.env` では `KB_VAULT_PATH` を 2 つ目のフォルダに設定してください:

```env
KB_VAULT_PATH=/home/alice/Obsidian/LLM Wiki
KB_HOST=127.0.0.1
KB_PORT=9999
KB_MCP_PATH=/mcp
```

`KB_VAULT_PATH` を `llm-wiki/src` や Obsidian の `.obsidian/` 設定フォルダにしてはいけません。`SCHEMA.md`, `index.md`, `log.md` が入っている vault root を指す必要があります。

最も重要な区別はこれです:

```text
llm-wiki repository の src/    = server code
KB_VAULT_PATH の raw/          = original/source material
KB_VAULT_PATH の entities/...  = synthesized wiki pages
```

Agent は文書を作成・更新する前に `SCHEMA.md`, `index.md`, 最近の `log.md` を先に読む必要があります。

### Obsidian 接続

別の connector は不要です。Obsidian で **Open folder as vault** を使い、`KB_VAULT_PATH` と同じフォルダを開いてください。Obsidian と MCP server は同じ Markdown files を読み書きします。

推奨設定は attachment folder を `raw/assets/` にし、Wikilinks を有効に保ち、YAML frontmatter query が必要なら Dataview plugin を入れることです。Obsidian Sync を使う場合も、この同じ vault folder を同期してください。

## 実行

```bash
uv run llm-wiki
```

Hermes MCP 設定例：

```yaml
mcp_servers:
  llm_wiki:
    url: "http://127.0.0.1:9999/mcp"
```

## LLM Wiki workflow 用 agent integration

この repository には、Hermes/Hermess、Claude Code、Codex からこのサーバーを Obsidian/Markdown LLM Wiki bridge として使うための、コピーして使える MCP snippet、単一の canonical agent skill、setup script が含まれています。

想定 workflow は次のとおりです：

1. `uv run llm-wiki` で MCP サーバーを実行します。
2. agent を `http://127.0.0.1:9999/mcp` に接続します。
3. canonical `llm-wiki` skill をインストールし、agent が wiki convention を理解できるようにします。
4. MCP tool と skill が再読み込みされるように agent session を再起動します。

### Agent integration 用に追加されたファイル

| Agent | MCP snippet | Skill source | Setup script |
| --- | --- | --- | --- |
| Hermes/Hermess | `mcp/hermess.yaml` | `skills/llm-wiki/` | `scripts/setup-hermess.sh` |
| Claude Code | `mcp/claude.json` | `skills/llm-wiki/` | `scripts/setup-claude.sh` |
| Codex | `mcp/codex.toml` | `skills/llm-wiki/` | `scripts/setup-codex.sh` |

この skill は意図的に single-source 構成です。すべての agent が同じ `skills/llm-wiki/SKILL.md` をインストールします。Agent-specific な違いは setup script と、skill 内の「Agent-specific MCP names」セクションにあります。

### Hermes/Hermess の設定

```bash
scripts/setup-hermess.sh
```

実行内容：

- `skills/llm-wiki/` を `${HERMES_HOME:-~/.hermes}/skills/llm-wiki/` にコピー
- `hermes mcp add llm_wiki --url http://127.0.0.1:9999/mcp` を実行
- CLI が利用可能な場合は `hermes mcp test llm_wiki` を実行

手動設定 equivalent：

```yaml
mcp_servers:
  llm_wiki:
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

- `skills/llm-wiki/` を `${CLAUDE_SKILLS_DIR:-~/.claude/skills}/llm-wiki/` にコピー
- `claude mcp add -s user --transport http llm-wiki http://127.0.0.1:9999/mcp` を実行
- CLI が利用可能な場合は `claude mcp get llm-wiki` を実行

Project-scoped `.mcp.json` の手動設定 equivalent：

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

Project-scoped `.mcp.json` server を初めて開くとき、Claude が承認を求める場合があります。

### Codex の設定

```bash
scripts/setup-codex.sh
```

実行内容：

- `skills/llm-wiki/` を `${CODEX_SKILLS_DIR:-${CODEX_HOME:-~/.codex}/skills}/llm-wiki/` にコピー
- `${CODEX_CONFIG_PATH:-~/.codex/config.toml}` に idempotent な `llm-wiki` block を追加

手動 `~/.codex/config.toml` 設定 equivalent：

```toml
[mcp_servers.llm_wiki]
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
--server-name NAME        # デフォルト: Hermes/Codex は llm_wiki、Claude は llm-wiki
```

Claude は `--scope local|user|project` もサポートします。Codex は `--config /path/to/config.toml` もサポートします。

### Agent による skill の使い方

この skill は agent に次を指示します：

- 書き込み前に `kb_search_notes` で既存 Markdown wiki page を検索する。
- 直接ファイルアクセスまたは `kb_search_notes` snippet で `SCHEMA.md`、`index.md`、`log.md` を基準に orientation する。
- `kb_write_note` を通じて完全な Markdown note を書き込む。
- optimistic concurrency のため、返された `content_hash` を次の `if_hash` として使う。
- raw source は immutable に保ち、durable wiki 変更では `index.md` と `log.md` を更新する。

現在サーバーが公開している MCP tool は `kb_write_note` と `kb_search_notes` です。Vault/graph counters は REST `GET /metrics` endpoint で公開します。

## 検証

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest --cov=src --cov-fail-under=80
```
