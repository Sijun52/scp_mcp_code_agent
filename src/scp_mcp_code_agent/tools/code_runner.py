"""Custom LangChain tools for running pytest and ruff against generated code.

These tools wrap subprocess calls and are designed to be used by the
LangChain agent AFTER it writes generated MCP server files to disk.

Design rationale (ADR-001):
  pytest and ruff are local process invocations — wrapping them as
  plain LangChain Tool objects is simpler and more reliable than
  routing them through an MCP server.
"""

import asyncio
import sys
from pathlib import Path

from langchain_core.tools import tool


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------


async def _run(cmd: list[str], cwd: str | Path | None = None) -> str:
    """Run *cmd* in a subprocess asynchronously and return combined stdout+stderr."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(cwd) if cwd else None,
    )
    stdout, stderr = await proc.communicate()
    output = (stdout.decode() if stdout else "") + (stderr.decode() if stderr else "")
    return output + f"\n[exit code: {proc.returncode}]"


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@tool
async def run_pytest(test_path: str, working_dir: str = ".") -> str:
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
    return await _run(cmd, cwd=working_dir)


@tool
async def run_ruff_check(target_path: str, working_dir: str = ".") -> str:
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
    return await _run(cmd, cwd=working_dir)


@tool
async def run_ruff_format_check(target_path: str, working_dir: str = ".") -> str:
    """Check code formatting with ruff format --check (does NOT modify files).

    Args:
        target_path: Path to a .py file or directory to check formatting.
        working_dir: Working directory from which to run ruff.

    Returns:
        Combined stdout + stderr from ruff with exit code appended.
        Exit code 0 means formatting is correct.
    """
    cmd = [sys.executable, "-m", "ruff", "format", "--check", target_path]
    return await _run(cmd, cwd=working_dir)


@tool
async def run_ruff_all(target_path: str, working_dir: str = ".") -> str:
    """Run ruff lint check AND ruff format check simultaneously in a single call.

    Prefer this tool over calling run_ruff_check and run_ruff_format_check
    separately — it runs both in parallel and returns a combined report,
    cutting the number of tool calls and wall-clock time in half.

    Args:
        target_path: Path to a .py file or directory to check.
        working_dir: Working directory from which to run ruff.

    Returns:
        Combined report with sections for lint and format results.
        Overall exit code is non-zero if either check failed.
    """
    lint_cmd = [sys.executable, "-m", "ruff", "check", target_path]
    fmt_cmd = [sys.executable, "-m", "ruff", "format", "--check", target_path]

    lint_result, fmt_result = await asyncio.gather(
        _run(lint_cmd, cwd=working_dir),
        _run(fmt_cmd, cwd=working_dir),
    )
    return f"=== ruff check ===\n{lint_result}\n=== ruff format --check ===\n{fmt_result}"


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

CODE_RUNNER_TOOLS = [run_pytest, run_ruff_check, run_ruff_format_check, run_ruff_all]
