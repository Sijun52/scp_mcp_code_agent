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
    ├─► Filesystem MCP Server  → 예시 코드 읽기 / 생성 코드 저장
    ├─► Docs MCP Server        → SCP 상품 문서 검색 (선택, DOCS_MCP_URL 설정 시)
    ├─► run_ruff_all            → Lint + 포맷 동시 검증
    └─► run_pytest              → 생성 테스트 코드 실행
    │
    ▼
~/scp-mcp-servers/<service>_mcp_server/
    ├── server.py
    └── tests/
        └── test_server.py
```

에이전트는 lint/테스트 실패 시 자동으로 코드를 수정하고 재검증하며, 두 검증이 모두 통과된 후에만 완료를 보고합니다.

---

## 빠른 시작 (Docker)

### 1. 환경변수 파일 준비

```bash
curl -o .env https://raw.githubusercontent.com/Sijun52/scp_mcp_code_agent/master/.env.example
```

`.env` 필수 항목:

```dotenv
OPENAI_API_KEY=sk-...

OPENAPI_MCP_TRANSPORT=streamable_http
OPENAPI_MCP_URL=http://your-openapi-mcp-server:8080/mcp
```

### 2. 실행

```bash
curl -o docker-compose.yml https://raw.githubusercontent.com/Sijun52/scp_mcp_code_agent/master/docker-compose.yml
docker compose up
```

브라우저에서 `http://localhost:8000` 접속 후 서비스명을 입력합니다.

생성된 파일은 로컬 `./generated/` 디렉토리에 저장됩니다.

---

## 사용 예시

```
입력: "block storage"

[Step 1] MANIFEST.json 읽기 → 가장 유사한 예시 선택 → 예시 코드 읽기
[Step 2] get_openapi_spec("block storage") 호출
[Step 3] server.py 생성
[Step 4] tests/test_server.py 생성
[Step 5] 파일 저장 → generated/block_storage_mcp_server/
[Step 6] run_ruff_all 실행 → lint 통과
[Step 7] run_pytest 실행 → 테스트 통과
[Step 8] 완료 보고
```

---

## 추가 문서

| 문서 | 내용 |
|---|---|
| [DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md) | 프로젝트 구조, 기술 스택, 로컬 개발, 테스트, MANIFEST 관리, 성능 최적화, ADR |
| [DEVOPS_GUIDE.md](docs/DEVOPS_GUIDE.md) | Docker 상세, MCP 서버 연결 설정, 환경변수 전체, vLLM 설정 |
| [TODO.md](TODO.md) | 개발 현황 및 백로그 |
