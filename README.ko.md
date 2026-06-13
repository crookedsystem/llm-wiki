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

기본적으로 setup은 prompt-time context hook을 먼저 설치합니다. Hook 설치가 켜져 있으면 Stop hook이 LLM 응답 전달을 방해할 수 있다고 경고하고 대문자 `Y` 또는 `N` 입력을 요구합니다. `Y`는 Stop hook을 설치하고, `N`은 context hook만 설치한 채 계속 진행하며, 잘못된 입력은 다시 묻고, non-interactive stdin/EOF에서는 설치 전에 중단합니다. `--dry-run`은 이 interactive prompt를 건너뛰고 dry-run 계획에 Stop hook을 포함하지 않습니다.

URL 결정 순서는 `--server-url` -> `LLM_WIKI_MCP_URL` -> `KB_HOST`/`KB_PORT`/`KB_MCP_PATH`입니다. Server name은 `--server-name` -> `LLM_WIKI_MCP_SERVER_NAME` -> agent 기본값 순서로 결정됩니다. 모든 hook 설치를 끄려면 `LLM_WIKI_INSTALL_HOOKS=false` 또는 `--no-hooks`를 사용합니다.

설정 후에는 agent session을 재시작해 MCP tool, skill, hook 설정을 다시 로드합니다.

## How to Work

### Hook이 동작하는 원리

Setup은 agent별 hook directory에 `llm-wiki-context-hook.sh`를 만듭니다. Stop hook prompt에 `Y`로 답한 경우에만 `llm-wiki-stop-hook.sh`를 만들고, Claude Code와 Codex는 선택된 hook entry를 `UserPromptSubmit`/`Stop` hook 설정에 병합합니다. Hermes/Hermess는 finalize 계열 hook에 직접 연결할 수 있도록 재사용 script를 설치합니다.

Context hook은 사용자 입력 시점에 `kb_search_notes`를 호출해 관련 wiki snippet을 model 앞에 붙입니다. 선택된 경우 Stop hook은 종료 직전에 wiki-worthy 지식만 판단해서 기록하라는 update pass를 요청합니다. Claude Code와 Codex는 한 번 `decision=block`으로 model을 재호출하고, `stop_hook_active=true`이면 다시 막지 않아 loop를 피합니다. Hook helper나 `uv`가 없으면 hook은 agent 실행을 방해하지 않도록 조용히 종료합니다.

### Agent가 skill을 사용하는 방식

Skill은 agent에게 다음을 지시합니다:

- 쓰기 전에 `kb_search_notes`로 기존 Markdown wiki page 검색
- 직접 파일 접근 또는 `kb_search_notes` snippet으로 `SCHEMA.md`, `index.md`, `log.md` 기준 orientation 수행
- 새 vault에 아직 `SCHEMA.md`가 없으면 skill에 포함된 schema, page type, index, log, provenance 가이드를 기준으로 초기화
- `kb_search_notes`는 전체 파일 읽기가 아니라 snippet 검색이므로, MCP-only mode에서는 complete current note body가 없으면 기존 note를 업데이트하지 않음
- `kb_write_note`를 통해 완전한 Markdown note 작성
- optimistic concurrency를 위해 반환된 `content_hash`를 다음 `if_hash`로 사용
- raw source는 immutable하게 유지하고 durable wiki 변경 시 `index.md`와 `log.md` 업데이트
- 설치된 hook command를 native hook, plugin, wrapper와 함께 사용: 사용자 input 시점에는 compact wiki context를 로드하고, setup에서 선택한 경우 agent 종료 시점에는 stop-time update pass 실행. Claude Code와 Codex는 동일한 `UserPromptSubmit`/`Stop` hook schema(in-loop `decision=block` 재프롬프트)를 공유하므로 선택된 경우 setup이 연결할 수 있습니다. Hermes/Hermess는 finalize 계열 session hook만 제공하므로, plugin/wrapper나 finalize hook에 연결해 out-of-loop update pass를 돌리도록 재사용 script를 설치합니다.

현재 서버가 노출하는 MCP tool은 `kb_write_note`, `kb_search_notes`입니다. Vault/graph counter는 REST `GET /metrics` endpoint로 제공합니다.

## Vault Structure

`KB_VAULT_PATH`가 가리키는 vault는 단순한 폴더 묶음이 아니라, write skill(`kb_write_note`)이 일정한 규칙으로 채우는 그래프입니다. 아래는 write skill이 어떤 폴더에 무엇을 기록하고, AI가 그것을 어떻게 다시 찾는지 정리한 것입니다.

### Folder Tree

