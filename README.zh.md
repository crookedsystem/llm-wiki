# LLM Wiki MCP

[English](README.md) | [한국어](README.ko.md) | [中文](README.zh.md) | [日本語](README.ja.md)

面向 Git 托管的 Obsidian/Markdown LLM Wiki vault 的 MCP 服务器。

## 当前功能

- FastAPI 应用在 `127.0.0.1:9999/mcp` 提供 Streamable HTTP MCP
- `GET /health` 健康检查端点
- FastAPI REST 错误使用 `{code, message, timestamp}` JSON envelope
- 在已配置的 vault 内安全解析 Markdown note path
- 通过单个 `WriteQueue` 串行化写入
- 用于更新的 `if_hash` optimistic concurrency
- `atomic=True` batch write 的文件 rollback
- write 结果中的 source hash、content hash，以及可选的 git commit hash
- 写入 note 的 provenance trailer
- 通过 `GET /metrics` REST endpoint 合并提供 vault 与 graph counters
- 通过 `kb_search_notes` MCP tool 搜索 LLM Wiki Markdown

## 本地设置

```bash
uv sync --extra dev
cp .env.example .env
```

编辑 `.env`，尤其是 `KB_VAULT_PATH`。

### 配置 LLM Wiki vault

使用 `llm-wiki` 时，请把两个文件夹分开理解。

`llm-wiki` repository 是程序代码所在的 Git repo：

```text
/home/alice/projects/llm-wiki/
├── src/        # server code
├── tests/
├── scripts/
└── ...
```

`KB_VAULT_PATH` 是真正存放知识文档的 Markdown vault：

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

在 `.env` 中，把 `KB_VAULT_PATH` 指向第二个文件夹：

```env
KB_VAULT_PATH=/home/alice/Obsidian/LLM Wiki
KB_HOST=127.0.0.1
KB_PORT=9999
KB_MCP_PATH=/mcp
```

不要把 `KB_VAULT_PATH` 设置为 `llm-wiki/src`，也不要设置为 Obsidian 的 `.obsidian/` 配置文件夹。它必须指向包含 `SCHEMA.md`、`index.md` 和 `log.md` 的 vault root。

最重要的区别是：

```text
llm-wiki repository 的 src/    = server code
KB_VAULT_PATH 的 raw/          = original/source material
KB_VAULT_PATH 的 entities/...  = synthesized wiki pages
```

Agent 在创建或更新文档之前，应先读取 `SCHEMA.md`、`index.md` 和最近的 `log.md`。

### 连接 Obsidian

不需要单独 connector。在 Obsidian 中使用 **Open folder as vault**，打开与 `KB_VAULT_PATH` 相同的文件夹即可。Obsidian 和 MCP server 读取、写入同一组 Markdown 文件。

建议把附件目录设为 `raw/assets/`，保持 Wikilinks 启用；如果需要 YAML frontmatter 查询，安装 Dataview plugin。如果使用 Obsidian Sync，请同步同一个 vault 文件夹。

## 运行

```bash
uv run llm-wiki
```

Hermes MCP 配置示例：

```yaml
mcp_servers:
  llm_wiki:
    url: "http://127.0.0.1:9999/mcp"
```

## 用于 LLM Wiki workflow 的 agent integration

本 repository 包含可直接复制的 MCP snippet、一个 canonical agent skill，以及基于 uv 的 setup entrypoint，用于让 Hermes/Hermess、Claude Code 和 Codex 将该服务器作为 Obsidian/Markdown LLM Wiki bridge 使用。

预期 workflow 如下：

1. 将 `.env.example` 复制为 `.env`，并为要运行的服务器设置 `KB_VAULT_PATH`、`KB_HOST`、`KB_PORT` 和 `KB_MCP_PATH`。
2. 使用 `uv run llm-wiki` 运行 MCP 服务器。
3. 运行 setup entrypoint。默认会安装所有支持的 agent；如只安装部分 agent，请传入 `--agent`。它也会安装 hook scaffold，让 user input 时的 context loading 与 stop-time wiki update pass 使用同一个 MCP server。
4. 重启 agent session，使 MCP tool、skill 和 native hook/plugin 配置重新加载。

### Agent integration 文件

