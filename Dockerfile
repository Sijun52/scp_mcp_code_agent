# ============================================================
# Multi-stage build for scp-mcp-code-agent
# ============================================================
# Stage 1: builder — uv로 의존성 설치
# Stage 2: runtime — 최소 이미지에 .venv만 복사
# ============================================================

# ---- Stage 1: builder ----
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder

WORKDIR /app

# 캐시 효율을 위해 pyproject.toml 먼저 복사 후 의존성 설치
COPY pyproject.toml .
COPY src/ src/

# --no-dev: 운영 의존성만 설치
# UV_COMPILE_BYTECODE: .pyc 사전 컴파일 (런타임 속도 향상)
# UV_LINK_MODE=copy: 심볼릭 링크 대신 파일 복사 (stage 간 이식성)
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

RUN uv sync --no-dev


# ---- Stage 2: runtime ----
FROM python:3.11-slim-bookworm AS runtime

WORKDIR /app

# builder에서 설치된 가상환경만 복사
COPY --from=builder /app/.venv /app/.venv

# 소스 코드 및 예시 코드 복사
COPY src/ src/
COPY mcp_code_example/ mcp_code_example/

# generated 디렉토리 생성 (volume mount 마운트 포인트)
RUN mkdir -p /app/generated

# PATH에 가상환경 bin 추가
ENV PATH="/app/.venv/bin:$PATH"

# 컨테이너 내부 경로 명시 (config.py 기본값 override)
ENV OUTPUT_DIR=/app/generated
ENV EXAMPLE_DIR=/app/mcp_code_example

# OpenAPI MCP는 Remote HTTP 서버로 연결 (기본값)
ENV OPENAPI_MCP_TRANSPORT=streamable_http

EXPOSE 8000

# Chainlit은 반드시 --host 0.0.0.0 지정해야 컨테이너 외부에서 접근 가능
CMD ["chainlit", "run", "src/scp_mcp_code_agent/app.py", \
     "--host", "0.0.0.0", "--port", "8000"]