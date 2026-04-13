# SCP MCP Code Agent

OpenAPI 스펙을 입력받아 **MCP(Model Context Protocol) 서버 코드를 자동 생성**하는 LangChain 에이전트.

---

## 개요

```
사용자 입력 (서비스명)
    │
    ▼
Chainlit UI  ─────────────────────────────────────────────────────
    │  (HITL: 스펙 확인 / 엔드포인트 계획 승인 / 파일 저장 확인 등)
    ▼
LangChain Agent  (langchain.agents.create_agent + gpt-4o)
    │
    ├─► OpenAPI MCP Server     → 서비스 OpenAPI 스펙 조회
    ├─► Filesystem MCP Server  → mcp_code_example 읽기 / 코드 파일 저장
    ├─► Docs MCP Server        → SCP 상품 문서 검색 (선택, DOCS_MCP_URL 설정 시)
    ├─► run_ruff_all            → Lint + 포맷 동시 검증 (asyncio.gather 병렬)
    └─► run_pytest              → 생성 테스트 코드 실행 (async, non-blocking)
    │
    ▼
~/scp-mcp-servers/<service>_mcp_server/
    ├── server.py
    └── tests/
        └── test_server.py
```

에이전트는 lint/테스트 실패 시 자동으로 코드를 수정하고 재검증하는 루프를 돌며, 두 검증이 모두 통과된 후에만 완료를 보고합니다.

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
│   │   ├── openapi_confirm.py          # Scenario 1: 스펙 조회 후 사용자 확인
│   │   ├── write_file_confirm.py       # Scenario 2+3: 코드 프리뷰 + 덮어쓰기 경고
│   │   └── test_failure.py             # Scenario 5: pytest 반복 실패 시 판단 위임
│   ├── tools/
│   │   ├── code_runner.py              # run_pytest / run_ruff_check / run_ruff_all (async)
│   │   └── planning.py                 # confirm_endpoint_plan / set_output_directory
│   ├── prompts/
│   │   └── system_prompt.py            # 시스템 프롬프트 빌더 (docs 연결 여부 반영)
│   └── mcp_servers/
│       └── filesystem_server.py        # 자체 구현 Filesystem MCP 서버 (read_multiple_files 포함)
│
├── mcp_code_example/                   # 에이전트 코드 스타일 레퍼런스
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
├── Dockerfile                          # 멀티스테이지 빌드
├── docker-compose.yml                  # volume 마운트로 로컬 파일 생성
├── pyproject.toml
├── .env.example
├── TODO.md
└── README.md
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

## 시작하기

### Docker로 실행 (권장)

사용자는 Docker 이미지를 받아서 실행하기만 하면 됩니다.  
에이전트가 생성한 `.py` 파일은 **사용자 로컬 `./generated/` 디렉토리**에 직접 저장됩니다.

```
[컨테이너 내부 /app/generated] ←── volume ──► [로컬 ./generated]
```

#### 1. 환경변수 파일 준비

```bash
curl -o .env https://raw.githubusercontent.com/Sijun52/scp_mcp_code_agent/master/.env.example
# 또는 직접 .env 파일 생성
```

`.env` 항목:

```dotenv
OPENAI_API_KEY=sk-...

# Remote OpenAPI MCP 서버 주소 (필수)
OPENAPI_MCP_TRANSPORT=streamable_http
OPENAPI_MCP_URL=http://your-openapi-mcp-server:8080/mcp

# SCP Docs MCP 서버 주소 (선택 — 미설정 시 스펙만으로 동작)
# DOCS_MCP_URL=http://your-docs-mcp-server:8080/mcp
```

#### 2. docker-compose로 실행

```bash
# docker-compose.yml 다운로드
curl -o docker-compose.yml https://raw.githubusercontent.com/Sijun52/scp_mcp_code_agent/master/docker-compose.yml

# 실행 (로컬 ./generated 디렉토리에 파일 생성됨)
docker compose up
```

브라우저에서 `http://localhost:8000` 접속 후 서비스명을 입력합니다.

#### 3. docker run으로 직접 실행

```bash
docker run \
  --env-file .env \
  -v $(pwd)/generated:/app/generated \
  -p 8000:8000 \
  sijun52/scp-mcp-code-agent:latest
```

---

### 로컬 개발 환경 설정

