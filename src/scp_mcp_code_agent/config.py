"""Application configuration loaded from environment variables."""

from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    # LLM
    openai_api_key: str = ""
    llm_model: str = "gpt-4o"
    llm_temperature: float = 0.2

    # OpenAPI MCP server connection
    openapi_mcp_transport: str = "stdio"
    openapi_mcp_command: str = "python"
    openapi_mcp_args: str = "-m openapi_mcp_server"
    openapi_mcp_url: str = ""  # used when transport=sse or streamable_http

    # Cloud platform credentials (forwarded to OpenAPI MCP server env)
    cloud_api_base_url: str = "https://api.example.com"
    cloud_api_key: str = ""
    cloud_tenant_id: str = ""

    # File system
    output_dir: Path = Path("./generated")
    example_dir: Path = Path("./mcp_code_example")

    # Agent behaviour
    agent_max_iterations: int = 25
    agent_verbose: bool = True

    # Middleware — ModelCallLimitMiddleware
    # 단일 서비스 생성 당 최대 모델 호출 횟수 (무한루프 / 비용 폭주 방지)
    middleware_model_call_run_limit: int = 20

    # Middleware — ToolRetryMiddleware / ModelRetryMiddleware
    middleware_retry_max: int = 3
    middleware_retry_backoff_factor: float = 2.0

    # Middleware — SummarizationMiddleware
    # 요약에 사용할 모델 (저렴한 모델 권장)
    middleware_summarization_model: str = "gpt-4o-mini"
    # 이 토큰 수 초과 시 요약 시작
    middleware_summarization_trigger_tokens: int = 60000
    # 요약 후 원본으로 남길 최근 메시지 수
    middleware_summarization_keep_messages: int = 10

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    @property
    def openapi_mcp_args_list(self) -> list[str]:
        """Split OPENAPI_MCP_ARGS string into a list for subprocess."""
        return self.openapi_mcp_args.split()


settings = Settings()
