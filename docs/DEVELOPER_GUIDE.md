# Developer Guide

로컬 개발 환경 설정, 프로젝트 구조, 테스트, 성능 최적화 등 개발자를 위한 가이드입니다.

---

## 로컬 개발 환경 설정

```bash
# 의존성 설치
uv sync --all-extras

# 환경변수 파일 생성
cp .env.example .env
# .env 수정:
#   OPENAI_API_KEY=sk-...
#   OPENAPI_MCP_TRANSPORT=stdio   (로컬 MCP 서버 사용 시)
#   OUTPUT_DIR=./generated        (선택 — 기본값: ~/scp-mcp-servers)
```

```bash
uv run chainlit run src/scp_mcp_code_agent/app.py
```

### CLI 실행 (선택)

```bash
uv run scp-agent "virtual server"
```

---

## 프로젝트 구조

```
scp_mcp_code_agent/
├── src/scp_mcp_code_agent/
│   ├── app.py                          # Chainlit UI 진입점 (히스토리 최대 30개 유지)
│   ├── agent.py                        # create_agent 팩토리 + 미들웨어 스택 + spec 캐시
│   ├── callbacks.py                    # TimingCallbackHandler — 툴/LLM 실행 시간 계측
│   ├── mcp_client.py                   # MultiServerMCPClient 설정 (filesystem/openapi/docs)
│   ├── config.py                       # 환경변수 (.env) 로딩 (pydantic-settings)
│   ├── middleware/                      # HITL 미들웨어 (5개 시나리오)
│   │   ├── gather_requirements.py      # Scenario 0: 코드 생성 전 요구사항 수집 (텍스트 질의)
│   │   ├── openapi_confirm.py          # Scenario 1: 스펙 조회 후 사용자 확인
│   │   ├── write_file_confirm.py       # Scenario 2+3: 코드 프리뷰 + 덮어쓰기 경고
│   │   └── test_failure.py             # Scenario 5: pytest 반복 실패 시 판단 위임
│   ├── tools/
│   │   ├── code_runner.py              # run_pytest / run_ruff_check / run_ruff_all (async)
│   │   └── planning.py                 # gather_requirements / confirm_endpoint_plan / set_output_directory
│   ├── prompts/
│   │   └── system_prompt.py            # 시스템 프롬프트 빌더 (docs 연결 여부 반영)
│   └── mcp_servers/
│       └── filesystem_server.py        # 자체 구현 Filesystem MCP 서버 (read_multiple_files 포함)
│
├── mcp_code_example/                   # 에이전트 코드 스타일 레퍼런스
│   ├── MANIFEST.json                   # 예시 프로젝트 인덱스 (에이전트가 best-match 선택에 사용)
│   ├── server.py                       # Virtual Server MCP 예시 (Annotated+Field 리치 프롬프트)
│   └── tests/
│       └── test_server.py              # 예시 테스트 코드
│
├── tests/                              # 단위 테스트 (커버리지 99%)
│   ├── test_agent.py
│   ├── test_agent_helpers.py
│   ├── test_app.py
│   ├── test_callbacks.py
│   ├── test_filesystem_server.py
│   ├── test_middleware.py
│   ├── test_planning.py
│   └── test_tools.py
│
├── docs/
│   ├── DEVELOPER_GUIDE.md              # 이 파일
│   ├── DEVOPS_GUIDE.md                 # Docker / 배포 / MCP 서버 연결
│   └── OPENAPI_MCP_SERVER_SPEC.md      # OpenAPI MCP 서버 구현 스펙 (2단계 조회 툴 인터페이스)
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── .env.example
```

---

## 기술 스택

