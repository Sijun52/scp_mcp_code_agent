"""Unit tests for code_runner custom LangChain tools.

These tests verify that run_pytest and run_ruff_check correctly
invoke the underlying subprocess commands and return their output.
"""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scp_mcp_code_agent.tools.code_runner import (
    run_pytest,
    run_ruff_all,
    run_ruff_check,
    run_ruff_format_check,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_proc(stdout: str = "", stderr: str = "", returncode: int = 0):
    """Build a mock async subprocess returned by asyncio.create_subprocess_exec."""
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(
        return_value=(stdout.encode(), stderr.encode())
    )
    return proc


def _patch_proc(stdout: str = "", stderr: str = "", returncode: int = 0):
    return patch(
        "asyncio.create_subprocess_exec",
        new=AsyncMock(return_value=_make_proc(stdout, stderr, returncode)),
    )


# ---------------------------------------------------------------------------
# run_pytest
# ---------------------------------------------------------------------------


class TestRunPytest:
    async def test_invokes_pytest_module(self):
        with _patch_proc(stdout="1 passed", returncode=0) as mock_exec:
            await run_pytest.ainvoke({"test_path": "tests/", "working_dir": "."})

        cmd = mock_exec.call_args.args
        assert sys.executable in cmd
        assert "-m" in cmd
        assert "pytest" in cmd
        assert "tests/" in cmd

    async def test_returns_stdout_and_exit_code(self):
        with _patch_proc(stdout="2 passed", returncode=0):
            result = await run_pytest.ainvoke({"test_path": "tests/"})

        assert "2 passed" in result
        assert "[exit code: 0]" in result

    async def test_returns_stderr_on_failure(self):
        with _patch_proc(stderr="FAILED test_foo.py::test_bar", returncode=1):
            result = await run_pytest.ainvoke({"test_path": "tests/"})

        assert "FAILED" in result
        assert "[exit code: 1]" in result

    async def test_uses_working_dir(self):
        with _patch_proc(returncode=0) as mock_exec:
            await run_pytest.ainvoke({"test_path": "tests/", "working_dir": "/some/project"})

        assert mock_exec.call_args.kwargs["cwd"] == "/some/project"


# ---------------------------------------------------------------------------
# run_ruff_check
# ---------------------------------------------------------------------------


class TestRunRuffCheck:
    async def test_invokes_ruff_check(self):
        with _patch_proc(returncode=0) as mock_exec:
            await run_ruff_check.ainvoke({"target_path": "server.py"})

        cmd = mock_exec.call_args.args
        assert "ruff" in cmd
        assert "check" in cmd
        assert "server.py" in cmd

    async def test_exit_code_zero_on_clean(self):
        with _patch_proc(stdout="All checks passed.", returncode=0):
            result = await run_ruff_check.ainvoke({"target_path": "server.py"})

        assert "[exit code: 0]" in result

    async def test_exit_code_nonzero_on_lint_errors(self):
        with _patch_proc(stdout="server.py:10:1: F401 [*] `os` imported but unused", returncode=1):
            result = await run_ruff_check.ainvoke({"target_path": "server.py"})

        assert "F401" in result
        assert "[exit code: 1]" in result


# ---------------------------------------------------------------------------
# run_ruff_format_check
# ---------------------------------------------------------------------------


class TestRunRuffAll:
    async def test_runs_both_check_and_format(self):
        with _patch_proc(stdout="ok", returncode=0) as mock_exec:
            result = await run_ruff_all.ainvoke({"target_path": "server.py"})

        assert mock_exec.call_count == 2
        assert "ruff check" in result
        assert "ruff format --check" in result

    async def test_combined_output_contains_both_sections(self):
        with _patch_proc(stdout="All good", returncode=0):
            result = await run_ruff_all.ainvoke({"target_path": "server.py"})

        assert "=== ruff check ===" in result
        assert "=== ruff format --check ===" in result

    async def test_exit_codes_included_in_output(self):
        with _patch_proc(returncode=1):
            result = await run_ruff_all.ainvoke({"target_path": "server.py"})

        assert result.count("[exit code: 1]") == 2


class TestRunRuffFormatCheck:
    async def test_invokes_ruff_format_check(self):
        with _patch_proc(returncode=0) as mock_exec:
            await run_ruff_format_check.ainvoke({"target_path": "server.py"})

        cmd = mock_exec.call_args.args
        assert "format" in cmd
        assert "--check" in cmd

    async def test_would_reformat_message_on_failure(self):
        with _patch_proc(stdout="Would reformat: server.py", returncode=1):
            result = await run_ruff_format_check.ainvoke({"target_path": "server.py"})

        assert "reformat" in result
        assert "[exit code: 1]" in result
