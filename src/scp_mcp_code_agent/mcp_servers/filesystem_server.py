"""Filesystem MCP Server.

Provides file read/write/list tools to the LangChain agent so that
generated code is written as actual .py files on disk — not just
returned as text in the chat response.

Usage (stdio transport):
    python -m scp_mcp_code_agent.mcp_servers.filesystem_server

Design rationale (ADR-002):
    We implement our own lightweight filesystem server in Python to
    avoid the Node.js dependency of the official MCP filesystem package.
"""

import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("filesystem")

# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def read_file(path: str) -> str:
    """Read the contents of a file.

    Args:
        path: Absolute or relative path to the file.

    Returns:
        File contents as a UTF-8 string.
    """
    return Path(path).read_text(encoding="utf-8")


@mcp.tool()
def write_file(path: str, content: str) -> str:
    """Write (or overwrite) a file with the given content.

    Parent directories are created automatically if they do not exist.

    Args:
        path: Absolute or relative path where the file should be written.
        content: File content to write (UTF-8).

    Returns:
        Confirmation message with the resolved path.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"Written {len(content)} characters to {target.resolve()}"


@mcp.tool()
def list_directory(path: str) -> list[str]:
    """List the names of files and directories inside *path*.

    Args:
        path: Path to the directory to list.

    Returns:
        Sorted list of entry names (not full paths).
    """
    return sorted(os.listdir(path))


@mcp.tool()
def create_directory(path: str) -> str:
    """Create a directory and all intermediate parents.

    Args:
        path: Path of the directory to create.

    Returns:
        Confirmation message.
    """
    Path(path).mkdir(parents=True, exist_ok=True)
    return f"Directory created: {Path(path).resolve()}"


@mcp.tool()
def file_exists(path: str) -> bool:
    """Check whether a file or directory exists at *path*.

    Args:
        path: Path to check.

    Returns:
        True if the path exists, False otherwise.
    """
    return Path(path).exists()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