| Agent | MCP snippet | Skill source | Install command |
| --- | --- | --- | --- |
| Hermes/Hermess | `mcp/hermess.yaml` | `skills/llm-wiki/` | `uv run python scripts/main.py --agent hermes` |
| Claude Code | `mcp/claude.json` | `skills/llm-wiki/` | `uv run python scripts/main.py --agent claude` |
| Codex | `mcp/codex.toml` | `skills/llm-wiki/` | `uv run python scripts/main.py --agent codex` |

Setup entrypoint 是 `scripts/main.py`。不传 `--agent` 运行时，会一次安装 Hermes/Hermess、Claude Code 和 Codex。可复用代码位于 `scripts/setup_support/`，因此 env 读取、MCP URL 解析、skill 复制、hook 安装、重复检查和 Codex TOML 编辑都走同一套代码。Runtime hook helper 位于 `scripts/agent_hooks/llm_wiki_agent_hook.py`。

该 skill 有意保持 single-source：所有 agent 都安装同一个 `skills/llm-wiki/SKILL.md`。Agent-specific 差异只存在于 setup code，以及 skill 的 “Agent-specific MCP names” 部分。

### Setup entrypoint 会读取 `.env`

Setup entrypoint 默认读取 repository 的 `.env`，并允许已 export 的 shell 变量覆盖 `.env`。如果要使用其他 dotenv 文件，请传入 `--env-file /path/to/file`。

MCP URL 解析顺序：

1. `--server-url URL`
2. `LLM_WIKI_MCP_URL`
3. `LLM_WIKI_MCP_SCHEME` + `LLM_WIKI_MCP_HOST` 或 `KB_HOST` + `KB_PORT` + `KB_MCP_PATH`

如果 `KB_HOST=0.0.0.0`，setup 会为本机 agent client 转换为 `127.0.0.1`。服务器可以绑定所有 interface，但同一机器上的 agent 通常应通过 loopback 连接。

MCP server name 解析顺序：

1. `--server-name NAME`
2. `LLM_WIKI_MCP_SERVER_NAME`
3. Agent 默认值：Hermes/Codex 为 `llm_wiki`，Claude Code 为 `llm-wiki`

Hook setup 默认启用。若要禁用，请设置 `LLM_WIKI_INSTALL_HOOKS=false` 或传入 `--no-hooks`。生成的 hook script 使用同一个 helper 的两种 mode：

- user input：查询 `kb_search_notes`，并输出给 model 的 compact `<llm-wiki-context>` block
- stop/completion：要求 model 执行最后一次 MCP update pass，只写入 durable fact/decision/procedure，并在 content 变化时更新 `index.md`/`log.md`

Hook 位置可通过 `HERMES_LLM_WIKI_HOOKS_DIR`、`CLAUDE_HOOKS_DIR`、`CLAUDE_SETTINGS_PATH`、`CODEX_LLM_WIKI_HOOKS_DIR` 配置。

### 不覆盖已有 MCP config

Setup 只在 server 缺失时添加：

- Claude Code：先检查 `claude mcp get <name>` 和 `claude mcp list`，再运行 `claude mcp add`。
- Hermes/Hermess：先在 `hermes mcp list` 中检查相同 name 或 URL，再运行 `hermes mcp add`。
- Codex：解析 `${CODEX_CONFIG_PATH:-~/.codex/config.toml}`，如果相同 server name 或 URL 已存在则跳过。

如果找到匹配 server，setup 会打印跳过原因，并保持已有 MCP config 不变。

### 设置 Hermes/Hermess

```bash
uv run python scripts/main.py --agent hermes
```

它会执行：

- 将 `skills/llm-wiki/` 复制到 `${HERMES_HOME:-~/.hermes}/skills/llm-wiki/`
- 将 reusable hook command 安装到 `${HERMES_LLM_WIKI_HOOKS_DIR:-${HERMES_HOME:-~/.hermes}/hooks/llm-wiki}/`
- 仅当 `${LLM_WIKI_MCP_SERVER_NAME:-llm_wiki}` 缺失时添加到 Hermes MCP config
- CLI 可用时运行 `hermes mcp test <server-name>`

设置完成后，重启 Hermes；如果现有 session 支持，也可以使用 `/reload-mcp`。

### 设置 Claude Code

```bash
uv run python scripts/main.py --agent claude
```

它会执行：

