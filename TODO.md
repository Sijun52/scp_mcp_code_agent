# SCP MCP Code Agent - TODO

## Project Overview
OpenAPI 스펙을 기반으로 MCP 서버 코드를 자동 생성하는 LangChain 에이전트.

```
Chainlit UI → LangChain Agent (create_agent)
                 ├── OpenAPI MCP  → OpenAPI 스펙 조회
                 ├── Filesystem MCP → 예시 코드 읽기 / 생성 코드 저장
                 ├── run_ruff_check → Lint 검증
                 └── run_pytest     → 테스트 검증
```

---

## Phase 1: Foundation ✅

### 프로젝트 기반
- [x] 프로젝트 구조 설계 (`src/scp_mcp_code_agent/`, `tests/`, `mcp_code_example/`)
- [x] `pyproject.toml` 구성 (uv + hatchling + ruff + pytest + langgraph)
- [x] `.env.example` 환경 변수 정의
- [x] `README.md` 작성

### 에이전트 코어
- [x] `agent.py` — `langchain.agents.create_agent` 기반 에이전트 팩토리
- [x] `mcp_client.py` — `MultiServerMCPClient` 설정 (filesystem + openapi 서버)
- [x] `config.py` — `pydantic-settings` 기반 환경변수 로딩 (`.env`)
- [x] `prompts/system_prompt.py` — 경로 기반 프롬프트 (파일 내용 비주입, 에이전트가 MCP로 직접 읽음)

### 도구
- [x] `tools/code_runner.py` — `run_pytest`, `run_ruff_check`, `run_ruff_format_check` (LangChain `@tool`)
- [x] `mcp_servers/filesystem_server.py` — 자체 구현 Filesystem MCP 서버 (FastMCP)

### UI
- [x] `src/scp_mcp_code_agent/app.py` — Chainlit 앱 (세션별 에이전트 인스턴스, 대화 히스토리 유지)

### 템플릿
- [x] `mcp_code_example/server.py` — Virtual Server MCP 서버 예시 (에이전트 코드 스타일 레퍼런스)
- [x] `mcp_code_example/tests/test_server.py` — 예시 테스트 코드 (에이전트 테스트 스타일 레퍼런스)

### 테스트 코드
- [x] `tests/test_tools.py` — code_runner 도구 단위 테스트 (subprocess mock)
- [x] `tests/test_agent.py` — 시스템 프롬프트 / MCP 클라이언트 설정 테스트

### 기술 결정 (ADR)
- [x] ADR-001: pytest/ruff는 MCP 아닌 커스텀 LangChain 도구로 구현
- [x] ADR-002: Filesystem MCP 서버 자체 구현 (Python, Node.js 불필요)
- [x] ADR-003: LLM = OpenAI `gpt-4o` (ChatOpenAI)
- [x] ADR-004: 생성 코드 저장 위치 = `./generated/<service_name>_mcp_server/`
- [x] ADR-005: 예시 코드는 프롬프트에 주입하지 않고 에이전트가 Filesystem MCP로 직접 읽음

---

## Phase 2: 검증 🔲

- [ ] `uv sync --all-extras` 후 패키지 설치 확인
- [ ] `uv run pytest tests/ -v` — 단위 테스트 전체 통과 확인
- [ ] `uv run ruff check src/ tests/` — lint 통과 확인
- [ ] `mcp_code_example/tests/` 테스트 통과 확인 (예시 코드 자체 검증)
- [ ] Chainlit 앱 실행 후 E2E 시나리오 수동 검증
  - [ ] "virtual server" 입력 → 코드 생성 → lint 통과 → 테스트 통과

---

## Phase 3: 기능 개선 🔲

- [ ] 생성된 서버에 `pyproject.toml` 자동 포함 (독립 실행 가능한 패키지로 생성)
- [ ] Chainlit Step 세분화 (스펙 조회 / 코드 생성 / lint / 테스트 단계별 표시)
- [ ] 생성 히스토리 로깅 (생성된 파일 경로 목록 기록)
- [ ] 멀티 서비스 동시 생성 지원

---

## Phase 4: 프로덕션 🔲

- [ ] OpenAPI MCP 서버 구현 (현재 외부 서버 assume 상태)
  - `get_openapi_spec(service_name: str)` 툴 노출
  - SCP 플랫폼 API 연동
- [ ] Docker 컨테이너화
- [ ] 생성된 MCP 서버 자동 배포 파이프라인

---

## Architecture Decision Records

### ADR-001: 테스트/Lint 실행 방식
- **결정**: `subprocess` 래핑 커스텀 LangChain `@tool` 사용
- **이유**: pytest/ruff는 로컬 프로세스 실행 — MCP 오버헤드 불필요. 에이전트가 exit code로 성공/실패 판단 후 자동 수정 루프 진입.

### ADR-002: Filesystem MCP 서버
- **결정**: `mcp_servers/filesystem_server.py` 자체 구현 (FastMCP)
- **이유**: 공식 MCP filesystem 서버는 Node.js 기반 — Python만으로 의존성 완결.

### ADR-003: LLM
- **결정**: OpenAI `gpt-4o` (`ChatOpenAI`), `.env`의 `LLM_MODEL`로 변경 가능
- **이유**: 사용자 요구사항. `langchain-openai` 패키지 사용.

### ADR-004: 생성 코드 저장 위치
- **결정**: `./generated/<service_name_snake_case>_mcp_server/`
- **이유**: 프로젝트 루트 오염 방지, 서비스별 독립 디렉토리.

### ADR-005: 예시 코드 참조 방식
- **결정**: 시스템 프롬프트에 파일 내용 비주입 — 경로만 제공, 에이전트가 Filesystem MCP로 직접 읽음
- **이유**: 프롬프트 토큰 낭비 방지. 에이전트가 필요한 파일만 선택적으로 읽고 최신 상태를 반영.
