# LLM Wiki MCP

[English](README.md) | [한국어](README.ko.md) | [中文](README.zh.md) | [日本語](README.ja.md)

Git으로 관리되는 Obsidian/Markdown LLM Wiki vault를 위한 MCP 서버입니다.

## 현재 기능

- `127.0.0.1:9999/mcp`에서 Streamable HTTP MCP를 제공하는 FastAPI 앱
- `GET /health` 헬스 체크 엔드포인트
- FastAPI REST 오류는 `{code, message, timestamp}` JSON envelope 사용
- 설정된 vault 내부에서 안전한 Markdown note path 해석
- 단일 `WriteQueue`를 통한 직렬화된 쓰기
- 업데이트용 `if_hash` optimistic concurrency
- `atomic=True` batch write의 파일 rollback
- write 결과의 source hash, content hash, 선택적 git commit hash
- 작성된 synthesized/meta note의 provenance trailer
- `GET /metrics` REST endpoint에서 vault와 graph counter 통합 제공
- `kb_search_notes` MCP tool을 통한 LLM Wiki Markdown 검색
- `kb_wiki_context`를 통한 schema-first wiki 지도, link issue 후보, update suggestion 제공
- `kb_validate_vault`를 통한 vault schema 검증
- `kb_reconcile_taxonomy`를 통한 deterministic tag taxonomy reconciliation
- raw note metadata와 body-only sha256 check를 포함한 `kb_write_note` schema-enforced write

## 로컬 설정

```bash
uv sync --extra dev
cp .env.example .env
```

`.env`를 수정하세요. 특히 `KB_VAULT_PATH`를 설정해야 합니다.

### LLM Wiki vault 설정

`llm-wiki`에서는 두 폴더를 분리해서 생각해야 합니다.

`llm-wiki` repository는 프로그램 코드가 있는 Git repo입니다:

```text
/home/alice/projects/llm-wiki/
├── src/        # 서버 코드
├── tests/
├── scripts/
└── ...
```

`KB_VAULT_PATH`는 실제 지식 문서가 저장되는 Markdown vault입니다:

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

`.env`에서는 `KB_VAULT_PATH`를 두 번째 폴더로 지정하세요:

```env
KB_VAULT_PATH=/home/alice/Obsidian/LLM Wiki
KB_HOST=127.0.0.1
KB_PORT=9999
KB_MCP_PATH=/mcp
```

`KB_VAULT_PATH`를 `llm-wiki/src`나 Obsidian `.obsidian/` 설정 폴더로 지정하면 안 됩니다. `SCHEMA.md`, `index.md`, `log.md`가 들어있는 vault root를 가리켜야 합니다.

제일 중요한 구분은 이겁니다:

```text
llm-wiki repository의 src/     = 서버 코드
KB_VAULT_PATH의 raw/           = 원본 자료 저장소
KB_VAULT_PATH의 entities/...   = 정리된 위키 문서
```

Agent는 문서를 만들거나 수정하기 전에 `SCHEMA.md`, `index.md`, 최근 `log.md`를 먼저 읽어야 합니다.

### Obsidian 연결

별도 connector는 필요 없습니다. Obsidian에서 **Open folder as vault**로 `KB_VAULT_PATH`와 같은 폴더를 열면 됩니다. Obsidian과 MCP 서버가 같은 Markdown 파일을 읽고 씁니다.

권장 설정은 attachment folder를 `raw/assets/`로 지정하고, Wikilinks를 켜둔 상태로 유지하며, YAML frontmatter query가 필요하면 Dataview plugin을 설치하는 것입니다. Obsidian Sync를 쓴다면 이 동일한 vault 폴더를 동기화하세요.

## 실행

```bash
uv run llm-wiki
```

Hermes MCP 설정 예시:

```yaml
mcp_servers:
  llm_wiki:
    url: "http://127.0.0.1:9999/mcp"
```

## LLM Wiki workflow용 agent integration

