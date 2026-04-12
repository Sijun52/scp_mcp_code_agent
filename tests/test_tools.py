"""Unit tests for code_runner custom LangChain tools.

These tests verify that run_pytest and run_ruff_check correctly
invoke the underlying subprocess commands and return their output.
"""

import sys
from unittest.mock import MagicMock, patch

import pytest

from scp_mcp_code_agent.tools.code_runner import (
    run_pytest,
    run_ruff_check,
    run_ruff_format_check,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_completed_process(stdout: str = "", stderr: str = "", returncode: int = 0):
    """Build a mock CompletedProcess returned by subprocess.run."""
    mock = MagicMock()
    mock.stdout = stdout
    mock.stderr = stderr
    mock.returncode = returncode
    return mock


# ---------------------------------------------------------------------------
# run_pytest
# ---------------------------------------------------------------------------


class TestRunPytest:
    def test_invokes_pytest_module(self):
        mock_proc = _make_completed_process(stdout="1 passed", returncode=0)

        with patch("scp_mcp_code_agent.tools.code_runner.subprocess.run", return_value=mock_proc) as mock_run:
            result = run_pytest.invoke({"test_path": "tests/", "working_dir": "."})

        cmd = mock_run.call_args.args[0]
        assert sys.executable in cmd
        assert "-m" in cmd
        assert "pytest" in cmd
        assert "tests/" in cmd

    def test_returns_stdout_and_exit_code(self):
        mock_proc = _make_completed_process(stdout="2 passed", returncode=0)

        with patch("scp_mcp_code_agent.tools.code_runner.subprocess.run", return_value=mock_proc):
            result = run_pytest.invoke({"test_path": "tests/"})

        assert "2 passed" in result
        assert "[exit code: 0]" in result

    def test_returns_stderr_on_failure(self):
        mock_proc = _make_completed_process(stderr="FAILED test_foo.py::test_bar", returncode=1)

        with patch("scp_mcp_code_agent.tools.code_runner.subprocess.run", return_value=mock_proc):
            result = run_pytest.invoke({"test_path": "tests/"})

        assert "FAILED" in result
        assert "[exit code: 1]" in result

    def test_uses_working_dir(self):
        mock_proc = _make_completed_process(returncode=0)

        with patch("scp_mcp_code_agent.tools.code_runner.subprocess.run", return_value=mock_proc) as mock_run:
            run_pytest.invoke({"test_path": "tests/", "working_dir": "/some/project"})

        assert mock_run.call_args.kwargs["cwd"] == "/some/project"


# ---------------------------------------------------------------------------
# run_ruff_check
# ---------------------------------------------------------------------------


class TestRunRuffCheck:
    def test_invokes_ruff_check(self):
        mock_proc = _make_completed_process(returncode=0)

        with patch("scp_mcp_code_agent.tools.code_runner.subprocess.run", return_value=mock_proc) as mock_run:
            run_ruff_check.invoke({"target_path": "server.py"})

        cmd = mock_run.call_args.args[0]
        assert "ruff" in cmd
        assert "check" in cmd
        assert "server.py" in cmd

    def test_exit_code_zero_on_clean(self):
        mock_proc = _make_completed_process(stdout="All checks passed.", returncode=0)

        with patch("scp_mcp_code_agent.tools.code_runner.subprocess.run", return_value=mock_proc):
            result = run_ruff_check.invoke({"target_path": "server.py"})

        assert "[exit code: 0]" in result

    def test_exit_code_nonzero_on_lint_errors(self):
        mock_proc = _make_completed_process(
            stdout="server.py:10:1: F401 [*] `os` imported but unused",
            returncode=1,
        )

        with patch("scp_mcp_code_agent.tools.code_runner.subprocess.run", return_value=mock_proc):
            result = run_ruff_check.invoke({"target_path": "server.py"})

        assert "F401" in result
        assert "[exit code: 1]" in result


# ---------------------------------------------------------------------------
# run_ruff_format_check
# ---------------------------------------------------------------------------


class TestRunRuffFormatCheck:
    def test_invokes_ruff_format_check(self):
        mock_proc = _make_completed_process(returncode=0)

        with patch("scp_mcp_code_agent.tools.code_runner.subprocess.run", return_value=mock_proc) as mock_run:
            run_ruff_format_check.invoke({"target_path": "server.py"})

        cmd = mock_run.call_args.args[0]
        assert "format" in cmd
        assert "--check" in cmd

    def test_would_reformat_message_on_failure(self):
        mock_proc = _make_completed_process(
            stdout="Would reformat: server.py",
            returncode=1,
        )

        with patch("scp_mcp_code_agent.tools.code_runner.subprocess.run", return_value=mock_proc):
            result = run_ruff_format_check.invoke({"target_path": "server.py"})

        assert "reformat" in result
        assert "[exit code: 1]" in result
