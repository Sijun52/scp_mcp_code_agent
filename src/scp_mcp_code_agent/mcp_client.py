"""MCP client configuration using LangChain MultiServerMCPClient.

Manages connections to:
  1. Filesystem MCP server  — built-in, runs as a stdio subprocess.
  2. OpenAPI MCP server     — external, assumed to be running (config from .env).
  3. Docs MCP server        — optional, remote HTTP; omitted when DOCS_MCP_URL is unset.
"""

import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator

from langchain_mcp_adapters.client import MultiServerMCPClient

from scp_mcp_code_agent.config import settings


def _build_server_configs() -> dict:
    """Build the server connection configuration dict for MultiServerMCPClient."""
    configs: dict = {}

    # ------------------------------------------------------------------
    # 1. Filesystem MCP server (bundled — always stdio)
    # ------------------------------------------------------------------
    configs["filesystem"] = {
        "transport": "stdio",
        "command": sys.executable,
        "args": ["-m", "scp_mcp_code_agent.mcp_servers.filesystem_server"],
    }

    # ------------------------------------------------------------------
    # 2. OpenAPI spec MCP server (external — configured via .env)
    # ------------------------------------------------------------------
    transport = settings.openapi_mcp_transport.lower()

    if transport == "stdio":
        configs["openapi"] = {
            "transport": "stdio",
            "command": settings.openapi_mcp_command,
            "args": settings.openapi_mcp_args_list,
        }
    elif transport in ("sse", "streamable_http"):
        configs["openapi"] = {
            "transport": transport,
            "url": settings.openapi_mcp_url,
        }
    else:
        raise ValueError(f"Unsupported OPENAPI_MCP_TRANSPORT: {transport!r}")

    # ------------------------------------------------------------------
    # 3. Docs MCP server (optional — skipped when DOCS_MCP_URL is empty)
    # ------------------------------------------------------------------
    if settings.docs_mcp_url:
        configs["docs"] = {
            "transport": "streamable_http",
            "url": settings.docs_mcp_url,
        }

    return configs


@asynccontextmanager
async def create_mcp_client() -> AsyncIterator[MultiServerMCPClient]:
    """Async context manager that yields a connected MultiServerMCPClient.

    Usage::

        async with create_mcp_client() as client:
            tools = client.get_tools()
    """
    async with MultiServerMCPClient(_build_server_configs()) as client:
        yield client