- 将 `skills/llm-wiki/` 复制到 `${CLAUDE_SKILLS_DIR:-~/.claude/skills}/llm-wiki/`
- 将 `llm-wiki-context-hook.sh` 和 `llm-wiki-stop-hook.sh` 安装到 `${CLAUDE_HOOKS_DIR:-~/.claude/hooks/llm-wiki}/`
- 将 Claude Code `UserPromptSubmit` 与 `Stop` hook entry 合并到 `${CLAUDE_SETTINGS_PATH:-~/.claude/settings.json}`，且不重复添加
- 仅当 `${LLM_WIKI_MCP_SERVER_NAME:-llm-wiki}` 缺失时，通过 `claude mcp add -s ${CLAUDE_MCP_SCOPE:-user} --transport http ...` 添加
- CLI 可用时运行 `claude mcp get <server-name>`

Claude `UserPromptSubmit` hook 会在 model 开始前输出 wiki context。`Stop` hook 会返回一次 block decision，要求 Claude 在结束前通过 MCP 更新 LLM Wiki；后续 stop event 的 `stop_hook_active=true` 不会再次 block，因此不会无限循环。

第一次在项目中看到 project-scoped `.mcp.json` server 时，Claude 可能会要求你批准。

### 设置 Codex

```bash
uv run python scripts/main.py --agent codex
```

它会执行：

- 将 `skills/llm-wiki/` 复制到 `${CODEX_SKILLS_DIR:-${CODEX_HOME:-~/.codex}/skills}/llm-wiki/`
- 将 reusable hook command 安装到 `${CODEX_LLM_WIKI_HOOKS_DIR:-${CODEX_HOME:-~/.codex}/hooks/llm-wiki}/`
- 仅当相同 name 或 URL 不存在时，向 `${CODEX_CONFIG_PATH:-~/.codex/config.toml}` 追加新的 `[mcp_servers.<name>]` block

修改 `config.toml` 或 skill 文件后，请重启 Codex。

### Setup entrypoint option

安装所有支持的 agent：

```bash
uv run python scripts/main.py
```

只安装部分 agent 时，请传入一次或多次 `--agent`：

```bash
uv run python scripts/main.py --agent claude
uv run python scripts/main.py --agent claude --agent codex
```

Setup entrypoint 支持：

```bash
--agent {hermes,claude,codex}  # 可重复；省略则安装所有 agent
--dry-run                 # 只打印将执行的操作，不写文件或修改 agent config
--env-file PATH           # 默认值: repository .env
--server-url URL          # override .env MCP URL resolution
--server-name NAME        # 默认值: Hermes/Codex 为 llm_wiki，Claude 为 llm-wiki
--no-hooks                # 跳过 input/stop hook scaffold 安装
--claude-settings PATH    # 要合并 hook 的 Claude settings JSON
```

Claude 还支持 `--scope local|user|project`。Codex 还支持 `--config /path/to/config.toml`。

### Agent 应如何使用该 skill

该 skill 会指示 agent：

- 写入前使用 `kb_search_notes` 搜索已有 Markdown wiki page。
- 通过直接文件访问或 `kb_search_notes` snippet，基于 `SCHEMA.md`、`index.md` 和 `log.md` 进行 orientation。
- 当新 vault 还没有 `SCHEMA.md` 时，使用 skill 内置的 schema、page type、index、log 和 provenance 指南进行初始化。
- 将 `kb_search_notes` 视为 snippet 搜索，而不是完整文件读取；在 MCP-only mode 下，如果没有完整的当前 note body，不要更新已有 note。
- 通过 `kb_write_note` 写入完整 Markdown note。
- 使用返回的 `content_hash` 作为下一次 optimistic concurrency 的 `if_hash`。
- 保持 raw source immutable，并在 durable wiki 变更时更新 `index.md` 与 `log.md`。
- 使用已安装的 hook command，并通过 native hook、plugin 或 wrapper 接入：用户输入时加载 compact wiki context，agent 结束时运行 stop-time update pass。Claude Code 由 setup 自动接好；Hermes/Hermess 和 Codex 不共享 Claude 的 JSON hook schema，因此 setup 会安装 reusable script。

当前服务器暴露的 MCP tool 是 `kb_write_note` 和 `kb_search_notes`。Vault/graph counters 通过 REST `GET /metrics` endpoint 暴露。

## 验证

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest --cov=src --cov-fail-under=80
```