이 repository는 Hermes/Hermess, Claude Code, Codex에서 서버를 Obsidian/Markdown LLM Wiki bridge로 사용할 수 있도록 바로 복사 가능한 MCP snippet, 단일 canonical agent skill, uv 기반 setup entrypoint를 포함합니다.

예상 workflow는 다음과 같습니다:

1. `.env.example`을 `.env`로 복사하고, 실행할 서버 기준으로 `KB_VAULT_PATH`, `KB_HOST`, `KB_PORT`, `KB_MCP_PATH`를 설정합니다.
2. `uv run llm-wiki`로 MCP 서버를 실행합니다.
3. Setup entrypoint를 실행합니다. 기본값은 지원하는 모든 agent를 설치하고, 일부만 설치하려면 `--agent`를 넘깁니다. 또한 같은 MCP server를 사용해 user input 시점 context loading과 stop-time wiki update pass를 실행하는 hook scaffold도 함께 설치합니다.
4. MCP tool, skill, native hook/plugin 설정이 다시 로드되도록 agent session을 재시작합니다.

### Agent integration용 파일

| Agent | MCP snippet | Skill source | 설치 명령 |
| --- | --- | --- | --- |
| Hermes/Hermess | `mcp/hermess.yaml` | `skills/llm-wiki/` | `uv run python scripts/main.py --agent hermes` |
| Claude Code | `mcp/claude.json` | `skills/llm-wiki/` | `uv run python scripts/main.py --agent claude` |
| Codex | `mcp/codex.toml` | `skills/llm-wiki/` | `uv run python scripts/main.py --agent codex` |

Setup entrypoint는 `scripts/main.py`입니다. `--agent` 없이 실행하면 Hermes/Hermess, Claude Code, Codex를 한 번에 설치합니다. 재사용 코드는 `scripts/setup_support/` 아래에 있고, env 로딩, MCP URL 결정, skill 복사, hook 설치, 중복 확인, Codex TOML 편집을 모든 agent가 같은 코드 경로로 사용합니다. Runtime hook helper는 `scripts/agent_hooks/llm_wiki_agent_hook.py`입니다.

Skill은 의도적으로 single-source 구조입니다. 모든 agent는 동일한 `skills/llm-wiki/SKILL.md`를 설치합니다. Agent별 차이는 setup code와 skill의 "Agent-specific MCP names" 섹션에만 있습니다.

### Setup entrypoint는 `.env`를 읽습니다

Setup entrypoint는 기본적으로 repository의 `.env`를 읽고, 이미 shell에 export된 값이 있으면 그 값이 `.env`보다 우선합니다. 다른 dotenv 파일을 쓰려면 `--env-file /path/to/file`을 넘기면 됩니다.

MCP URL 결정 순서:

1. `--server-url URL`
2. `LLM_WIKI_MCP_URL`
3. `LLM_WIKI_MCP_SCHEME` + `LLM_WIKI_MCP_HOST` 또는 `KB_HOST` + `KB_PORT` + `KB_MCP_PATH`

`KB_HOST=0.0.0.0`이면 agent client용 URL은 `127.0.0.1`로 변환합니다. 서버는 모든 interface에 bind할 수 있지만, 같은 머신의 agent는 보통 loopback으로 접속하는 것이 맞습니다.

MCP server name 결정 순서:

1. `--server-name NAME`
2. `LLM_WIKI_MCP_SERVER_NAME`
3. Agent 기본값: Hermes/Codex는 `llm_wiki`, Claude Code는 `llm-wiki`

Hook setup은 기본으로 켜져 있습니다. 끄려면 `LLM_WIKI_INSTALL_HOOKS=false`를 설정하거나 `--no-hooks`를 넘깁니다. 생성되는 hook script는 같은 helper를 두 mode로 실행합니다:

- user input: `kb_search_notes`를 query하고 model에 줄 compact `<llm-wiki-context>` block 출력
- stop/completion: model에게 마지막 MCP update pass를 요청해 durable fact/decision/procedure만 쓰고 content 변경 시 `index.md`/`log.md` 업데이트

