"""Custom LangChain tools for running pytest and ruff against generated code.

These tools wrap subprocess calls and are designed to be used by the
LangChain agent AFTER it writes generated MCP server files to disk.

Design rationale (ADR-001):
  pytest and ruff are local process invocations — wrapping them as
  plain LangChain Tool objects is simpler and more reliable than
  routing them through an MCP server.
"""

import subprocess
import sys
from pathlib import Path

from langchain_core.tools import tool


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------


def _run(cmd: list[str], cwd: str | Path | None = None) -> str:
    """Run *cmd* in a subprocess and return combined stdout+stderr."""
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else None,
    )
    output = ""
    if result.stdout:
        output += result.stdout
    if result.stderr:
        output += result.stderr
    return_code_line = f"\n[exit code: {result.returncode}]"
    return output + return_code_line


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@tool
def run_pytest(test_path: str, working_dir: str = ".") -> str:
    """Run pytest against a test file or directory and return the output.

    Args:
        test_path: Path to a test file or directory (e.g. 'generated/my_service_mcp_server/tests/').
        working_dir: Working directory from which to run pytest.
                     Defaults to the current directory.

    Returns:
        Combined stdout + stderr from pytest with exit code appended.
        Exit code 0 means all tests passed.
    """
    cmd = [sys.executable, "-m", "pytest", test_path, "-v", "--tb=short"]
    return _run(cmd, cwd=working_dir)


@tool
def run_ruff_check(target_path: str, working_dir: str = ".") -> str:
    """Run ruff lint check against a file or directory and return the output.

    Args:
        target_path: Path to a .py file or directory to lint
                     (e.g. 'generated/my_service_mcp_server/server.py').
        working_dir: Working directory from which to run ruff.

    Returns:
        Combined stdout + stderr from ruff with exit code appended.
        Exit code 0 means no lint errors found.
    """
    cmd = [sys.executable, "-m", "ruff", "check", target_path]
    return _run(cmd, cwd=working_dir)


@tool
def run_ruff_format_check(target_path: str, working_dir: str = ".") -> str:
    """Check code formatting with ruff format --check (does NOT modify files).

    Args:
        target_path: Path to a .py file or directory to check formatting.
        working_dir: Working directory from which to run ruff.

    Returns:
        Combined stdout + stderr from ruff with exit code appended.
        Exit code 0 means formatting is correct.
    """
    cmd = [sys.executable, "-m", "ruff", "format", "--check", target_path]
    return _run(cmd, cwd=working_dir)


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

CODE_RUNNER_TOOLS = [run_pytest, run_ruff_check, run_ruff_format_check]
