"""Unit tests for TimingCallbackHandler."""

import logging
import time
import uuid
from unittest.mock import MagicMock

import pytest

from scp_mcp_code_agent.callbacks import TimingCallbackHandler


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
