# Personal KB MCP

[English](README.md) | [한국어](README.ko.md) | [中文](README.zh.md) | [日本語](README.ja.md)

Git으로 관리되는 Obsidian/Markdown 지식 베이스를 위한 개인용 MCP 서버입니다.

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
- vault status, graph health, metrics snapshot
- `VectorIndex`와 `NullVectorIndex`를 통한 Vector DB 확장 지점

## 로컬 설정

```bash
uv sync --extra dev
cp .env.example .env
```

`.env`를 수정하세요. 특히 `KB_VAULT_PATH`를 설정해야 합니다.

## 실행

```bash
uv run personal-kb-mcp
```

Hermes MCP 설정 예시:

```yaml
mcp_servers:
  personal_kb:
    url: "http://127.0.0.1:9999/mcp"
```

## LLM Wiki workflow용 agent integration

이 repository는 Hermes/Hermess, Claude Code, Codex에서 서버를 Obsidian/Markdown LLM Wiki bridge로 사용할 수 있도록 바로 복사 가능한 MCP snippet, 단일 canonical agent skill, setup script를 포함합니다.

예상 workflow는 다음과 같습니다:

1. `uv run personal-kb-mcp`로 MCP 서버를 실행합니다.
2. agent를 `http://127.0.0.1:9999/mcp`에 연결합니다.
3. canonical `personal-kb-llm-wiki` skill을 설치해 agent가 wiki convention을 알 수 있게 합니다.
4. MCP tool과 skill이 다시 로드되도록 agent session을 재시작합니다.

### Agent integration용 추가 파일

| Agent | MCP snippet | Skill source | Setup script |
| --- | --- | --- | --- |
| Hermes/Hermess | `mcp/hermess.yaml` | `skills/personal-kb-llm-wiki/` | `scripts/setup-hermess.sh` |
| Claude Code | `mcp/claude.json` | `skills/personal-kb-llm-wiki/` | `scripts/setup-claude.sh` |
| Codex | `mcp/codex.toml` | `skills/personal-kb-llm-wiki/` | `scripts/setup-codex.sh` |

이 skill은 의도적으로 single-source 구조입니다. 모든 agent는 동일한 `skills/personal-kb-llm-wiki/SKILL.md`를 설치합니다. Agent별 차이는 setup script와 skill의 "Agent-specific MCP names" 섹션에만 있습니다.

### Hermes/Hermess 설정

```bash
scripts/setup-hermess.sh
```

수행 내용:

- `skills/personal-kb-llm-wiki/`를 `${HERMES_HOME:-~/.hermes}/skills/personal-kb-llm-wiki/`로 복사
- `hermes mcp add personal_kb --url http://127.0.0.1:9999/mcp` 실행
- CLI를 사용할 수 있으면 `hermes mcp test personal_kb` 실행

수동 설정 equivalent:

```yaml
mcp_servers:
  personal_kb:
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

- `skills/personal-kb-llm-wiki/`를 `${CLAUDE_SKILLS_DIR:-~/.claude/skills}/personal-kb-llm-wiki/`로 복사
- `claude mcp add -s user --transport http personal-kb http://127.0.0.1:9999/mcp` 실행
- CLI를 사용할 수 있으면 `claude mcp get personal-kb` 실행

Project-scoped `.mcp.json` 수동 설정 equivalent:

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

Project-scoped `.mcp.json` server를 처음 열면 Claude가 승인 여부를 물을 수 있습니다.

### Codex 설정

```bash
scripts/setup-codex.sh
```

수행 내용:

- `skills/personal-kb-llm-wiki/`를 `${CODEX_SKILLS_DIR:-${CODEX_HOME:-~/.codex}/skills}/personal-kb-llm-wiki/`로 복사
- `${CODEX_CONFIG_PATH:-~/.codex/config.toml}`에 idempotent `personal-kb-mcp` block 추가

수동 `~/.codex/config.toml` 설정 equivalent:

```toml
[mcp_servers.personal_kb]
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
--server-name NAME        # 기본값: Hermes/Codex는 personal_kb, Claude는 personal-kb
```

Claude는 `--scope local|user|project`도 지원합니다. Codex는 `--config /path/to/config.toml`도 지원합니다.

### Agent가 skill을 사용하는 방식

Skill은 agent에게 다음을 지시합니다:

- 쓰기 전에 MCP status/health tool 호출
- vault를 읽을 수 있으면 `SCHEMA.md`, `index.md`, `log.md`를 기준으로 orientation 수행
- `kb_write_note`를 통해 완전한 Markdown note 작성
- optimistic concurrency를 위해 반환된 `content_hash`를 다음 `if_hash`로 사용
- raw source는 immutable하게 유지하고 durable wiki 변경 시 `index.md`와 `log.md` 업데이트

현재 서버가 노출하는 MCP tool은 `kb_write_note`, `kb_vault_status`, `kb_graph_health`, `kb_metrics`입니다.

## 검증

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest --cov=personal_kb_mcp --cov-fail-under=80
```