```bash
# 의존성 설치
uv sync --all-extras

# 환경변수 파일 생성
cp .env.example .env
# .env에서 수정:
#   OPENAI_API_KEY=sk-...
#   OPENAPI_MCP_TRANSPORT=stdio  (로컬 MCP 서버 사용 시)
#   OUTPUT_DIR=./generated       (선택 — 기본값: ~/scp-mcp-servers)
```

```bash
uv run chainlit run src/scp_mcp_code_agent/app.py
```

#### CLI 실행 (선택)

```bash
uv run scp-agent "virtual server"
```

---

## 사용 예시

Chainlit 채팅창에 서비스명을 입력하면 에이전트가 자동으로 아래 단계를 수행합니다:

```
입력: "block storage"

[Step 1] mcp_code_example/ 디렉토리 탐색 및 예시 코드 읽기
[Step 2] get_openapi_spec("block storage") 호출
[Step 3] server.py 생성
[Step 4] tests/test_server.py 생성
[Step 5] 파일 저장 → generated/block_storage_mcp_server/
[Step 6] run_ruff_check 실행 → lint 통과
[Step 7] run_pytest 실행 → 테스트 통과
[Step 8] 완료 보고
```

생성된 파일은 `generated/block_storage_mcp_server/` 디렉토리에 저장됩니다.

---

## 개발

### 테스트 실행

```bash
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

## 성능 최적화

| 항목 | 방식 | 효과 |
|------|------|------|
| **Async subprocess** | `subprocess.run()` → `asyncio.create_subprocess_exec()` | pytest/ruff 실행(10~30s) 중 이벤트 루프 블로킹 제거 |
| **ruff 병렬 실행** | `run_ruff_all` 툴 — `asyncio.gather()`로 lint + format 동시 실행 | 툴 호출 2회 → 1회, 실행 시간 절반 |
| **OpenAPI spec 캐싱** | `_wrap_spec_tool_with_cache()` — TTL 5분 in-memory 캐시 | 동일 세션 내 반복 스펙 조회 즉시 반환 |
| **파일 읽기 배치** | `read_multiple_files` 툴 — 여러 파일을 단일 MCP 호출로 읽기 | N번 `read_file` → 1번으로 단축 |
| **컨텍스트 관리** | `SummarizationMiddleware` 트리거 60k → 80k 토큰 | 불필요한 조기 요약 방지 |
| **히스토리 제한** | `_CHAT_HISTORY_MAX = 30` — 세션당 마지막 30개 메시지만 유지 | 장기 세션 컨텍스트 무한 누적 방지 |
| **타이밍 계측** | `TimingCallbackHandler` — LLM/툴 호출별 실행 시간 INFO 로그 | 실제 병목 식별 가능 |
| **vLLM Prefix 캐싱** | 서버 실행 시 `--enable-prefix-caching` 플래그 | 시스템 프롬프트 prefill 재계산 skip, TTFT 단축 |

---

## MCP 서버 구성

| 서버 | 역할 | 설정 |
|---|---|---|
| **filesystem** | 파일 읽기/쓰기/디렉토리 탐색 | 자체 구현, 자동 실행 (stdio) |
| **openapi** | 서비스별 OpenAPI 스펙 제공 | `.env`의 `OPENAPI_MCP_*` 설정 |
| **docs** | SCP 상품 문서 검색 (선택) | `.env`의 `DOCS_MCP_URL` 설정 시 연결 |

### OpenAPI MCP 서버 연결 설정 (`.env`)

**HTTP 방식 (원격 서버)**
```dotenv
OPENAPI_MCP_TRANSPORT=streamable_http
OPENAPI_MCP_URL=http://your-openapi-mcp-server:8080/mcp
```

**stdio 방식 (로컬 개발)**
```dotenv
OPENAPI_MCP_TRANSPORT=stdio
OPENAPI_MCP_COMMAND=python
OPENAPI_MCP_ARGS=-m openapi_mcp_server
```

> OpenAPI MCP 서버는 `get_openapi_spec(service_name: str)` 툴을 노출해야 합니다.

### Docs MCP 서버 (선택)

`DOCS_MCP_URL`을 설정하면 에이전트가 SCP 상품 문서를 검색하여 생성 코드의 툴 설명(docstring, Field description)을 풍부하게 작성합니다. 미설정 시 OpenAPI 스펙만으로 동작합니다.

```dotenv
DOCS_MCP_URL=http://your-docs-mcp-server:8080/mcp
```

