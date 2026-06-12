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

## How to Start

### `.env` の設定

```bash
uv sync --extra dev
cp .env.example .env
```

`.env` で、少なくとも vault パスと MCP サーバーのアドレスを設定します。

```env
KB_VAULT_PATH=/home/alice/Obsidian/LLM Wiki
KB_HOST=127.0.0.1
KB_PORT=9999
KB_MCP_PATH=/mcp
```

`KB_VAULT_PATH` は実際の Markdown 知識文書が置かれている vault root です。`llm-wiki/src` や Obsidian の `.obsidian/` 設定フォルダではなく、`SCHEMA.md`、`index.md`、`log.md` が入っているフォルダを指す必要があります。

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

ネットワークのルールはシンプルです。同じマシンからのみ使うなら `KB_HOST=127.0.0.1` のままにします。リモート agent が接続する必要がある場合は、サーバーを `KB_HOST=0.0.0.0` または到達可能な bind IP で起動し、agent 設定には `LLM_WIKI_MCP_URL=http://<サーバーIPまたはドメイン>:9999/mcp` または `--server-url` で実際の接続 URL を明示します。`KB_HOST=0.0.0.0` は同じマシンの client 用 URL では `127.0.0.1` に変換されるため、remote では URL override が必要です。

Obsidian は別の connector なしで **Open folder as vault** で `KB_VAULT_PATH` と同じフォルダを開けば使えます。推奨設定は attachment folder を `raw/assets/` にし、Wikilinks を有効にしておくことです。

### MCP サーバーの起動

```bash
uv run llm-wiki
```

デフォルト endpoint は `http://127.0.0.1:9999/mcp` です。サーバー起動後は `GET /health` で状態を確認でき、MCP tool は `kb_search_notes`、`kb_write_note` を公開します。Vault/graph counter は REST `GET /metrics` で確認します。

### Hook setup の方法

サーバーを起動した状態で、別のターミナルから setup entrypoint を実行します。

```bash
uv run python scripts/main.py                 # Hermes/Hermess、Claude Code、Codex すべて
uv run python scripts/main.py --agent claude  # 特定の agent だけインストール
uv run python scripts/main.py --agent codex --server-url http://127.0.0.1:9999/mcp
```

`scripts/main.py` は `.env` と shell export 値を読み、skill、MCP config、hook command をインストールします。同じ server name または URL がすでにある場合は、既存の MCP config を上書きしません。

デフォルトでは、setup は prompt-time context hook を先にインストールします。Hook インストールが有効な場合、Stop hook が LLM response の受け取りを妨げる可能性があることを警告し、大文字 `Y` または `N` の入力を求めます。`Y` は Stop hook をインストールし、`N` は context hook のみで続行します。無効な入力では再度確認し、non-interactive stdin/EOF ではインストール前に中止します。`--dry-run` はこの interactive prompt を skip し、dry-run plan に Stop hook を含めません。

URL の決定順は `--server-url` -> `LLM_WIKI_MCP_URL` -> `KB_HOST`/`KB_PORT`/`KB_MCP_PATH` です。Server name は `--server-name` -> `LLM_WIKI_MCP_SERVER_NAME` -> agent デフォルト値の順で決まります。すべての hook インストールを無効にするには `LLM_WIKI_INSTALL_HOOKS=false` または `--no-hooks` を使います。

設定後は agent session を再起動して、MCP tool、skill、hook 設定を再読み込みします。

## How to Work

### Hook の動作原理

Setup は agent ごとの hook directory に `llm-wiki-context-hook.sh` を作成します。Stop hook prompt に `Y` と答えた場合だけ `llm-wiki-stop-hook.sh` を作成し、Claude Code と Codex は選択された hook entry を `UserPromptSubmit`/`Stop` hook 設定へ merge します。Hermes/Hermess には、finalize 系 hook へ接続できるよう再利用可能な script をインストールします。

Context hook はユーザー入力時に `kb_search_notes` を呼び出し、関連する wiki snippet を model の前に付け加えます。選択された場合、Stop hook は終了直前に wiki-worthy な知識だけを判断して記録するよう update pass を依頼します。Claude Code と Codex は一度 `decision=block` で model を再呼び出しし、`stop_hook_active=true` になると再び block しないため loop を回避します。Hook helper や `uv` が無い場合、hook は agent の実行を妨げないよう静かに終了します。

### Agent が skill を使う方法

この skill は agent に次を指示します：

