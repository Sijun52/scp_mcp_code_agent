"""Application configuration loaded from environment variables.

환경변수로 관리하는 것:
  - API 키, MCP 서버 URL 등 배포 환경마다 달라지는 값

코드에서 직접 관리하는 것 (변경 시 재배포):
  - LLM temperature, example_dir, agent 반복 설정 등 튜닝 파라미터
"""

from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()

# mcp_code_example 디렉토리는 패키지 위치 기준 상대경로로 고정
# src/scp_mcp_code_agent/config.py → 상위 3단계 = 프로젝트 루트
_EXAMPLE_DIR: Path = Path(__file__).parent.parent.parent / "mcp_code_example"


class Settings(BaseSettings):
    # LLM
    openai_api_key: str = ""
    llm_model: str = "gpt-4o"

    # OpenAPI MCP server connection (스펙 제공 전용 — 인증 불필요)
    openapi_mcp_transport: str = "streamable_http"
    openapi_mcp_url: str = ""          # streamable_http / sse 방식
    openapi_mcp_command: str = "python"  # stdio 방식 fallback
    openapi_mcp_args: str = "-m openapi_mcp_server"

    # 생성된 MCP 서버 저장 위치 (기본: 사용자 홈 디렉토리)
    output_dir: Path = Path.home() / "scp-mcp-servers"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    @property
    def example_dir(self) -> Path:
        """예시 코드 디렉토리 — 코드 고정값, env 오버라이드 불필요."""
        return _EXAMPLE_DIR

    @property
    def openapi_mcp_args_list(self) -> list[str]:
        """Split OPENAPI_MCP_ARGS string into a list for subprocess."""
        return self.openapi_mcp_args.split()


settings = Settings()