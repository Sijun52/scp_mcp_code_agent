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

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    @property
    def openapi_mcp_args_list(self) -> list[str]:
        """Split OPENAPI_MCP_ARGS string into a list for subprocess."""
        return self.openapi_mcp_args.split()


settings = Settings()
