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
- 작성된 note의 provenance trailer
- `GET /metrics` REST endpoint에서 vault와 graph counter 통합 제공
- `kb_search_notes` MCP tool을 통한 LLM Wiki Markdown 검색

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

이 repository는 Hermes/Hermess, Claude Code, Codex에서 서버를 Obsidian/Markdown LLM Wiki bridge로 사용할 수 있도록 바로 복사 가능한 MCP snippet, 단일 canonical agent skill, setup script를 포함합니다.

예상 workflow는 다음과 같습니다:

1. `uv run llm-wiki`로 MCP 서버를 실행합니다.
2. agent를 `http://127.0.0.1:9999/mcp`에 연결합니다.
3. canonical `llm-wiki` skill을 설치해 agent가 wiki convention을 알 수 있게 합니다.
4. MCP tool과 skill이 다시 로드되도록 agent session을 재시작합니다.

### Agent integration용 추가 파일

| Agent | MCP snippet | Skill source | Setup script |
| --- | --- | --- | --- |
| Hermes/Hermess | `mcp/hermess.yaml` | `skills/llm-wiki/` | `scripts/setup-hermess.sh` |
| Claude Code | `mcp/claude.json` | `skills/llm-wiki/` | `scripts/setup-claude.sh` |
| Codex | `mcp/codex.toml` | `skills/llm-wiki/` | `scripts/setup-codex.sh` |

이 skill은 의도적으로 single-source 구조입니다. 모든 agent는 동일한 `skills/llm-wiki/SKILL.md`를 설치합니다. Agent별 차이는 setup script와 skill의 "Agent-specific MCP names" 섹션에만 있습니다.

### Hermes/Hermess 설정

```bash
scripts/setup-hermess.sh
```

수행 내용:

- `skills/llm-wiki/`를 `${HERMES_HOME:-~/.hermes}/skills/llm-wiki/`로 복사
- `hermes mcp add llm_wiki --url http://127.0.0.1:9999/mcp` 실행
- CLI를 사용할 수 있으면 `hermes mcp test llm_wiki` 실행

수동 설정 equivalent:

```yaml
mcp_servers:
  llm_wiki:
    url: "http://127.0.0.1:9999/mcp"
    timeout: 120
    connect_timeout: 30
```

설정 후 Hermes를 재시작하거나, 기존 session에서 가능하면 `/reload-mcp`를 사용하세요.

### Claude Code 설정

```bash
scripts/setup-claude.sh
```

수행 내용:

- `skills/llm-wiki/`를 `${CLAUDE_SKILLS_DIR:-~/.claude/skills}/llm-wiki/`로 복사
- `claude mcp add -s user --transport http llm-wiki http://127.0.0.1:9999/mcp` 실행
- CLI를 사용할 수 있으면 `claude mcp get llm-wiki` 실행

Project-scoped `.mcp.json` 수동 설정 equivalent:

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

Project-scoped `.mcp.json` server를 처음 열면 Claude가 승인 여부를 물을 수 있습니다.

### Codex 설정

```bash
scripts/setup-codex.sh
```

수행 내용:

- `skills/llm-wiki/`를 `${CODEX_SKILLS_DIR:-${CODEX_HOME:-~/.codex}/skills}/llm-wiki/`로 복사
- `${CODEX_CONFIG_PATH:-~/.codex/config.toml}`에 idempotent `llm-wiki` block 추가

수동 `~/.codex/config.toml` 설정 equivalent:

```toml
[mcp_servers.llm_wiki]
url = "http://127.0.0.1:9999/mcp"
startup_timeout_sec = 30
tool_timeout_sec = 120
default_tools_approval_mode = "prompt"
```

`config.toml` 또는 skill file을 변경한 뒤에는 Codex를 재시작하세요.

### Setup script option

모든 setup script는 다음 option을 지원합니다:

```bash
--dry-run                 # 파일 작성이나 agent config 변경 없이 실행할 작업 출력
--server-url URL          # 기본값: http://127.0.0.1:9999/mcp
--server-name NAME        # 기본값: Hermes/Codex는 llm_wiki, Claude는 llm-wiki
```

Claude는 `--scope local|user|project`도 지원합니다. Codex는 `--config /path/to/config.toml`도 지원합니다.

### Agent가 skill을 사용하는 방식

Skill은 agent에게 다음을 지시합니다:

- 쓰기 전에 `kb_search_notes`로 기존 Markdown wiki page 검색
- 직접 파일 접근 또는 `kb_search_notes` snippet으로 `SCHEMA.md`, `index.md`, `log.md` 기준 orientation 수행
- `kb_write_note`를 통해 완전한 Markdown note 작성
- optimistic concurrency를 위해 반환된 `content_hash`를 다음 `if_hash`로 사용
- raw source는 immutable하게 유지하고 durable wiki 변경 시 `index.md`와 `log.md` 업데이트

현재 서버가 노출하는 MCP tool은 `kb_write_note`, `kb_search_notes`입니다. Vault/graph counter는 REST `GET /metrics` endpoint로 제공합니다.

## 검증

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest --cov=src --cov-fail-under=80
```
