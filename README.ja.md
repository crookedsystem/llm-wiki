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

この repository には、Hermes/Hermess、Claude Code、Codex からこのサーバーを Obsidian/Markdown LLM Wiki bridge として使うための、コピーして使える MCP snippet、単一の canonical agent skill、uv ベースの setup entrypoint が含まれています。

想定 workflow は次のとおりです：

1. `.env.example` を `.env` にコピーし、実行するサーバーに合わせて `KB_VAULT_PATH`、`KB_HOST`、`KB_PORT`、`KB_MCP_PATH` を設定します。
2. `uv run llm-wiki` で MCP サーバーを実行します。
3. Setup entrypoint を実行します。デフォルトでは対応するすべての agent をインストールし、一部だけを対象にする場合は `--agent` を渡します。同じ MCP server を使って user input 時の context loading と stop-time wiki update pass を実行する hook scaffold も同時にインストールします。
4. MCP tool、skill、native hook/plugin 設定が再読み込みされるように agent session を再起動します。

### Agent integration 用ファイル

| Agent | MCP snippet | Skill source | Install command |
| --- | --- | --- | --- |
| Hermes/Hermess | `mcp/hermess.yaml` | `skills/llm-wiki/` | `uv run python scripts/main.py --agent hermes` |
| Claude Code | `mcp/claude.json` | `skills/llm-wiki/` | `uv run python scripts/main.py --agent claude` |
| Codex | `mcp/codex.toml` | `skills/llm-wiki/` | `uv run python scripts/main.py --agent codex` |

Setup entrypoint は `scripts/main.py` です。`--agent` なしで実行すると Hermes/Hermess、Claude Code、Codex を一度にインストールします。再利用コードは `scripts/setup_support/` にあり、env 読み込み、MCP URL 解決、skill コピー、hook インストール、重複チェック、Codex TOML 編集をすべての agent が同じコードパスで使います。Runtime hook helper は `scripts/agent_hooks/llm_wiki_agent_hook.py` です。

この skill は意図的に single-source 構成です。すべての agent が同じ `skills/llm-wiki/SKILL.md` をインストールします。Agent-specific な違いは setup code と、skill 内の「Agent-specific MCP names」セクションにあります。

### Setup entrypoint は `.env` を読みます

Setup entrypoint はデフォルトで repository の `.env` を読み、すでに export されている shell 変数があれば `.env` より優先します。別の dotenv ファイルを使う場合は `--env-file /path/to/file` を渡します。

MCP URL の解決順：

1. `--server-url URL`
2. `LLM_WIKI_MCP_URL`
3. `LLM_WIKI_MCP_SCHEME` + `LLM_WIKI_MCP_HOST` または `KB_HOST` + `KB_PORT` + `KB_MCP_PATH`

`KB_HOST=0.0.0.0` の場合、setup はローカル agent client 用に `127.0.0.1` に変換します。サーバーは全 interface に bind できますが、同じマシン上の agent は通常 loopback で接続します。

MCP server name の解決順：

1. `--server-name NAME`
2. `LLM_WIKI_MCP_SERVER_NAME`
3. Agent デフォルト: Hermes/Codex は `llm_wiki`、Claude Code は `llm-wiki`

Hook setup はデフォルトで有効です。無効にするには `LLM_WIKI_INSTALL_HOOKS=false` を設定するか `--no-hooks` を渡します。生成される hook script は同じ helper を 2 つの mode で実行します:

- user input: `kb_search_notes` を query し、model 用の compact `<llm-wiki-context>` block を出力
- stop/completion: 最後の MCP update pass を model に依頼し、durable fact/decision/procedure だけを書き、content 変更時に `index.md`/`log.md` を更新

Hook location は `HERMES_LLM_WIKI_HOOKS_DIR`、`CLAUDE_HOOKS_DIR`、`CLAUDE_SETTINGS_PATH`、`CODEX_LLM_WIKI_HOOKS_DIR` で変更できます。

### 既存の MCP config は上書きしません

Setup は server が存在しない場合だけ追加します：

- Claude Code: `claude mcp get <name>` と `claude mcp list` を確認してから `claude mcp add` を実行します。
- Hermes/Hermess: `hermes mcp list` で同じ name または URL を確認してから `hermes mcp add` を実行します。
- Codex: `${CODEX_CONFIG_PATH:-~/.codex/config.toml}` を parse し、同じ server name または URL があれば skip します。

一致する server がある場合、setup は skip 理由を表示し、既存 MCP config は変更しません。

### Hermes/Hermess の設定

```bash
uv run python scripts/main.py --agent hermes
```

実行内容：