- 書き込み前に `kb_search_notes` で既存の Markdown wiki page を検索する
- 直接ファイルアクセスまたは `kb_search_notes` snippet で `SCHEMA.md`、`index.md`、`log.md` を基準に orientation する
- 新しい vault にまだ `SCHEMA.md` がない場合、skill 内蔵の schema、page type、index、log、provenance ガイドで初期化する
- `kb_search_notes` は完全なファイル読み取りではなく snippet 検索なので、MCP-only mode では完全な現在の note body が無い限り既存 note を更新しない
- `kb_write_note` を通じて完全な Markdown note を書き込む
- optimistic concurrency のため、返された `content_hash` を次の `if_hash` として使う
- raw source は immutable に保ち、durable wiki 変更時に `index.md` と `log.md` を更新する
- インストールされた hook command を native hook、plugin、wrapper と一緒に使う。ユーザー入力時に compact wiki context を読み込み、setup で選択した場合は agent 終了時に stop-time update pass を実行する。Claude Code と Codex は同じ `UserPromptSubmit`/`Stop` hook schema（in-loop `decision=block` 再プロンプト）を共有するため、選択された場合は setup が接続できる。Hermes/Hermess は finalize 系の session hook しか提供しないため、plugin/wrapper や finalize hook に接続して out-of-loop の update pass を実行できるよう reusable script をインストールする。

現在サーバーが公開している MCP tool は `kb_write_note`、`kb_search_notes` です。Vault/graph counter は REST `GET /metrics` endpoint で提供します。

## Vault Structure

`KB_VAULT_PATH` が指す vault は単なるフォルダの集まりではなく、write skill（`kb_write_note`）が一定のルールで埋めていくグラフです。本セクションでは、write skill が各フォルダに何を記録し、AI がそれをどう再発見するかを説明します。

### Folder Tree

```text
KB_VAULT_PATH/
├── SCHEMA.md        # vault の規約、ページ閾値、tag taxonomy
├── index.md         # synthesized ページのナビゲーションカタログ
├── log.md           # append-only の変更監査ログ
├── raw/             # 変更不可の原本素材と添付 (raw/assets/)
├── entities/        # 人物、組織、製品、モデル、プロジェクト、標準、API
├── concepts/        # アイデア、手法、メカニズム、トピック、原則
├── comparisons/     # 並列比較の分析と意思決定記録
└── queries/         # 保存する価値のある回答済みの質問 / 調査結果
```

`raw/` は素材で、`entities/`・`concepts/`・`comparisons/`・`queries/` は AI が所有する synthesized wiki ページです。

### 各フォルダに書き込まれる詳細内容

write skill は frontmatter の `type` 値で、ページがどのフォルダに入るかを決めます。

| フォルダ | `type` | 記録内容 | 使わない場合 |
| --- | --- | --- | --- |
| `entities/` | `entity` | 人物、企業、製品、モデル、プロジェクト、プロトコル、データセット、標準、API | 広いアイデアや手法 |
| `concepts/` | `concept` | 手法、原則、メカニズム、トピック、用語、繰り返すパターン | 抽象概念でない限り、名前付きの組織/製品 |
| `comparisons/` | `comparison` | トレードオフ分析、A-vs-B の意思決定、ランキング、マトリクス、移行の選択 | 単一物の単純な要約 |
| `queries/` | `query` | 再利用に値する、十分に回答された質問・調査・統合結果 | 些末な照会や一度きりのチャット回答 |
| `concepts/` または `queries/` | `summary` | 複数トピックを横断する概要・トピックマップ | より具体的に分類できるページ |

すべての synthesized ページは次のルールに従います:

- **Frontmatter:** `title`、`created`、`updated`、`type`、`tags`、`sources` は必須、`confidence`（high/medium/low）と `contested`（true/false）は任意。
- **本文の形:** `# タイトル` の後に `## Summary`、`## Key facts`、`## Relationships`、`## Open questions`、`## Sources` の順。
- **パス:** 小文字 kebab-case（`concepts/llm-wiki.md`、`entities/anthropic.md`）。
- **リンク:** ページ間は `[[wikilinks]]`、新規ページは可能なら outbound リンク 2 つ以上。
- **閾値:** entity/concept が 2 つ以上の source に現れるか、重要な 1 つの source の中心である場合のみページを作成。約 200 行を超えたら分割。

write skill は本文の後に provenance trailer（`<!-- kb-provenance: ... -->`）を自動で付け、意味のある write のたびに `index.md`（ナビゲーション）と `log.md`（監査ログ）を更新します。`raw/` の原本は immutable に保ち、修正・統合は wiki ページ側で行います。

### AI がこれを探索する方法

AI は vault をテキスト検索インデックスではなくグラフとして扱います。

1. `index.md` と直近の `log.md` で現在の地図と最近の変更をまず把握します。
2. `kb_search_notes` で複数の語（ユーザーの表現、同義語、エンティティ名、tag）を検索します。
3. `path_prefix`（`entities`、`concepts`、`comparisons`、`queries`、`raw`）で範囲を絞ります。
4. 関連ページの `[[wikilinks]]` をたどり、統合に影響しうる場合はリンク先ページも読みます。
5. confidence が高く、日付が新しく、source が複数あるページを優先し、低 confidence や contested のページは明示的に示します。
6. 答えが再利用可能な統合になったら `queries/` や `comparisons/` ページとして整理し、`index.md` と `log.md` を更新します。

`kb_search_notes` は完全なファイルではなく snippet を返すため、MCP-only mode では完全な現在の note body なしに既存 note を上書きしません。
