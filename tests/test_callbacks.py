"""Unit tests for TimingCallbackHandler and ChainlitStepCallbackHandler."""

import logging
import time
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import scp_mcp_code_agent.callbacks as _cb_module
from scp_mcp_code_agent.callbacks import (
    ChainlitStepCallbackHandler,
    TimingCallbackHandler,
    _format_step_output,
    _is_tool_failure,
    _step_name,
)


def _run_id():
    return uuid.uuid4()


class TestTimingCallbackHandlerLLM:
    def test_llm_completion_logged(self, caplog):
        handler = TimingCallbackHandler()
        rid = _run_id()
        serialized = {"kwargs": {"model_name": "gpt-4o"}}

        with caplog.at_level(logging.INFO, logger="scp_agent.timing"):
            handler.on_llm_start(serialized, [], run_id=rid)
            handler.on_llm_end(MagicMock(), run_id=rid)

        assert any("LLM(gpt-4o)" in r.message and "completed" in r.message for r in caplog.records)

    def test_llm_error_logged(self, caplog):
        handler = TimingCallbackHandler()
        rid = _run_id()

        with caplog.at_level(logging.INFO, logger="scp_agent.timing"):
            handler.on_llm_start({"kwargs": {}}, [], run_id=rid)
            handler.on_llm_error(ValueError("boom"), run_id=rid)

        assert any("failed" in r.message and "boom" in r.message for r in caplog.records)

    def test_llm_elapsed_time_positive(self, caplog):
        handler = TimingCallbackHandler()
        rid = _run_id()

        with caplog.at_level(logging.INFO, logger="scp_agent.timing"):
            handler.on_llm_start({"kwargs": {}}, [], run_id=rid)
            time.sleep(0.01)
            handler.on_llm_end(MagicMock(), run_id=rid)

        record = next(r for r in caplog.records if "completed" in r.message)
        # Extract elapsed from "completed in X.XXs"
        parts = record.message.split("completed in ")
        elapsed = float(parts[1].replace("s", ""))
        assert elapsed >= 0.01

    def test_fallback_model_name_when_missing(self, caplog):
        handler = TimingCallbackHandler()
        rid = _run_id()

        with caplog.at_level(logging.INFO, logger="scp_agent.timing"):
            handler.on_llm_start({}, [], run_id=rid)
            handler.on_llm_end(MagicMock(), run_id=rid)

        assert any("LLM(llm)" in r.message for r in caplog.records)

    def test_unknown_run_id_end_does_not_raise(self):
        handler = TimingCallbackHandler()
        handler.on_llm_end(MagicMock(), run_id=_run_id())  # no matching start

    def test_unknown_run_id_error_does_not_raise(self):
        handler = TimingCallbackHandler()
        handler.on_llm_error(Exception(), run_id=_run_id())


class TestTimingCallbackHandlerTool:
    def test_tool_completion_logged(self, caplog):
        handler = TimingCallbackHandler()
        rid = _run_id()

        with caplog.at_level(logging.INFO, logger="scp_agent.timing"):
            handler.on_tool_start({"name": "run_pytest"}, "tests/", run_id=rid)
            handler.on_tool_end("output", run_id=rid)

        assert any("tool:run_pytest" in r.message and "completed" in r.message for r in caplog.records)

    def test_tool_error_logged(self, caplog):
        handler = TimingCallbackHandler()
        rid = _run_id()

        with caplog.at_level(logging.INFO, logger="scp_agent.timing"):
            handler.on_tool_start({"name": "read_file"}, "path", run_id=rid)
            handler.on_tool_error(RuntimeError("oops"), run_id=rid)

        assert any("tool:read_file" in r.message and "failed" in r.message for r in caplog.records)

    def test_fallback_tool_name_when_missing(self, caplog):
        handler = TimingCallbackHandler()
        rid = _run_id()

        with caplog.at_level(logging.INFO, logger="scp_agent.timing"):
            handler.on_tool_start({}, "", run_id=rid)
            handler.on_tool_end("", run_id=rid)

        assert any("tool:tool" in r.message for r in caplog.records)

    def test_multiple_concurrent_tools(self, caplog):
        handler = TimingCallbackHandler()
        rid1, rid2 = _run_id(), _run_id()

        with caplog.at_level(logging.INFO, logger="scp_agent.timing"):
            handler.on_tool_start({"name": "tool_a"}, "", run_id=rid1)
            handler.on_tool_start({"name": "tool_b"}, "", run_id=rid2)
            handler.on_tool_end("", run_id=rid1)
            handler.on_tool_end("", run_id=rid2)

        messages = [r.message for r in caplog.records]
        assert any("tool:tool_a" in m for m in messages)
        assert any("tool:tool_b" in m for m in messages)

    def test_run_id_cleaned_up_after_end(self):
        handler = TimingCallbackHandler()
        rid = _run_id()
        handler.on_tool_start({"name": "t"}, "", run_id=rid)
        handler.on_tool_end("", run_id=rid)
        assert rid not in handler._starts


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


