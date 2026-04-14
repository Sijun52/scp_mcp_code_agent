# DevOps Guide

Docker 빌드, 배포, MCP 서버 연결 설정 등 운영/배포를 위한 가이드입니다.

---

## Docker로 실행 (권장)

에이전트가 생성한 `.py` 파일은 **사용자 로컬 `./generated/` 디렉토리**에 직접 저장됩니다.

```
[컨테이너 내부 /app/generated] ←── volume ──► [로컬 ./generated]
```

### 1. 환경변수 파일 준비

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

# 생성 파일 저장 경로 (선택 — 기본값: ~/scp-mcp-servers)
# OUTPUT_DIR=/app/generated

# LLM 모델 (선택 — 기본값: gpt-4o)
# LLM_MODEL=gpt-4o
```

### 2. docker-compose로 실행

```bash
# docker-compose.yml 다운로드
curl -o docker-compose.yml https://raw.githubusercontent.com/Sijun52/scp_mcp_code_agent/master/docker-compose.yml

# 실행 (로컬 ./generated 디렉토리에 파일 생성됨)
docker compose up
```

브라우저에서 `http://localhost:8000` 접속 후 서비스명을 입력합니다.

### 3. docker run으로 직접 실행

```bash
docker run \
  --env-file .env \
  -v $(pwd)/generated:/app/generated \
  -p 8000:8000 \
  sijun52/scp-mcp-code-agent:latest
```

---

## Docker 이미지 빌드

```bash
docker build -t scp-mcp-code-agent .
```

멀티스테이지 빌드 구조:
- **builder**: `uv` 기반 의존성 설치
- **runtime**: 최소 Python 이미지에 패키지만 복사

---

## MCP 서버 연결 설정

### OpenAPI MCP 서버 (필수)

에이전트가 `get_openapi_spec(service_name)` 툴을 통해 OpenAPI 스펙을 가져오는 서버입니다.

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

> OpenAPI MCP 서버는 반드시 `get_openapi_spec(service_name: str)` 툴을 노출해야 합니다.

### Docs MCP 서버 (선택)

`DOCS_MCP_URL`을 설정하면 에이전트가 SCP 상품 문서를 검색해 생성 코드의 docstring과 Field description을 풍부하게 작성합니다.
미설정 시 OpenAPI 스펙만으로 동작합니다.

```dotenv
DOCS_MCP_URL=http://your-docs-mcp-server:8080/mcp
```

### Filesystem MCP 서버 (자동)

별도 설정 불필요. `mcp_servers/filesystem_server.py`가 에이전트 시작 시 자동으로 stdio로 실행됩니다.

---

## MCP 서버 구성 요약

| 서버 | 역할 | 설정 |
|---|---|---|
| **filesystem** | 파일 읽기/쓰기/디렉토리 탐색 | 자체 구현, 자동 실행 (stdio) |
| **openapi** | 서비스별 OpenAPI 스펙 제공 | `.env`의 `OPENAPI_MCP_*` 설정 |
| **docs** | SCP 상품 문서 검색 (선택) | `.env`의 `DOCS_MCP_URL` 설정 시 연결 |

---

## vLLM 사용 시 성능 최적화

OpenAI API 대신 vLLM 호환 서버를 사용할 경우, Prefix Caching을 활성화해 시스템 프롬프트 prefill 비용을 줄일 수 있습니다.

```bash
python -m vllm.entrypoints.openai.api_server \
  --model <your-model> \
  --enable-prefix-caching
```

`.env`에서 엔드포인트 변경:

```dotenv
OPENAI_API_BASE=http://your-vllm-server:8000/v1
LLM_MODEL=your-model-name
```

> OpenAI API의 Prompt Caching은 자동 적용됩니다 (1024 토큰 이상 프롬프트, 추가 설정 불필요).
