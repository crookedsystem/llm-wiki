# Personal KB MCP

[English](README.md) | [한국어](README.ko.md) | [中文](README.zh.md) | [日本語](README.ja.md)

面向 Git 托管的 Obsidian/Markdown 知识库的私有 MCP 服务器。

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
- vault status、graph health 和 metrics snapshot
- 通过 `VectorIndex` 和 `NullVectorIndex` 提供 Vector DB 扩展点

## 本地设置

```bash
uv sync --extra dev
cp .env.example .env
```

编辑 `.env`，尤其是 `KB_VAULT_PATH`。

## 运行

```bash
uv run personal-kb-mcp
```

Hermes MCP 配置示例：

```yaml
mcp_servers:
  personal_kb:
    url: "http://127.0.0.1:9999/mcp"
```

## 用于 LLM Wiki workflow 的 agent integration

本 repository 包含可直接复制的 MCP snippet、一个 canonical agent skill，以及 setup script，用于让 Hermes/Hermess、Claude Code 和 Codex 将该服务器作为 Obsidian/Markdown LLM Wiki bridge 使用。

预期 workflow 如下：

1. 使用 `uv run personal-kb-mcp` 运行 MCP 服务器。
2. 将 agent 连接到 `http://127.0.0.1:9999/mcp`。
3. 安装 canonical `personal-kb-llm-wiki` skill，让 agent 了解 wiki convention。
4. 重启 agent session，使 MCP tool 和 skill 重新加载。

### 为 agent integration 添加的文件

| Agent | MCP snippet | Skill source | Setup script |
| --- | --- | --- | --- |
| Hermes/Hermess | `mcp/hermess.yaml` | `skills/personal-kb-llm-wiki/` | `scripts/setup-hermess.sh` |
| Claude Code | `mcp/claude.json` | `skills/personal-kb-llm-wiki/` | `scripts/setup-claude.sh` |
| Codex | `mcp/codex.toml` | `skills/personal-kb-llm-wiki/` | `scripts/setup-codex.sh` |

该 skill 有意保持 single-source：所有 agent 都安装同一个 `skills/personal-kb-llm-wiki/SKILL.md`。Agent-specific 差异只存在于 setup script，以及 skill 的 “Agent-specific MCP names” 部分。

### 设置 Hermes/Hermess

```bash
scripts/setup-hermess.sh
```

它会执行：

- 将 `skills/personal-kb-llm-wiki/` 复制到 `${HERMES_HOME:-~/.hermes}/skills/personal-kb-llm-wiki/`
- 运行 `hermes mcp add personal_kb --url http://127.0.0.1:9999/mcp`
- CLI 可用时运行 `hermes mcp test personal_kb`

手动 equivalent：

```yaml
mcp_servers:
  personal_kb:
    url: "http://127.0.0.1:9999/mcp"
    timeout: 120
    connect_timeout: 30
```

设置完成后，重启 Hermes；如果现有 session 支持，也可以使用 `/reload-mcp`。

### 设置 Claude Code

```bash
scripts/setup-claude.sh
```

它会执行：

- 将 `skills/personal-kb-llm-wiki/` 复制到 `${CLAUDE_SKILLS_DIR:-~/.claude/skills}/personal-kb-llm-wiki/`
- 运行 `claude mcp add -s user --transport http personal-kb http://127.0.0.1:9999/mcp`
- CLI 可用时运行 `claude mcp get personal-kb`

Project-scoped `.mcp.json` 手动 equivalent：

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

第一次在项目中看到 project-scoped `.mcp.json` server 时，Claude 可能会要求你批准。

### 设置 Codex

```bash
scripts/setup-codex.sh
```

它会执行：

- 将 `skills/personal-kb-llm-wiki/` 复制到 `${CODEX_SKILLS_DIR:-${CODEX_HOME:-~/.codex}/skills}/personal-kb-llm-wiki/`
- 向 `${CODEX_CONFIG_PATH:-~/.codex/config.toml}` 添加 idempotent `personal-kb-mcp` block

手动 `~/.codex/config.toml` equivalent：

```toml
[mcp_servers.personal_kb]
url = "http://127.0.0.1:9999/mcp"
startup_timeout_sec = 30
tool_timeout_sec = 120
default_tools_approval_mode = "prompt"
```

修改 `config.toml` 或 skill 文件后，请重启 Codex。

### Setup script option

所有 setup script 都支持：

```bash
--dry-run                 # 只打印将执行的操作，不写文件或修改 agent config
--server-url URL          # 默认值: http://127.0.0.1:9999/mcp
--server-name NAME        # 默认值: Hermes/Codex 为 personal_kb，Claude 为 personal-kb
```

Claude 还支持 `--scope local|user|project`。Codex 还支持 `--config /path/to/config.toml`。

### Agent 应如何使用该 skill

该 skill 会指示 agent：

- 写入前调用 MCP status/health tool。
- vault 可读时，先查看 `SCHEMA.md`、`index.md` 和 `log.md` 进行 orientation。
- 通过 `kb_write_note` 写入完整 Markdown note。
- 使用返回的 `content_hash` 作为下一次 optimistic concurrency 的 `if_hash`。
- 保持 raw source immutable，并在 durable wiki 变更时更新 `index.md` 与 `log.md`。

当前服务器暴露的 MCP tool 是 `kb_write_note`、`kb_vault_status`、`kb_graph_health` 和 `kb_metrics`。

## 验证

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest --cov=personal_kb_mcp --cov-fail-under=80
```