class TestStepName:
    def test_unknown_tool_returns_tool_name(self):
        assert _step_name("unknown_tool", "{}") == "unknown_tool"

    def test_spec_endpoints_with_service(self):
        name = _step_name("get_openapi_spec_endpoints", '{"service_name": "block-storage"}')
        assert "block-storage" in name

    def test_spec_detail_with_service_and_ops(self):
        name = _step_name(
            "get_openapi_spec_detail",
            '{"service_name": "block-storage", "operation_ids": ["op1", "op2", "op3"]}',
        )
        assert "block-storage" in name
        assert "3" in name

    def test_read_file_shows_filename(self):
        name = _step_name("read_file", '{"path": "/home/user/mcp_code_example/server.py"}')
        assert "server.py" in name

    def test_read_multiple_files_shows_count(self):
        name = _step_name(
            "read_multiple_files",
            '{"paths": ["/a/server.py", "/a/tests/test_server.py"]}',
        )
        assert "2" in name

    def test_run_pytest_shows_dir_name(self):
        name = _step_name("run_pytest", '{"test_path": "generated/my_server/tests/"}')
        assert "tests" in name

    def test_run_ruff_all_shows_target(self):
        name = _step_name("run_ruff_all", '{"target_path": "generated/my_server/server.py"}')
        assert "server.py" in name

    def test_invalid_json_falls_back_to_base(self):
        name = _step_name("run_pytest", "not-json")
        assert name  # doesn't raise, returns base name


class TestIsToolFailure:
    def test_exit_code_zero_is_not_failure(self):
        assert not _is_tool_failure("run_pytest", "1 passed\n[exit code: 0]")

    def test_nonzero_exit_code_is_failure(self):
        assert _is_tool_failure("run_pytest", "FAILED test.py\n[exit code: 1]")

    def test_ruff_pass(self):
        assert not _is_tool_failure("run_ruff_all", "All checks passed.\n[exit code: 0]")

    def test_ruff_fail(self):
        assert _is_tool_failure("run_ruff_check", "E501 line too long\n[exit code: 1]")

    def test_non_runner_tool_never_fails(self):
        assert not _is_tool_failure("read_file", "some error text")


class TestFormatStepOutput:
    def test_short_output_unchanged(self):
        out = "1 passed in 0.5s\n[exit code: 0]"
        assert _format_step_output("run_pytest", out) == out

    def test_long_code_runner_shows_tail(self):
        long = "x" * 1000
        result = _format_step_output("run_pytest", long)
        assert result.startswith("...")
        assert result.endswith(long[-400:])

    def test_long_other_tool_shows_head(self):
        long = "y" * 1000
        result = _format_step_output("read_file", long)
        assert result.endswith("...")
        assert result.startswith(long[:400])


# ---------------------------------------------------------------------------
# ChainlitStepCallbackHandler
# ---------------------------------------------------------------------------


def _make_mock_step():
    step = MagicMock()
    step.__aenter__ = AsyncMock(return_value=step)
    step.__aexit__ = AsyncMock(return_value=None)
    step.input = None
    step.output = None
    step.is_error = False
    return step


def _make_mock_cl(mock_step):
    """Return a mock Chainlit module where cl.Step() returns mock_step."""
    mock_cl = MagicMock()
    mock_cl.Step.return_value = mock_step
    return mock_cl


