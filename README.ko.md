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

## How to Start

### .env 설정

```bash
uv sync --extra dev
cp .env.example .env
```

`.env`에서 최소한 vault 경로와 MCP 서버 주소를 정합니다.

```env
KB_VAULT_PATH=/home/alice/Obsidian/LLM Wiki
KB_HOST=127.0.0.1
KB_PORT=9999
KB_MCP_PATH=/mcp
```

`KB_VAULT_PATH`는 실제 Markdown 지식 문서가 있는 vault root입니다. `llm-wiki/src`나 Obsidian `.obsidian/` 설정 폴더가 아니라, `SCHEMA.md`, `index.md`, `log.md`가 들어있는 폴더를 가리켜야 합니다.

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

네트워크 규칙은 단순합니다. 같은 머신에서만 쓰면 `KB_HOST=127.0.0.1`을 유지합니다. 원격 agent가 접속해야 하면 서버는 `KB_HOST=0.0.0.0` 또는 접근 가능한 bind IP로 띄우고, agent 설정에는 `LLM_WIKI_MCP_URL=http://<서버IP또는도메인>:9999/mcp` 또는 `--server-url`로 실제 접속 URL을 명시합니다. `KB_HOST=0.0.0.0`은 같은 머신 client용 URL로는 `127.0.0.1`로 변환되므로 remote에서는 URL override가 필요합니다.

Obsidian은 별도 connector 없이 **Open folder as vault**로 `KB_VAULT_PATH`와 같은 폴더를 열면 됩니다. 권장 설정은 attachment folder를 `raw/assets/`로 지정하고 Wikilinks를 켜두는 것입니다.

### MCP 서버 시작

```bash
uv run llm-wiki
```

기본 endpoint는 `http://127.0.0.1:9999/mcp`입니다. 서버가 뜬 뒤 `GET /health`로 상태를 확인할 수 있고, MCP tool은 `kb_search_notes`, `kb_write_note`를 노출합니다. Vault/graph counter는 REST `GET /metrics`에서 확인합니다.

### Hook setup 방법

서버를 켠 상태에서 다른 터미널에서 setup entrypoint를 실행합니다.

```bash
uv run python scripts/main.py                 # Hermes/Hermess, Claude Code, Codex 전체
uv run python scripts/main.py --agent claude  # 특정 agent만 설치
uv run python scripts/main.py --agent codex --server-url http://127.0.0.1:9999/mcp
```

`scripts/main.py`는 `.env`와 shell export 값을 읽어 skill, MCP config, hook command를 설치합니다. 같은 server name이나 URL이 이미 있으면 기존 MCP config를 덮어쓰지 않습니다.

URL 결정 순서는 `--server-url` -> `LLM_WIKI_MCP_URL` -> `KB_HOST`/`KB_PORT`/`KB_MCP_PATH`입니다. Server name은 `--server-name` -> `LLM_WIKI_MCP_SERVER_NAME` -> agent 기본값 순서로 결정됩니다. Hook 설치를 끄려면 `LLM_WIKI_INSTALL_HOOKS=false` 또는 `--no-hooks`를 사용합니다.

설정 후에는 agent session을 재시작해 MCP tool, skill, hook 설정을 다시 로드합니다.

## How to Work

### Hook이 동작하는 원리

Setup은 agent별 hook directory에 `llm-wiki-context-hook.sh`, `llm-wiki-stop-hook.sh`를 만들고, Claude Code와 Codex는 `UserPromptSubmit`/`Stop` hook 설정에 자동 병합합니다. Hermes/Hermess는 finalize 계열 hook에 직접 연결할 수 있도록 재사용 script를 설치합니다.

Context hook은 사용자 입력 시점에 `kb_search_notes`를 호출해 관련 wiki snippet을 model 앞에 붙입니다. Stop hook은 종료 직전에 wiki-worthy 지식만 판단해서 기록하라는 update pass를 요청합니다. Claude Code와 Codex는 한 번 `decision=block`으로 model을 재호출하고, `stop_hook_active=true`이면 다시 막지 않아 loop를 피합니다. Hook helper나 `uv`가 없으면 hook은 agent 실행을 방해하지 않도록 조용히 종료합니다.

### Agent가 skill을 사용하는 방식

Skill은 agent에게 다음을 지시합니다:

- 쓰기 전에 `kb_search_notes`로 기존 Markdown wiki page 검색
- 직접 파일 접근 또는 `kb_search_notes` snippet으로 `SCHEMA.md`, `index.md`, `log.md` 기준 orientation 수행
- 새 vault에 아직 `SCHEMA.md`가 없으면 skill에 포함된 schema, page type, index, log, provenance 가이드를 기준으로 초기화
- `kb_search_notes`는 전체 파일 읽기가 아니라 snippet 검색이므로, MCP-only mode에서는 complete current note body가 없으면 기존 note를 업데이트하지 않음
- `kb_write_note`를 통해 완전한 Markdown note 작성
- optimistic concurrency를 위해 반환된 `content_hash`를 다음 `if_hash`로 사용
- raw source는 immutable하게 유지하고 durable wiki 변경 시 `index.md`와 `log.md` 업데이트
- 설치된 hook command를 native hook, plugin, wrapper와 함께 사용: 사용자 input 시점에는 compact wiki context를 로드하고, agent 종료 시점에는 stop-time update pass 실행. Claude Code와 Codex는 동일한 `UserPromptSubmit`/`Stop` hook schema(in-loop `decision=block` 재프롬프트)를 공유하므로 setup이 자동으로 연결합니다. Hermes/Hermess는 finalize 계열 session hook만 제공하므로, plugin/wrapper나 finalize hook에 연결해 out-of-loop update pass를 돌리도록 재사용 script를 설치합니다.

현재 서버가 노출하는 MCP tool은 `kb_write_note`, `kb_search_notes`입니다. Vault/graph counter는 REST `GET /metrics` endpoint로 제공합니다.

## 검증

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest --cov=src --cov-fail-under=80
```
