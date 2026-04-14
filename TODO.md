# SCP MCP Code Agent - TODO

## Project Overview
OpenAPI 스펙을 기반으로 MCP 서버 코드를 자동 생성하는 LangChain 에이전트.

```
Chainlit UI → LangChain Agent (create_agent)
                 ├── OpenAPI MCP  → 엔드포인트 목록 조회 / 선택된 스펙 상세 조회 (2단계)
                 ├── Filesystem MCP → 예시 코드 읽기 / 생성 코드 저장
                 ├── Docs MCP     → SCP 상품 문서 검색 (선택)
                 ├── run_ruff_all  → Lint + 포맷 동시 검증
                 └── run_pytest    → 테스트 검증

HITL 흐름:
  Scenario 0: gather_requirements   — 코드 생성 전 요구사항 수집 (텍스트 질의)
  Scenario 1: openapi_confirm       — 스펙 확인 후 사용자 승인
  Scenario 2+3: write_file_confirm  — 코드 프리뷰 + 덮어쓰기 경고
  Scenario 4: confirm_endpoint_plan — 엔드포인트 계획 승인
  Scenario 5: test_failure          — pytest 반복 실패 시 판단 위임
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
- [x] `mcp_client.py` — `MultiServerMCPClient` 설정 (filesystem + openapi + docs 서버)
- [x] `config.py` — `pydantic-settings` 기반 환경변수 로딩 (LLM temperature 등 튜닝 파라미터는 코드에서 관리)
- [x] `prompts/system_prompt.py` — 경로 기반 프롬프트 (파일 내용 비주입, docs 연결 여부에 따라 동적 구성)

### 도구
- [x] `tools/code_runner.py` — `run_pytest`, `run_ruff_check`, `run_ruff_all` (async, `asyncio.gather` 병렬)
- [x] `tools/planning.py` — `gather_requirements`, `confirm_endpoint_plan`, `set_output_directory`
- [x] `mcp_servers/filesystem_server.py` — 자체 구현 Filesystem MCP 서버 (`read_multiple_files` 포함)

### 예시 코드 관리
- [x] `mcp_code_example/MANIFEST.json` — 예시 프로젝트 인덱스 (tags/characteristics 기반 best-match 선택)
- [x] `prompts/system_prompt.py` Step 1 — MANIFEST 읽기 → best-match 선택 → `read_multiple_files` 배치 읽기

### HITL 미들웨어
- [x] `middleware/gather_requirements.py` — Scenario 0: 코드 생성 전 요구사항 수집 (텍스트 질의)
- [x] `middleware/openapi_confirm.py` — Scenario 1: 스펙 조회 후 사용자 확인
- [x] `middleware/write_file_confirm.py` — Scenario 2+3: 코드 프리뷰 + 덮어쓰기 경고
- [x] `middleware/test_failure.py` — Scenario 5: pytest 반복 실패 시 사용자 판단 위임
- [x] `HumanInTheLoopMiddleware` — Scenario 4: 엔드포인트 계획 승인 (LangChain 내장)
- [x] `ModelRetryMiddleware`, `ToolRetryMiddleware`, `ModelCallLimitMiddleware`, `SummarizationMiddleware` 적용

### UI
- [x] `src/scp_mcp_code_agent/app.py` — Chainlit 앱 (세션별 에이전트 인스턴스, HITL interrupt/resume 루프)

### 템플릿
- [x] `mcp_code_example/server.py` — Virtual Server MCP 예시 (`Annotated+Field` 리치 프롬프트 스타일)
- [x] `mcp_code_example/tests/test_server.py` — 예시 테스트 코드 (에이전트 테스트 스타일 레퍼런스)

### 테스트 코드
- [x] `tests/test_tools.py` — code_runner 도구 단위 테스트
- [x] `tests/test_agent.py` — 시스템 프롬프트 / MCP 클라이언트 설정 테스트
- [x] `tests/test_filesystem_server.py`, `tests/test_callbacks.py`, `tests/test_planning.py`
- [x] `tests/test_middleware.py`, `tests/test_agent_helpers.py`, `tests/test_app.py`

### 배포
- [x] `Dockerfile` — 멀티스테이지 빌드 (uv builder → python runtime)
- [x] `docker-compose.yml` — volume 마운트로 생성 파일 로컬 저장

### 기술 결정 (ADR)
- [x] ADR-001: pytest/ruff는 MCP 아닌 커스텀 LangChain 도구로 구현
- [x] ADR-002: Filesystem MCP 서버 자체 구현 (Python, Node.js 불필요)
- [x] ADR-003: LLM = OpenAI `gpt-4o` (ChatOpenAI)
- [x] ADR-004: 생성 코드 저장 위치 = 기본 `~/scp-mcp-servers`, 대화로 변경 가능
- [x] ADR-005: 예시 코드는 프롬프트에 주입하지 않고 에이전트가 Filesystem MCP로 직접 읽음
- [x] ADR-006: Docs MCP는 선택 연결 — `DOCS_MCP_URL` 미설정 시 스펙만으로 동작
- [x] ADR-007: 생성 툴 파라미터는 `Annotated+Field` 스타일, docstring은 "Use this tool when / Workflow / Common scenarios" 구조 사용
- [x] ADR-008: 코드 생성 전 요구사항 수집 — `gather_requirements` 툴 + `GatherRequirementsMiddleware` (HITL 텍스트 질의)
- [x] ADR-009: OpenAPI 스펙 2단계 조회 — `get_openapi_spec_endpoints` → `get_openapi_spec_detail` (레거시 폴백 지원)

---

## Phase 2: 검증 🔲

- [ ] `uv sync --all-extras` 후 패키지 설치 확인
- [x] `uv run pytest tests/ -v` — 144개 테스트 통과
- [ ] `uv run ruff check src/ tests/` — lint 통과 확인
- [ ] `mcp_code_example/tests/` 테스트 통과 확인 (예시 코드 자체 검증)
- [ ] Chainlit 앱 실행 후 E2E 시나리오 수동 검증
  - [ ] "block storage" 입력 → 요구사항 수집 → 2단계 스펙 조회 → 코드 생성 → lint/테스트 통과
  - [ ] HITL 시나리오 동작 확인 (요구사항 수집 / 스펙 확인 / 계획 승인 / 파일 저장 확인)
  - [ ] `DOCS_MCP_URL` 설정 시 docs 검색 후 리치 docstring 생성 확인

---

## Phase 2.5: 성능 개선 ✅

### P0 — 즉시 적용 (비용·블로킹 직접 영향)

- [x] **[P0] async subprocess 전환** — `code_runner.py` → `asyncio.create_subprocess_exec()` 기반. pytest/ruff 실행 중 이벤트 루프 블로킹 제거

### P1 — 응답 속도 개선

- [x] **[P1] OpenAPI spec 응답 캐싱** — `_wrap_spec_tool_with_cache()` 래퍼, TTL 5분. 3개 spec 툴 모두 적용 (`get_openapi_spec`, `get_openapi_spec_endpoints`, `get_openapi_spec_detail`)
- [x] **[P1] 파일 읽기 배치** — `read_multiple_files` 툴. N번 `read_file` → 1번 MCP 호출로 단축
- [x] **[P1] ruff 병렬 실행** — `run_ruff_all` 툴. `asyncio.gather()`로 lint + format 동시 실행
- [x] **[P1] 채팅 히스토리 최대 크기 제한** — `_CHAT_HISTORY_MAX = 30`. 무한 누적 방지
- [x] **[P1] 2단계 OpenAPI 스펙 조회** — `get_openapi_spec_endpoints` → `get_openapi_spec_detail`. 100개 전체 스펙 대비 토큰 ~91% 절감 (OpenAPI MCP 서버 구현 후 활성화)

### P2 — 안정화 (컨텍스트 관리 + 계측)

- [x] **[P2] SummarizationMiddleware 트리거 조정** — 60,000 → 80,000 토큰. 불필요한 조기 요약 방지
- [x] **[P2] 타이밍 계측** — `TimingCallbackHandler` (`callbacks.py`). LLM/툴 호출별 실행 시간 INFO 로그

### 버그 수정 (테스트 작성 중 발견)

- [x] **`agent.py` 이름 충돌 수정** — `from langchain.agents import create_agent as _langchain_create_agent`. 무한 재귀 버그 수정

---

## Phase 3: 기능 개선

- [x] **요구사항 수집 대화** — `gather_requirements` 툴 + `GatherRequirementsMiddleware`. 코드 생성 전 에이전트가 서비스별 맞춤 질문을 구성해 사용자 요구사항 추출
- [ ] 생성된 서버에 `pyproject.toml` 자동 포함 (독립 실행 가능한 패키지로 생성)
- [ ] Chainlit Step 세분화 (스펙 조회 / 코드 생성 / lint / 테스트 단계별 표시)
- [ ] 생성 히스토리 로깅 (생성된 파일 경로 목록 기록)

---

## Phase 4: 프로덕션 🔲

- [ ] **OpenAPI MCP 서버 구현** — 스펙: [`docs/OPENAPI_MCP_SERVER_SPEC.md`](docs/OPENAPI_MCP_SERVER_SPEC.md)
  - `get_openapi_spec_endpoints(service_name)` — 엔드포인트 목록만 반환 (compact, ~3k 토큰)
  - `get_openapi_spec_detail(service_name, operation_ids[])` — 선택된 operation 상세 스펙만 반환
  - `get_openapi_spec(service_name)` — 레거시 폴백용 전체 스펙 반환
  - SCP 플랫폼 API 연동
- [ ] Docs MCP 서버 구현 (현재 외부 서버 assume 상태)
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
- **이유**: `langchain-openai` 패키지 사용.

### ADR-004: 생성 코드 저장 위치
- **결정**: 기본값 `~/scp-mcp-servers`, 대화 중 `set_output_directory` 툴로 변경 가능
- **이유**: 사용자 홈 디렉토리를 기본으로 하여 Docker 볼륨 마운트 없이도 접근 가능.

### ADR-005: 예시 코드 참조 방식
- **결정**: 시스템 프롬프트에 파일 내용 비주입 — MANIFEST로 best-match 선택 후 `read_multiple_files`로 읽기
- **이유**: 프롬프트 토큰 낭비 방지. 에이전트가 필요한 파일만 선택적으로 읽고 최신 상태를 반영.

### ADR-006: Docs MCP 선택 연결
- **결정**: `DOCS_MCP_URL` 설정 시에만 docs 서버 연결, 미설정 시 조용히 건너뜀
- **이유**: Docs MCP 서버 없이도 기본 동작은 완전히 가능. 연결 여부에 따라 시스템 프롬프트가 동적으로 구성됨.

### ADR-007: 생성 툴 프롬프트 스타일
- **결정**: `Annotated[type, Field(description=...)]` 파라미터 + "Use this tool when / Workflow / Common scenarios" docstring 구조
- **이유**: AWS MCP 서버 패턴 참조. AI 어시스턴트가 툴 호출 시점과 파라미터 선택을 더 정확히 판단하도록 유도.

### ADR-008: 코드 생성 전 요구사항 수집
- **결정**: `gather_requirements` 툴 + `GatherRequirementsMiddleware` (Scenario 0 HITL)
- **이유**: 서비스명만으로는 파악 불가능한 요구사항(엔드포인트 범위, 에러 처리 방식, 인증 구조 등)을 에이전트가 서비스 특성에 맞는 질문으로 추출. `cl.AskUserMessage`로 텍스트 답변 수집 후 ToolMessage로 에이전트에 반환.

### ADR-009: OpenAPI 스펙 2단계 조회
- **결정**: `get_openapi_spec_endpoints` → `get_openapi_spec_detail` 2단계 조회. `get_openapi_spec` 레거시 폴백 유지.
- **이유**: 서비스당 70~100개 엔드포인트의 전체 스펙은 150k 토큰 수준. 목록 조회(~3k) 후 선택된 5~10개만 상세 조회(~10k)하여 ~91% 절감. 에이전트 측 준비 완료, OpenAPI MCP 서버 구현 시 활성화.