- `skills/llm-wiki/` を `${HERMES_HOME:-~/.hermes}/skills/llm-wiki/` にコピー
- reusable hook command を `${HERMES_LLM_WIKI_HOOKS_DIR:-${HERMES_HOME:-~/.hermes}/hooks/llm-wiki}/` にインストール
- `${LLM_WIKI_MCP_SERVER_NAME:-llm_wiki}` が存在しない場合だけ Hermes MCP config に追加
- CLI が利用可能な場合は `hermes mcp test <server-name>` を実行

設定後は Hermes を再起動するか、既存 session で利用可能な場合は `/reload-mcp` を使ってください。

### Claude Code の設定

```bash
uv run python scripts/main.py --agent claude
```

実行内容：

- `skills/llm-wiki/` を `${CLAUDE_SKILLS_DIR:-~/.claude/skills}/llm-wiki/` にコピー
- `llm-wiki-context-hook.sh` と `llm-wiki-stop-hook.sh` を `${CLAUDE_HOOKS_DIR:-~/.claude/hooks/llm-wiki}/` にインストール
- Claude Code の `UserPromptSubmit` と `Stop` hook entry を `${CLAUDE_SETTINGS_PATH:-~/.claude/settings.json}` に重複なしで merge
- `${LLM_WIKI_MCP_SERVER_NAME:-llm-wiki}` が存在しない場合だけ `claude mcp add -s ${CLAUDE_MCP_SCOPE:-user} --transport http ...` で追加
- CLI が利用可能な場合は `claude mcp get <server-name>` を実行

Claude の `UserPromptSubmit` hook は model 開始前に wiki context を出力します。`Stop` hook は Claude が終了する前に MCP で LLM Wiki を更新するよう一度だけ block decision を返し、follow-up stop event の `stop_hook_active=true` では再 block しないため無限 loop を防ぎます。

Project-scoped `.mcp.json` server を初めて開くとき、Claude が承認を求める場合があります。

### Codex の設定

```bash
uv run python scripts/main.py --agent codex
```

実行内容：

- `skills/llm-wiki/` を `${CODEX_SKILLS_DIR:-${CODEX_HOME:-~/.codex}/skills}/llm-wiki/` にコピー
- reusable hook command を `${CODEX_LLM_WIKI_HOOKS_DIR:-${CODEX_HOME:-~/.codex}/hooks/llm-wiki}/` にインストール
- 同じ name または URL が存在しない場合だけ `${CODEX_CONFIG_PATH:-~/.codex/config.toml}` に新しい `[mcp_servers.<name>]` block を追加

`config.toml` または skill file を変更した後は Codex を再起動してください。

### Setup entrypoint option

対応するすべての agent をインストールします：

```bash
uv run python scripts/main.py
```

一部の agent だけをインストールするには、`--agent` を 1 回以上渡します：

```bash
uv run python scripts/main.py --agent claude
uv run python scripts/main.py --agent claude --agent codex
```

Setup entrypoint は次の option をサポートします：

```bash
--agent {hermes,claude,codex}  # 繰り返し指定可能。省略するとすべての agent をインストール
--dry-run                 # ファイル書き込みや agent config 変更をせず、実行予定の操作を表示
--env-file PATH           # デフォルト: repository .env
--server-url URL          # .env MCP URL resolution を override
--server-name NAME        # デフォルト: Hermes/Codex は llm_wiki、Claude は llm-wiki
--no-hooks                # input/stop hook scaffold installation を skip
--claude-settings PATH    # hook を merge する Claude settings JSON
```

Claude は `--scope local|user|project` もサポートします。Codex は `--config /path/to/config.toml` もサポートします。

### Agent による skill の使い方

この skill は agent に次を指示します：

- 書き込み前に `kb_search_notes` で既存 Markdown wiki page を検索する。
- 直接ファイルアクセスまたは `kb_search_notes` snippet で `SCHEMA.md`、`index.md`、`log.md` を基準に orientation する。
- 新しい vault にまだ `SCHEMA.md` がない場合、skill 内蔵の schema、page type、index、log、provenance ガイドで初期化する。
- `kb_search_notes` は完全なファイル読み取りではなく snippet 検索として扱う。MCP-only mode では完全な現在の note body がない限り既存 note を更新しない。
- `kb_write_note` を通じて完全な Markdown note を書き込む。
- optimistic concurrency のため、返された `content_hash` を次の `if_hash` として使う。
- raw source は immutable に保ち、durable wiki 変更では `index.md` と `log.md` を更新する。
- インストールされた hook command を native hook、plugin、wrapper と一緒に使う。ユーザー入力時に compact wiki context を読み込み、agent 終了時に stop-time update pass を実行する。Claude Code は setup が自動で接続し、Hermes/Hermess と Codex は Claude の JSON hook schema を共有しないため reusable script をインストールする。

現在サーバーが公開している MCP tool は `kb_write_note` と `kb_search_notes` です。Vault/graph counters は REST `GET /metrics` endpoint で公開します。

## 検証

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest --cov=src --cov-fail-under=80
```