```text
KB_VAULT_PATH/
├── SCHEMA.md        # vault 규칙, 페이지 임계값, 태그 taxonomy
├── index.md         # synthesized 페이지의 네비게이션 카탈로그
├── log.md           # append-only 변경 감사 로그
├── raw/             # 변경 불가한 원본 소스 자료와 첨부 (raw/assets/)
├── entities/        # 사람, 조직, 제품, 모델, 프로젝트, 표준, API
├── concepts/        # 아이디어, 기법, 메커니즘, 주제, 원칙
├── comparisons/     # 나란히 비교한 분석과 의사결정 기록
└── queries/         # 보존할 가치가 있는 답변된 질문 / 조사 결과
```

`raw/`는 소스 자료이고, `entities/`·`concepts/`·`comparisons/`·`queries/`는 AI가 소유하는 synthesized wiki 페이지입니다.

### 각 폴더에 작성되는 세부 내용

write skill은 frontmatter의 `type` 값으로 페이지가 어느 폴더에 들어갈지 결정합니다.

| 폴더 | `type` | 기록 내용 | 쓰지 않는 경우 |
| --- | --- | --- | --- |
| `entities/` | `entity` | 사람, 회사, 제품, 모델, 프로젝트, 프로토콜, 데이터셋, 표준, API | 넓은 아이디어나 기법 |
| `concepts/` | `concept` | 기법, 원칙, 메커니즘, 주제, 용어, 반복되는 패턴 | 추상 개념이 아닌 한 명명된 조직/제품 |
| `comparisons/` | `comparison` | 트레이드오프 분석, A-vs-B 의사결정, 랭킹, 매트릭스, 마이그레이션 선택 | 한 가지에 대한 단순 요약 |
| `queries/` | `query` | 재사용할 만한, 충실히 답변된 질문·조사·합성 결과 | 사소한 조회나 일회성 채팅 답변 |
| `concepts/` 또는 `queries/` | `summary` | 여러 주제를 가로지르는 개요·토픽 맵 | 더 구체적으로 분류 가능한 페이지 |

모든 synthesized 페이지는 다음 규칙을 따릅니다:

- **Frontmatter:** `title`, `created`, `updated`, `type`, `tags`, `sources`는 필수이며, `created`와 `updated`는 초까지 포함하고 끝에 `Z`가 붙은 UTC ISO datetime이어야 합니다(`YYYY-MM-DDTHH:MM:SSZ`). `confidence`(high/medium/low)와 `contested`(true/false)는 선택.
- **본문 형태:** `# 제목` 다음에 `## Summary`, `## Key facts`, `## Relationships`, `## Open questions`, `## Sources` 순서.
- **경로:** 소문자 kebab-case (`concepts/llm-wiki.md`, `entities/anthropic.md`).
- **링크:** 페이지 간에는 `[[wikilinks]]`, 새 페이지는 가능하면 outbound 링크 2개 이상.
- **임계값:** entity/concept가 2개 이상 소스에 나오거나 중요한 한 소스의 중심일 때만 페이지 생성. 약 200줄을 넘으면 하위 페이지로 분할.

write skill은 본문 뒤에 provenance trailer(`<!-- kb-provenance: ... -->`)를 자동으로 덧붙이고, 의미 있는 write마다 `index.md`(네비게이션)와 `log.md`(감사 로그)를 갱신합니다. `raw/`의 원본은 immutable로 유지하고, 수정·합성은 wiki 페이지 쪽에서 합니다.

### AI가 이걸 탐색하는 방식

AI는 vault를 텍스트 검색 인덱스가 아니라 그래프로 다룹니다.

1. `index.md`와 최근 `log.md`로 현재 지도와 최근 변경을 먼저 파악합니다.
2. `kb_search_notes`로 여러 용어(사용자 표현, 동의어, 엔티티 이름, 태그)를 검색합니다.
3. `path_prefix`(`entities`, `concepts`, `comparisons`, `queries`, `raw`)로 검색 범위를 좁힙니다.
4. 관련 페이지의 `[[wikilinks]]`를 따라가며, 합성에 영향을 줄 수 있으면 링크된 페이지까지 읽습니다.
5. confidence가 높고, 날짜가 최신이며, 소스가 여러 개인 페이지를 우선하고, 낮은 confidence나 contested 페이지는 명시적으로 드러냅니다.
6. 답이 재사용 가능한 합성이 되면 `queries/`나 `comparisons/` 페이지로 정리하고 `index.md`·`log.md`를 갱신합니다.

`kb_search_notes`는 전체 파일이 아니라 snippet을 반환하므로, MCP-only mode에서는 완전한 현재 note body 없이 기존 note를 덮어쓰지 않습니다.