class TestChainlitStepCallbackHandler:
    async def test_tracked_tool_opens_and_closes_step(self):
        mock_step = _make_mock_step()
        rid = _run_id()
        mock_cl = _make_mock_cl(mock_step)
        with patch.object(_cb_module, "_CHAINLIT_AVAILABLE", True), \
             patch.object(_cb_module, "cl", mock_cl):
            handler = ChainlitStepCallbackHandler()
            await handler.on_tool_start({"name": "run_pytest"}, '{"test_path": "tests/"}', run_id=rid)
            await handler.on_tool_end("1 passed\n[exit code: 0]", run_id=rid)

        mock_step.__aenter__.assert_called_once()
        mock_step.__aexit__.assert_called_once()

    async def test_untracked_tool_creates_no_step(self):
        rid = _run_id()
        mock_cl = _make_mock_cl(_make_mock_step())
        with patch.object(_cb_module, "_CHAINLIT_AVAILABLE", True), \
             patch.object(_cb_module, "cl", mock_cl):
            handler = ChainlitStepCallbackHandler()
            # gather_requirements is excluded (has HITL UI)
            await handler.on_tool_start({"name": "gather_requirements"}, "{}", run_id=rid)

        mock_cl.Step.assert_not_called()

    async def test_tool_error_marks_step_as_error(self):
        mock_step = _make_mock_step()
        rid = _run_id()
        with patch.object(_cb_module, "_CHAINLIT_AVAILABLE", True), \
             patch.object(_cb_module, "cl", _make_mock_cl(mock_step)):
            handler = ChainlitStepCallbackHandler()
            await handler.on_tool_start({"name": "run_ruff_all"}, '{"target_path": "server.py"}', run_id=rid)
            await handler.on_tool_error(RuntimeError("timeout"), run_id=rid)

        assert mock_step.is_error is True
        mock_step.__aexit__.assert_called_once()

    async def test_pytest_failure_sets_is_error(self):
        mock_step = _make_mock_step()
        rid = _run_id()
        with patch.object(_cb_module, "_CHAINLIT_AVAILABLE", True), \
             patch.object(_cb_module, "cl", _make_mock_cl(mock_step)):
            handler = ChainlitStepCallbackHandler()
            await handler.on_tool_start({"name": "run_pytest"}, '{"test_path": "tests/"}', run_id=rid)
            await handler.on_tool_end("FAILED test.py\n[exit code: 1]", run_id=rid)

        assert mock_step.is_error is True

    async def test_pytest_pass_does_not_set_is_error(self):
        mock_step = _make_mock_step()
        rid = _run_id()
        with patch.object(_cb_module, "_CHAINLIT_AVAILABLE", True), \
             patch.object(_cb_module, "cl", _make_mock_cl(mock_step)):
            handler = ChainlitStepCallbackHandler()
            await handler.on_tool_start({"name": "run_pytest"}, '{"test_path": "tests/"}', run_id=rid)
            await handler.on_tool_end("2 passed\n[exit code: 0]", run_id=rid)

        assert mock_step.is_error is False

    async def test_step_name_enriched_with_service(self):
        mock_step = _make_mock_step()
        rid = _run_id()
        mock_cl = _make_mock_cl(mock_step)
        with patch.object(_cb_module, "_CHAINLIT_AVAILABLE", True), \
             patch.object(_cb_module, "cl", mock_cl):
            handler = ChainlitStepCallbackHandler()
            await handler.on_tool_start(
                {"name": "get_openapi_spec_endpoints"},
                '{"service_name": "block-storage"}',
                run_id=rid,
            )
            await handler.on_tool_end("[]", run_id=rid)

        call_kwargs = mock_cl.Step.call_args
        name_used = call_kwargs[1].get("name") or call_kwargs[0][0]
        assert "block-storage" in name_used

    async def test_no_step_when_chainlit_unavailable(self):
        rid = _run_id()
        mock_cl = _make_mock_cl(_make_mock_step())
        with patch.object(_cb_module, "_CHAINLIT_AVAILABLE", False), \
             patch.object(_cb_module, "cl", mock_cl):
            handler = ChainlitStepCallbackHandler()
            await handler.on_tool_start({"name": "run_pytest"}, "{}", run_id=rid)

        mock_cl.Step.assert_not_called()

    async def test_orphaned_on_tool_end_does_not_raise(self):
        handler = ChainlitStepCallbackHandler()
        await handler.on_tool_end("output", run_id=_run_id())

    async def test_orphaned_on_tool_error_does_not_raise(self):
        handler = ChainlitStepCallbackHandler()
        await handler.on_tool_error(RuntimeError("x"), run_id=_run_id())

    async def test_step_cleaned_up_after_end(self):
        mock_step = _make_mock_step()
        rid = _run_id()
        with patch.object(_cb_module, "_CHAINLIT_AVAILABLE", True), \
             patch.object(_cb_module, "cl", _make_mock_cl(mock_step)):
            handler = ChainlitStepCallbackHandler()
            await handler.on_tool_start({"name": "run_pytest"}, "{}", run_id=rid)
            await handler.on_tool_end("done\n[exit code: 0]", run_id=rid)

        assert rid not in handler._steps
