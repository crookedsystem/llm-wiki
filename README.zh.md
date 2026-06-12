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

## How to Start

### 配置 `.env`

```bash
uv sync --extra dev
cp .env.example .env
```

在 `.env` 中，至少设置 vault 路径和 MCP 服务器地址。

```env
KB_VAULT_PATH=/home/alice/Obsidian/LLM Wiki
KB_HOST=127.0.0.1
KB_PORT=9999
KB_MCP_PATH=/mcp
```

`KB_VAULT_PATH` 是真正存放 Markdown 知识文档的 vault root。它必须指向包含 `SCHEMA.md`、`index.md`、`log.md` 的文件夹，而不是 `llm-wiki/src` 或 Obsidian 的 `.obsidian/` 配置文件夹。

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

网络规则很简单。如果只在同一台机器上使用，保持 `KB_HOST=127.0.0.1` 即可。如果需要远程 agent 连接，请用 `KB_HOST=0.0.0.0` 或可达的 bind IP 启动服务器，并在 agent 配置中通过 `LLM_WIKI_MCP_URL=http://<服务器IP或域名>:9999/mcp` 或 `--server-url` 指定真实的连接 URL。`KB_HOST=0.0.0.0` 在同一机器 client 的 URL 中会被转换为 `127.0.0.1`，因此 remote 端需要 URL override。

Obsidian 不需要单独 connector，只需使用 **Open folder as vault** 打开与 `KB_VAULT_PATH` 相同的文件夹即可。建议把附件目录设为 `raw/assets/`，并保持 Wikilinks 启用。

### 启动 MCP 服务器

```bash
uv run llm-wiki
```

默认 endpoint 是 `http://127.0.0.1:9999/mcp`。服务器启动后可通过 `GET /health` 查看状态，MCP tool 暴露 `kb_search_notes`、`kb_write_note`。Vault/graph counter 通过 REST `GET /metrics` 查看。

### Hook setup 方法

在服务器开启的状态下，从另一个终端运行 setup entrypoint。

```bash
uv run python scripts/main.py                 # Hermes/Hermess、Claude Code、Codex 全部
uv run python scripts/main.py --agent claude  # 只安装特定 agent
uv run python scripts/main.py --agent codex --server-url http://127.0.0.1:9999/mcp
```

`scripts/main.py` 读取 `.env` 和 shell export 值，安装 skill、MCP config 和 hook command。如果相同 server name 或 URL 已存在，则不会覆盖已有的 MCP config。

默认情况下，setup 会先安装 prompt-time context hook。启用 hook 安装时，它会警告 Stop hook 可能影响 LLM response 的正常接收，并要求输入大写 `Y` 或 `N`：`Y` 安装 Stop hook，`N` 只安装 context hook 后继续，非法输入会重新询问，non-interactive stdin/EOF 会在安装前中止。`--dry-run` 会跳过这个 interactive prompt，并且不会把 Stop hook 放进 dry-run 计划。

URL 解析顺序为 `--server-url` -> `LLM_WIKI_MCP_URL` -> `KB_HOST`/`KB_PORT`/`KB_MCP_PATH`。Server name 按 `--server-name` -> `LLM_WIKI_MCP_SERVER_NAME` -> agent 默认值的顺序决定。若要关闭所有 hook 安装，使用 `LLM_WIKI_INSTALL_HOOKS=false` 或 `--no-hooks`。

设置完成后，重启 agent session 以重新加载 MCP tool、skill 和 hook 配置。

## How to Work

### Hook 的工作原理

Setup 会在各 agent 的 hook 目录中创建 `llm-wiki-context-hook.sh`。只有在 Stop hook prompt 中回答 `Y` 时才会创建 `llm-wiki-stop-hook.sh`，并为 Claude Code 和 Codex 将选中的 hook entry 合并到 `UserPromptSubmit`/`Stop` hook 配置中。对 Hermes/Hermess，它会安装可复用 script，便于接入 finalize 类 hook。

Context hook 在用户输入时调用 `kb_search_notes`，把相关 wiki snippet 附加到 model 前面。被选中时，Stop hook 会在结束前请求一次 update pass，要求 model 只判断并记录 wiki-worthy 的知识。Claude Code 和 Codex 通过一次 `decision=block` 重新调用 model，并在 `stop_hook_active=true` 时不再阻止，从而避免 loop。如果缺少 hook helper 或 `uv`，hook 会安静退出，不干扰 agent 运行。

### Agent 使用 skill 的方式

该 skill 会指示 agent：

