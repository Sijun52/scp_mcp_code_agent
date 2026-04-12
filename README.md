# SCP MCP Code Agent

OpenAPI 스펙을 입력받아 **MCP(Model Context Protocol) 서버 코드를 자동 생성**하는 LangChain 에이전트.

---

## 개요

```
사용자 입력 (서비스명)
    │
    ▼
Chainlit UI  ──────────────────────────────────────────────────────
    │
    ▼
LangChain Agent  (langchain.agents.create_agent + gpt-4o)
    │
    ├─► OpenAPI MCP Server     → 서비스 OpenAPI 스펙 조회
    ├─► Filesystem MCP Server  → mcp_code_example 읽기 / 코드 파일 저장
    ├─► run_ruff_check          → 생성 코드 Lint 검증
    └─► run_pytest              → 생성 테스트 코드 실행
    │
    ▼
generated/<service>_mcp_server/
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
│   ├── app.py                          # Chainlit UI 진입점
│   ├── agent.py                        # create_agent 팩토리
│   ├── mcp_client.py                   # MultiServerMCPClient 설정
│   ├── config.py                       # 환경변수 (.env) 로딩
│   ├── tools/
│   │   └── code_runner.py              # run_pytest / run_ruff_check (LangChain 도구)
│   ├── prompts/
│   │   └── system_prompt.py            # 시스템 프롬프트 빌더
│   └── mcp_servers/
│       └── filesystem_server.py        # 자체 구현 Filesystem MCP 서버
│
├── mcp_code_example/                   # 에이전트 코드 스타일 레퍼런스
│   ├── server.py                       # Virtual Server MCP 서버 예시
│   └── tests/
│       └── test_server.py              # 예시 테스트 코드
│
├── tests/                              # 프로젝트 단위 테스트
│   ├── test_agent.py
│   └── test_tools.py
│
├── generated/                          # 에이전트가 생성한 MCP 서버 출력 디렉토리
│   └── <service_name>_mcp_server/
│       ├── server.py
│       └── tests/
│           └── test_server.py
│
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

### 1. 환경 설정

```bash
# 의존성 설치
uv sync --all-extras

# 환경변수 파일 생성
cp .env.example .env
```

`.env` 파일에서 아래 항목을 채웁니다:

```dotenv
OPENAI_API_KEY=sk-...         # OpenAI API 키 (필수)
LLM_MODEL=gpt-4o              # 사용할 모델 (기본값)

CLOUD_API_BASE_URL=https://...  # SCP 플랫폼 API URL
CLOUD_API_KEY=...               # SCP API 키
CLOUD_TENANT_ID=...             # SCP 테넌트 ID
```

### 2. Chainlit UI 실행

```bash
uv run chainlit run src/scp_mcp_code_agent/app.py
```

브라우저에서 `http://localhost:8000` 접속 후 서비스명을 입력합니다.

### 3. CLI 실행 (선택)

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

## MCP 서버 구성

에이전트는 두 개의 MCP 서버를 연결합니다:

| 서버 | 역할 | 설정 |
|---|---|---|
| **filesystem** | 파일 읽기/쓰기/디렉토리 탐색 | 자체 구현, 자동 실행 (stdio) |
| **openapi** | 서비스별 OpenAPI 스펙 제공 | `.env`의 `OPENAPI_MCP_*` 설정 |

### OpenAPI MCP 서버 연결 설정 (`.env`)

**stdio 방식 (기본)**
```dotenv
OPENAPI_MCP_TRANSPORT=stdio
OPENAPI_MCP_COMMAND=python
OPENAPI_MCP_ARGS=-m openapi_mcp_server
```

**HTTP 방식**
```dotenv
OPENAPI_MCP_TRANSPORT=streamable_http
OPENAPI_MCP_URL=http://localhost:8080/mcp
```

> OpenAPI MCP 서버는 `get_openapi_spec(service_name: str)` 툴을 노출해야 합니다.

---

## 생성 코드 예시

에이전트가 생성하는 `server.py`는 아래 구조를 따릅니다:

```python
from mcp.server.fastmcp import FastMCP
import httpx, os

mcp = FastMCP("block-storage")

@mcp.tool()
async def list_volumes(region: str = "kr-central-1") -> list[dict]:
    """List all block storage volumes. ..."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(f"{BASE_URL}/volumes", headers=_headers())
        response.raise_for_status()
        return response.json()["volumes"]

# ... 추가 툴들

if __name__ == "__main__":
    mcp.run()
```