| 영역 | 기술 |
|---|---|
| 언어 | Python 3.11+ |
| 의존성 관리 | [uv](https://docs.astral.sh/uv/) |
| 에이전트 | [LangChain](https://python.langchain.com/) `create_agent` + [LangGraph](https://langchain-ai.github.io/langgraph/) |
| LLM | OpenAI `gpt-4o` (`langchain-openai`) |
| MCP 연결 | [`langchain-mcp-adapters`](https://github.com/langchain-ai/langchain-mcp-adapters) `MultiServerMCPClient` |
| MCP 서버 | [`mcp`](https://github.com/modelcontextprotocol/python-sdk) `FastMCP` |
| UI | [Chainlit](https://docs.chainlit.io/) |
| Lint | [ruff](https://docs.astral.sh/ruff/) |
| 테스트 | [pytest](https://pytest.org/) + pytest-asyncio |

---

## 테스트

```bash
# 전체 테스트 실행
uv run pytest tests/ -v

# 커버리지 포함 (99%)
uv run pytest tests/ --cov=scp_mcp_code_agent --cov-report=term-missing
```

### Lint 체크

```bash
uv run ruff check src/ tests/
```

### MCP 예시 코드 테스트

```bash
uv run pytest mcp_code_example/tests/ -v
```

---

## 예시 코드 관리 (`mcp_code_example/MANIFEST.json`)

에이전트는 코드 생성 전 `MANIFEST.json`을 읽어 서비스 특성(`tags`, `service_characteristics`)이 가장 유사한 예시를 선택합니다.
선택된 예시의 파일만 `read_multiple_files`로 배치 읽기하여 불필요한 파일 로드를 줄입니다.

### 예시 추가 방법

1. `mcp_code_example/<예시명>/` 디렉토리 생성 후 `server.py`, `tests/test_server.py` 작성
2. `MANIFEST.json`의 `examples` 배열에 항목 추가:

```json
{
  "name": "block_storage",
  "description": "블록 스토리지 볼륨 관리 MCP 서버 예시",
  "tags": ["storage", "block", "volume", "IaaS"],
  "service_characteristics": ["CRUD 기반 리소스 관리", "비동기 작업"],
  "path": "block_storage",
  "files": ["server.py", "tests/test_server.py"],
  "highlights": ["볼륨 스냅샷 처리", "attach/detach 작업"]
}
```

### MANIFEST 필드 설명

| 필드 | 역할 |
|---|---|
| `name` | 고유 식별자 (snake_case) |
| `description` | 에이전트에게 노출되는 예시 설명 |
| `tags` | 서비스 분류 키워드 — 요청 서비스와 매칭할 때 사용 |
| `service_characteristics` | 패턴 설명 (CRUD, 비동기 작업, 이벤트 기반 등) |
| `path` | `mcp_code_example/` 기준 상대 경로 (flat 구조면 `"."`) |
| `files` | 에이전트가 읽을 파일 목록 (`path` 기준 상대 경로) |
| `highlights` | 이 예시에서 주목할 패턴 — 에이전트 선택 판단에 참고 |

---

## 성능 최적화

| 항목 | 방식 | 효과 |
|------|------|------|
| **Async subprocess** | `subprocess.run()` → `asyncio.create_subprocess_exec()` | pytest/ruff 실행(10~30s) 중 이벤트 루프 블로킹 제거 |
| **ruff 병렬 실행** | `run_ruff_all` — `asyncio.gather()`로 lint + format 동시 실행 | 툴 호출 2회 → 1회, 실행 시간 절반 |
| **2단계 OpenAPI 스펙 조회** | `get_openapi_spec_endpoints` → `get_openapi_spec_detail` — 선택된 operation만 상세 조회 | 전체 스펙(~150k 토큰) → 목록(~3k) + 상세(~10k), 약 91% 토큰 절감 |
| **OpenAPI spec 캐싱** | `_wrap_spec_tool_with_cache()` — TTL 5분 in-memory 캐시 | 동일 세션 내 반복 스펙 조회 즉시 반환 |
| **파일 읽기 배치** | `read_multiple_files` — 여러 파일을 단일 MCP 호출로 읽기 | N번 `read_file` → 1번으로 단축 |
| **MANIFEST 기반 예시 선택** | `MANIFEST.json` → tags 매칭 → `read_multiple_files` 배치 읽기 | 불필요한 예시 파일 로드 제거, 서비스별 최적 레퍼런스 자동 선택 |
| **컨텍스트 관리** | `SummarizationMiddleware` 트리거 60k → 80k 토큰 | 불필요한 조기 요약 방지 |
| **히스토리 제한** | `_CHAT_HISTORY_MAX = 30` — 세션당 마지막 30개 메시지만 유지 | 장기 세션 컨텍스트 무한 누적 방지 |
| **타이밍 계측** | `TimingCallbackHandler` — LLM/툴 호출별 실행 시간 INFO 로그 | 실제 병목 식별 가능 |
| **vLLM Prefix 캐싱** | 서버 실행 시 `--enable-prefix-caching` 플래그 | 시스템 프롬프트 prefill 재계산 skip, TTFT 단축 |

### 타이밍 로그 확인

```bash
uv run chainlit run src/scp_mcp_code_agent/app.py 2>&1 | grep "\[timing\]"
# [timing] LLM(gpt-4o) completed in 3.42s
# [timing] Tool(get_openapi_spec) completed in 0.18s (cached)
```

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
- **이유**: 서비스명만으로는 파악 불가능한 요구사항(엔드포인트 범위, 에러 처리 방식, 인증 구조 등)을 에이전트가 서비스 특성에 맞는 질문으로 추출. `cl.AskUserMessage`로 텍스트 답변 수집 후 `ToolMessage`로 에이전트에 반환.

### ADR-009: OpenAPI 스펙 2단계 조회
- **결정**: `get_openapi_spec_endpoints` → `get_openapi_spec_detail` 2단계 조회. `get_openapi_spec` 레거시 폴백 유지.
- **이유**: 서비스당 70~100개 엔드포인트의 전체 스펙은 150k 토큰 수준. 목록 조회(~3k) 후 선택된 5~10개만 상세 조회(~10k)하여 ~91% 절감. 상세 스펙은 `docs/OPENAPI_MCP_SERVER_SPEC.md` 참조.