- 写入前用 `kb_search_notes` 搜索已有 Markdown wiki page
- 通过直接文件访问或 `kb_search_notes` snippet，基于 `SCHEMA.md`、`index.md`、`log.md` 进行 orientation
- 当新 vault 还没有 `SCHEMA.md` 时，使用 skill 内置的 schema、page type、index、log 和 provenance 指南进行初始化
- 将 `kb_search_notes` 视为 snippet 搜索而非完整文件读取，因此在 MCP-only mode 下，如果没有完整的当前 note body，不更新已有 note
- 通过 `kb_write_note` 写入完整 Markdown note
- 使用返回的 `content_hash` 作为下一次 optimistic concurrency 的 `if_hash`
- 保持 raw source immutable，并在 durable wiki 变更时更新 `index.md` 与 `log.md`
- 将已安装的 hook command 与 native hook、plugin、wrapper 一起使用：用户输入时加载 compact wiki context，并在 setup 中选中时于 agent 结束时运行 stop-time update pass。Claude Code 和 Codex 共享同一套 `UserPromptSubmit`/`Stop` hook schema（in-loop `decision=block` 再提示），因此被选中时 setup 可以接好。Hermes/Hermess 只提供 finalize 类 session hook，因此 setup 会安装 reusable script，供你接入 plugin/wrapper 或 finalize hook 来运行 out-of-loop update pass。

当前服务器暴露的 MCP tool 是 `kb_write_note` 和 `kb_search_notes`。Vault/graph counter 通过 REST `GET /metrics` endpoint 提供。

## Vault Structure

`KB_VAULT_PATH` 指向的 vault 不只是一堆文件夹，而是 write skill（`kb_write_note`）按固定规则填充的图。本节说明 write skill 在每个文件夹写入什么，以及 AI 如何再次找到它。

### Folder Tree

```text
KB_VAULT_PATH/
├── SCHEMA.md        # vault 约定、页面阈值、tag taxonomy
├── index.md         # synthesized 页面的导航目录
├── log.md           # append-only 变更审计日志
├── raw/             # 不可变的原始素材与附件 (raw/assets/)
├── entities/        # 人物、组织、产品、模型、项目、标准、API
├── concepts/        # 想法、技术、机制、主题、原则
├── comparisons/     # 并排分析与决策记录
└── queries/         # 值得保留的已回答问题 / 调研结果
```

`raw/` 是素材；`entities/`、`concepts/`、`comparisons/`、`queries/` 是由 AI 拥有的 synthesized wiki 页面。

### 各文件夹写入的具体内容

write skill 用 frontmatter 的 `type` 值决定页面归属哪个文件夹。

| 文件夹 | `type` | 记录内容 | 不适用 |
| --- | --- | --- | --- |
| `entities/` | `entity` | 人物、公司、产品、模型、项目、协议、数据集、标准、API | 宽泛的想法或技术 |
| `concepts/` | `concept` | 技术、原则、机制、主题、术语、反复出现的模式 | 命名的组织/产品（除非页面讲的是抽象概念） |
| `comparisons/` | `comparison` | 权衡分析、A-vs-B 决策、排名、矩阵、迁移选择 | 对单一事物的简单总结 |
| `queries/` | `query` | 值得复用的、充分回答的问题、调查或综合结果 | 琐碎查询或一次性聊天回答 |
| `concepts/` 或 `queries/` | `summary` | 跨主题的概览与 topic map | 可以更具体分类的页面 |

每个 synthesized 页面都遵循以下规则：

- **Frontmatter:** `title`、`created`、`updated`、`type`、`tags`、`sources` 必填；`confidence`（high/medium/low）与 `contested`（true/false）可选。
- **正文结构:** `# 标题` 之后依次为 `## Summary`、`## Key facts`、`## Relationships`、`## Open questions`、`## Sources`。
- **路径:** 小写 kebab-case（`concepts/llm-wiki.md`、`entities/anthropic.md`）。
- **链接:** 页面间使用 `[[wikilinks]]`；新页面尽量有 2 个以上有用的 outbound 链接。
- **阈值:** 仅当 entity/concept 出现在 2 个以上 source，或是某个重要 source 的核心时才创建页面；超过约 200 行就拆分。

write skill 会在正文后自动追加 provenance trailer（`<!-- kb-provenance: ... -->`），并在每次有意义的写入时更新 `index.md`（导航）与 `log.md`（审计日志）。`raw/` 下的原始素材保持 immutable，修正与综合写在 wiki 页面里。

### AI 探索它的方式

AI 把 vault 当作图，而不只是文本搜索索引。

1. 先用 `index.md` 和最近的 `log.md` 了解当前地图和最新变更。
2. 用 `kb_search_notes` 以多个词搜索：用户的措辞、同义词、实体名、tag。
3. 用 `path_prefix`（`entities`、`concepts`、`comparisons`、`queries`、`raw`）缩小范围。
4. 沿相关页面的 `[[wikilinks]]` 跟进，当链接页面可能影响综合时一并阅读。
5. 优先 confidence 更高、日期更新、source 更多的页面；显式标出低 confidence 或 contested 页面。
6. 当答案成为可复用的综合时，归档为 `queries/` 或 `comparisons/` 页面并更新 `index.md` 和 `log.md`。

由于 `kb_search_notes` 返回 snippet 而非完整文件，在 MCP-only mode 下，AI 不会在没有完整当前 note body 的情况下覆盖已有 note。
