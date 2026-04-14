"""Unit tests for HITL middleware classes."""

from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import ToolMessage

from scp_mcp_code_agent.middleware import (
    GatherRequirementsMiddleware,
    OpenAPISpecConfirmMiddleware,
    TestFailureHandlerMiddleware,
    WriteFileConfirmMiddleware,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------




def _make_request(name: str, args: dict | None = None, tool_id: str = "call_1"):
    req = MagicMock()
    req.name = name
    req.args = args or {}
    req.id = tool_id
    return req


def _make_handler(content: str = "result"):
    msg = ToolMessage(content=content, tool_call_id="call_1")
    return MagicMock(return_value=msg)


# ---------------------------------------------------------------------------
# OpenAPISpecConfirmMiddleware
# ---------------------------------------------------------------------------


class TestOpenAPISpecConfirmMiddleware:
    def test_passthrough_for_non_spec_tool(self):
        mw = OpenAPISpecConfirmMiddleware()
        req = _make_request("read_file")
        handler = _make_handler("file content")

        result = mw.wrap_tool_call(req, handler)

        handler.assert_called_once_with(req)
        assert result.content == "file content"

    def test_approve_returns_original_result(self):
        mw = OpenAPISpecConfirmMiddleware()
        req = _make_request("get_openapi_spec")
        handler = _make_handler("openapi spec content")

        with patch("scp_mcp_code_agent.middleware.openapi_confirm.interrupt", return_value="approve"):
            result = mw.wrap_tool_call(req, handler)

        assert result.content == "openapi spec content"

    def test_reject_returns_rejection_message(self):
        mw = OpenAPISpecConfirmMiddleware()
        req = _make_request("get_openapi_spec")
        handler = _make_handler("spec")

        with patch("scp_mcp_code_agent.middleware.openapi_confirm.interrupt", return_value="reject"):
            result = mw.wrap_tool_call(req, handler)

        assert "거절" in result.content or "중단" in result.content
        assert isinstance(result, ToolMessage)

    def test_interrupt_receives_spec_preview(self):
        mw = OpenAPISpecConfirmMiddleware()
        long_spec = "x" * 5000
        req = _make_request("get_openapi_spec")
        handler = MagicMock(return_value=ToolMessage(content=long_spec, tool_call_id="call_1"))

        with patch("scp_mcp_code_agent.middleware.openapi_confirm.interrupt", return_value="approve") as mock_interrupt:
            mw.wrap_tool_call(req, handler)

        payload = mock_interrupt.call_args.args[0]
        assert payload["type"] == "openapi_confirm"
        assert len(payload["spec_preview"]) <= 3000

    def test_result_without_content_attr(self):
        mw = OpenAPISpecConfirmMiddleware()
        req = _make_request("get_openapi_spec")
        plain_result = "plain string result"
        handler = MagicMock(return_value=plain_result)

        with patch("scp_mcp_code_agent.middleware.openapi_confirm.interrupt", return_value="approve"):
            result = mw.wrap_tool_call(req, handler)

        assert result == plain_result


# ---------------------------------------------------------------------------
# WriteFileConfirmMiddleware
# ---------------------------------------------------------------------------


class TestWriteFileConfirmMiddleware:
    def test_passthrough_for_non_write_tool(self):
        mw = WriteFileConfirmMiddleware()
        req = _make_request("read_file")
        handler = _make_handler()

        mw.wrap_tool_call(req, handler)
        handler.assert_called_once_with(req)

    def test_passthrough_for_non_py_extension(self):
        mw = WriteFileConfirmMiddleware()
        req = _make_request("write_file", {"path": "README.md", "content": "x" * 100})
        handler = _make_handler()

        mw.wrap_tool_call(req, handler)
        handler.assert_called_once()

    def test_passthrough_for_short_content(self):
        mw = WriteFileConfirmMiddleware()
        req = _make_request("write_file", {"path": "f.py", "content": "x"})
        handler = _make_handler()

        mw.wrap_tool_call(req, handler)
        handler.assert_called_once()

    def test_approve_saves_file(self, tmp_path):
        mw = WriteFileConfirmMiddleware()
        py_path = str(tmp_path / "server.py")
        req = _make_request("write_file", {"path": py_path, "content": "x" * 100})
        handler = _make_handler("written")

        with patch("scp_mcp_code_agent.middleware.write_file_confirm.interrupt", return_value="approve"):
            result = mw.wrap_tool_call(req, handler)

        handler.assert_called_once_with(req)
        assert result.content == "written"

    def test_reject_returns_cancel_message(self, tmp_path):
        mw = WriteFileConfirmMiddleware()
        py_path = str(tmp_path / "server.py")
        req = _make_request("write_file", {"path": py_path, "content": "x" * 100})
        handler = _make_handler()

        with patch("scp_mcp_code_agent.middleware.write_file_confirm.interrupt", return_value="reject"):
            result = mw.wrap_tool_call(req, handler)

        handler.assert_not_called()
        assert "취소" in result.content

    def test_edit_decision_replaces_content(self, tmp_path):
        mw = WriteFileConfirmMiddleware()
        py_path = str(tmp_path / "server.py")
        req = _make_request("write_file", {"path": py_path, "content": "x" * 100})
        handler = _make_handler("written")

        with patch(
            "scp_mcp_code_agent.middleware.write_file_confirm.interrupt",
            return_value={"content": "new content"},
        ):
            mw.wrap_tool_call(req, handler)

        assert req.args["content"] == "new content"

    def test_file_exists_flag_in_interrupt_payload(self, tmp_path):
        mw = WriteFileConfirmMiddleware()
        existing = tmp_path / "server.py"
        existing.write_text("old", encoding="utf-8")

        req = _make_request("write_file", {"path": str(existing), "content": "x" * 100})
        handler = _make_handler()

        with patch("scp_mcp_code_agent.middleware.write_file_confirm.interrupt", return_value="approve") as mock_interrupt:
            mw.wrap_tool_call(req, handler)

        payload = mock_interrupt.call_args.args[0]
        assert payload["file_exists"] is True


# ---------------------------------------------------------------------------
# TestFailureHandlerMiddleware
# ---------------------------------------------------------------------------


class TestTestFailureHandlerMiddleware:
    def test_passthrough_for_non_pytest_tool(self):
        mw = TestFailureHandlerMiddleware()
        req = _make_request("run_ruff_check")
        handler = _make_handler("ok\n[exit code: 0]")

        result = mw.wrap_tool_call(req, handler)
        handler.assert_called_once_with(req)

    def test_success_resets_failure_count(self):
        mw = TestFailureHandlerMiddleware()
        mw._failure_count = 2
        req = _make_request("run_pytest")
        handler = _make_handler("1 passed\n[exit code: 0]")

        mw.wrap_tool_call(req, handler)
        assert mw._failure_count == 0

    def test_first_two_failures_return_result_without_interrupt(self):
        mw = TestFailureHandlerMiddleware()
        req = _make_request("run_pytest")
        handler = _make_handler("FAILED\n[exit code: 1]")

        with patch("scp_mcp_code_agent.middleware.test_failure.interrupt") as mock_interrupt:
            mw.wrap_tool_call(req, handler)
            mw.wrap_tool_call(req, handler)
            mock_interrupt.assert_not_called()

        assert mw._failure_count == 2

    def test_third_failure_triggers_interrupt(self):
        mw = TestFailureHandlerMiddleware()
        req = _make_request("run_pytest")
        handler = _make_handler("FAILED\n[exit code: 1]")

        with patch("scp_mcp_code_agent.middleware.test_failure.interrupt", return_value="retry"):
            for _ in range(3):
                mw.wrap_tool_call(req, handler)

    def test_retry_decision_resets_count_and_appends_message(self):
        mw = TestFailureHandlerMiddleware()
        mw._failure_count = 2
        req = _make_request("run_pytest")
        handler = _make_handler("FAILED\n[exit code: 1]")

        with patch("scp_mcp_code_agent.middleware.test_failure.interrupt", return_value="retry"):
            result = mw.wrap_tool_call(req, handler)

        assert mw._failure_count == 0
        assert "재시도" in result.content

    def test_save_as_is_decision(self):
        mw = TestFailureHandlerMiddleware()
        mw._failure_count = 2
        req = _make_request("run_pytest")
        handler = _make_handler("FAILED\n[exit code: 1]")

        with patch("scp_mcp_code_agent.middleware.test_failure.interrupt", return_value="save_as_is"):
            result = mw.wrap_tool_call(req, handler)

        assert "저장" in result.content

    def test_abort_decision(self):
        mw = TestFailureHandlerMiddleware()
        mw._failure_count = 2
        req = _make_request("run_pytest")
        handler = _make_handler("FAILED\n[exit code: 1]")

        with patch("scp_mcp_code_agent.middleware.test_failure.interrupt", return_value="abort"):
            result = mw.wrap_tool_call(req, handler)

        assert "중단" in result.content

    def test_failure_count_increments_each_failure(self):
        mw = TestFailureHandlerMiddleware()
        req = _make_request("run_pytest")
        handler = _make_handler("FAILED\n[exit code: 1]")

        with patch("scp_mcp_code_agent.middleware.test_failure.interrupt", return_value="abort"):
            for i in range(1, 4):
                mw.wrap_tool_call(req, handler)


# ---------------------------------------------------------------------------
# GatherRequirementsMiddleware
# ---------------------------------------------------------------------------


class TestGatherRequirementsMiddleware:
    def test_passthrough_for_non_gather_tool(self):
        mw = GatherRequirementsMiddleware()
        req = _make_request("read_file")
        handler = _make_handler("file content")

        result = mw.wrap_tool_call(req, handler)

        handler.assert_called_once_with(req)
        assert result.content == "file content"

    def test_intercepts_gather_requirements_tool(self):
        mw = GatherRequirementsMiddleware()
        req = _make_request(
            "gather_requirements",
            args={
                "service_name": "block storage",
                "questions": ["주로 어떤 작업?", "인증 방식은?"],
            },
        )
        handler = _make_handler("should not be called")

        with patch(
            "scp_mcp_code_agent.middleware.gather_requirements.interrupt",
            return_value="Q1. 주로 어떤 작업?\nA1. 자동화\nQ2. 인증 방식은?\nA2. API Key",
        ):
            result = mw.wrap_tool_call(req, handler)

        # 핸들러는 호출되지 않아야 함
        handler.assert_not_called()
        assert isinstance(result, ToolMessage)

    def test_result_contains_collected_answers(self):
        mw = GatherRequirementsMiddleware()
        req = _make_request(
            "gather_requirements",
            args={"service_name": "svc", "questions": ["Q?"]},
        )
        handler = _make_handler()
        answers = "Q1. Q?\nA1. 자동화 위주"

        with patch(
            "scp_mcp_code_agent.middleware.gather_requirements.interrupt",
            return_value=answers,
        ):
            result = mw.wrap_tool_call(req, handler)

        assert answers in result.content

    def test_interrupt_called_with_correct_type(self):
        mw = GatherRequirementsMiddleware()
        questions = ["Q1?", "Q2?"]
        req = _make_request(
            "gather_requirements",
            args={"service_name": "block storage", "questions": questions},
        )
        handler = _make_handler()

        with patch(
            "scp_mcp_code_agent.middleware.gather_requirements.interrupt",
            return_value="answers",
        ) as mock_interrupt:
            mw.wrap_tool_call(req, handler)

        call_arg = mock_interrupt.call_args[0][0]
        assert call_arg["type"] == "gather_requirements"
        assert call_arg["service_name"] == "block storage"
        assert call_arg["questions"] == questions