Hook 위치는 `HERMES_LLM_WIKI_HOOKS_DIR`, `CLAUDE_HOOKS_DIR`, `CLAUDE_SETTINGS_PATH`, `CODEX_LLM_WIKI_HOOKS_DIR`, `CODEX_HOOKS_JSON_PATH`로 조정할 수 있습니다.

### 기존 MCP config는 덮어쓰지 않습니다

Setup은 server가 없을 때만 추가합니다:

- Claude Code: `claude mcp get <name>`과 `claude mcp list`를 확인한 뒤 `claude mcp add`를 실행합니다.
- Hermes/Hermess: `hermes mcp list`에서 같은 name 또는 URL이 있는지 확인한 뒤 `hermes mcp add`를 실행합니다.
- Codex: `${CODEX_CONFIG_PATH:-~/.codex/config.toml}`을 parse해서 같은 server name 또는 URL이 있으면 skip합니다.

이미 matching server가 있으면 skip 이유를 출력하고 기존 MCP config를 그대로 둡니다.

### Hermes/Hermess 설정

```bash
uv run python scripts/main.py --agent hermes
```

수행 내용:

- `skills/llm-wiki/`를 `${HERMES_HOME:-~/.hermes}/skills/llm-wiki/`로 복사
- 재사용 가능한 hook command를 `${HERMES_LLM_WIKI_HOOKS_DIR:-${HERMES_HOME:-~/.hermes}/hooks/llm-wiki}/` 아래에 설치
- `${LLM_WIKI_MCP_SERVER_NAME:-llm_wiki}`가 없을 때만 Hermes MCP config에 추가
- CLI를 사용할 수 있으면 `hermes mcp test <server-name>` 실행

설정 후 Hermes를 재시작하거나, 기존 session에서 가능하면 `/reload-mcp`를 사용하세요.

### Claude Code 설정

```bash
uv run python scripts/main.py --agent claude
```

수행 내용:

- `skills/llm-wiki/`를 `${CLAUDE_SKILLS_DIR:-~/.claude/skills}/llm-wiki/`로 복사
- `llm-wiki-context-hook.sh`, `llm-wiki-stop-hook.sh`를 `${CLAUDE_HOOKS_DIR:-~/.claude/hooks/llm-wiki}/` 아래에 설치
- Claude Code `UserPromptSubmit`, `Stop` hook entry를 `${CLAUDE_SETTINGS_PATH:-~/.claude/settings.json}`에 중복 없이 병합
- `${LLM_WIKI_MCP_SERVER_NAME:-llm-wiki}`가 없을 때만 `claude mcp add -s ${CLAUDE_MCP_SCOPE:-user} --transport http ...`로 추가
- CLI를 사용할 수 있으면 `claude mcp get <server-name>` 실행

Claude `UserPromptSubmit` hook은 model 시작 전에 wiki context를 출력합니다. `Stop` hook은 Claude가 종료하기 전에 MCP로 LLM Wiki를 업데이트하도록 한 번 block decision을 반환하며, follow-up stop event의 `stop_hook_active=true`에서는 다시 block하지 않아 무한 loop를 방지합니다.

Project-scoped `.mcp.json` server를 처음 열면 Claude가 승인 여부를 물을 수 있습니다.

### Codex 설정

```bash
uv run python scripts/main.py --agent codex
```

수행 내용:

- `skills/llm-wiki/`를 `${CODEX_SKILLS_DIR:-${CODEX_HOME:-~/.codex}/skills}/llm-wiki/`로 복사
- `llm-wiki-context-hook.sh`와 `llm-wiki-stop-hook.sh`를 `${CODEX_LLM_WIKI_HOOKS_DIR:-${CODEX_HOME:-~/.codex}/hooks/llm-wiki}/` 아래에 설치
- Codex `UserPromptSubmit`/`Stop` hook 엔트리를 중복 없이 `${CODEX_HOOKS_JSON_PATH:-~/.codex/hooks.json}`에 병합
- 같은 name 또는 URL이 없을 때만 `${CODEX_CONFIG_PATH:-~/.codex/config.toml}`에 새 `[mcp_servers.<name>]` block 추가

Codex(2026+)는 Claude Code와 동일한 hook JSON schema를 공유하므로, `Stop` hook도 종료 전에 LLM Wiki를 업데이트하라는 일회성 `decision=block`을 emit합니다. `stop_hook_active=true`가 되면 helper가 재차단을 건너뛰어 loop가 발생하지 않습니다. `config.toml`, `hooks.json`, 또는 skill file을 변경한 뒤에는 Codex를 재시작하세요.

### Setup entrypoint option

지원하는 모든 agent를 설치합니다:

```bash
uv run python scripts/main.py
```

일부 agent만 설치하려면 `--agent`를 한 번 이상 넘깁니다:

```bash
uv run python scripts/main.py --agent claude
uv run python scripts/main.py --agent claude --agent codex
```

Setup entrypoint는 다음 option을 지원합니다:

```bash
--agent {hermes,claude,codex}  # 반복 가능; 생략하면 모든 agent 설치
--dry-run                 # 파일 작성이나 agent config 변경 없이 실행할 작업 출력
--env-file PATH           # 기본값: repository .env
--server-url URL          # .env 기반 MCP URL 결정을 override
--server-name NAME        # 기본값: Hermes/Codex는 llm_wiki, Claude는 llm-wiki
--no-hooks                # input/stop hook scaffold 설치 skip
--claude-settings PATH    # hook을 병합할 Claude settings JSON
```

Claude는 `--scope local|user|project`도 지원합니다. Codex는 `--config /path/to/config.toml`도 지원합니다.

### Agent가 skill을 사용하는 방식

Skill은 agent에게 다음을 지시합니다:

- 쓰기 전에 `kb_search_notes`로 기존 Markdown wiki page를 검색합니다.
- 직접 파일 접근 또는 `kb_search_notes` snippet으로 `SCHEMA.md`, `index.md`, `log.md` 기준 orientation을 수행합니다.
- 새 vault에 아직 `SCHEMA.md`가 없으면 skill에 포함된 schema, page type, index, log, provenance 가이드를 기준으로 초기화합니다.
- `kb_search_notes`는 전체 파일 읽기가 아니라 snippet 검색으로 취급합니다. MCP-only mode에서는 complete current note body가 없으면 기존 note를 업데이트하지 않습니다.
- `kb_write_note`로 완전한 Markdown note를 작성합니다. 서버는 쓰기 전에 schema violation을 거부합니다.
- Wiki 작업은 `kb_wiki_context`로 시작해 allowed tag, page type, index, recent log, schema health를 drafting 전에 확인합니다.
- `kb_validate_vault`와 `kb_reconcile_taxonomy`를 deterministic schema hygiene 및 tag taxonomy repair에 사용합니다.
- optimistic concurrency를 위해 반환된 `content_hash`를 다음 `if_hash`로 사용합니다.
- raw source는 immutable하게 유지하고 durable wiki 변경 시 `index.md`와 `log.md`를 업데이트합니다.
- 설치된 hook command를 native hook, plugin, wrapper와 함께 사용: 사용자 input 시점에는 compact wiki context를 로드하고, agent 종료 시점에는 stop-time update pass 실행. Claude Code와 Codex는 동일한 `UserPromptSubmit`/`Stop` hook schema(in-loop `decision=block` 재프롬프트)를 공유하므로 setup이 자동으로 연결합니다. Hermes/Hermess는 finalize 계열 session hook만 제공하므로, plugin/wrapper나 finalize hook에 연결해 out-of-loop update pass를 돌리도록 재사용 script를 설치합니다.

현재 서버가 노출하는 MCP tool은 `kb_write_note`, `kb_search_notes`, `kb_wiki_context`, `kb_validate_vault`, `kb_reconcile_taxonomy`입니다. Vault/graph counter는 REST `GET /metrics` endpoint로 제공합니다.

## 검증

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest --cov=src --cov-fail-under=80
```
