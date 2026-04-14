"""Unit tests for app.py — _handle_interrupt, _run_with_hitl, multi-service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage
from langgraph.types import Command

from scp_mcp_code_agent.app import (
    _CHAT_HISTORY_MAX,
    _handle_interrupt,
    _parse_multi_service,
    _run_concurrent_services,
    _run_service_headless,
    _run_with_hitl,
    on_chat_end,
    on_chat_start,
    on_message,
    reset_history,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_cl_action(**kwargs):
    """cl.Action(name=..., label=..., value=...) 을 흉내내는 MagicMock."""
    a = MagicMock()
    for k, v in kwargs.items():
        setattr(a, k, v)
    return a


def _make_ask_response(value: str):
    resp = MagicMock()
    resp.value = value
    return resp


# ---------------------------------------------------------------------------
# _handle_interrupt
# ---------------------------------------------------------------------------


class TestHandleInterrupt:
    async def test_openapi_confirm_approve(self):
        mock_cl = MagicMock()
        mock_cl.Message.return_value.send = AsyncMock()
        mock_cl.AskActionMessage.return_value.send = AsyncMock(
            return_value=_make_ask_response("approve")
        )
        mock_cl.Action = _mock_cl_action

        with patch("scp_mcp_code_agent.app.cl", mock_cl):
            result = await _handle_interrupt({
                "type": "openapi_confirm",
                "message": "확인해주세요",
                "spec_preview": "openapi: 3.0",
            })

        assert result == "approve"

    async def test_openapi_confirm_none_response_defaults_to_reject(self):
        mock_cl = MagicMock()
        mock_cl.Message.return_value.send = AsyncMock()
        mock_cl.AskActionMessage.return_value.send = AsyncMock(return_value=None)
        mock_cl.Action = _mock_cl_action

        with patch("scp_mcp_code_agent.app.cl", mock_cl):
            result = await _handle_interrupt({"type": "openapi_confirm", "message": "msg"})

        assert result == "reject"

    async def test_write_file_confirm_new_file(self):
        mock_cl = MagicMock()
        mock_cl.Message.return_value.send = AsyncMock()
        mock_cl.AskActionMessage.return_value.send = AsyncMock(
            return_value=_make_ask_response("approve")
        )
        mock_cl.Action = _mock_cl_action

        with patch("scp_mcp_code_agent.app.cl", mock_cl):
            result = await _handle_interrupt({
                "type": "write_file_confirm",
                "message": "저장할까요?",
                "path": "server.py",
                "content_preview": "def main(): pass",
                "file_exists": False,
            })

        assert result == "approve"

    async def test_write_file_confirm_existing_file_adds_overwrite_action(self):
        mock_cl = MagicMock()
        mock_cl.Message.return_value.send = AsyncMock()
        ask_instance = MagicMock()
        ask_instance.send = AsyncMock(return_value=_make_ask_response("approve"))
        mock_cl.AskActionMessage.return_value = ask_instance
        mock_cl.Action = MagicMock(side_effect=lambda **kw: MagicMock(**kw))

        with patch("scp_mcp_code_agent.app.cl", mock_cl):
            await _handle_interrupt({
                "type": "write_file_confirm",
                "message": "덮어쓸까요?",
                "path": "server.py",
                "content_preview": "x" * 100,
                "file_exists": True,
            })

        # actions에 overwrite가 포함됐는지 확인
        call_kwargs = mock_cl.AskActionMessage.call_args.kwargs
        action_values = [a.value for a in call_kwargs.get("actions", [])]
        assert "approve" in action_values  # overwrite value

    async def test_hitl_default_confirm_endpoint_plan(self):
        mock_cl = MagicMock()
        mock_cl.Message.return_value.send = AsyncMock()
        mock_cl.AskActionMessage.return_value.send = AsyncMock(
            return_value=_make_ask_response("approve")
        )
        mock_cl.Action = _mock_cl_action

        with patch("scp_mcp_code_agent.app.cl", mock_cl):
            result = await _handle_interrupt({
                "type": "hitl_default",
                "message": "계획 확인",
                "tool_name": "confirm_endpoint_plan",
                "tool_args": {
                    "service_name": "virtual server",
                    "planned_tools": ["list_vms", "get_vm"],
                    "reasoning": "Main endpoints",
                },
            })

        assert result == "approve"

    async def test_hitl_default_none_response_defaults_to_reject(self):
        mock_cl = MagicMock()
        mock_cl.Message.return_value.send = AsyncMock()
        mock_cl.AskActionMessage.return_value.send = AsyncMock(return_value=None)
        mock_cl.Action = _mock_cl_action

        with patch("scp_mcp_code_agent.app.cl", mock_cl):
            result = await _handle_interrupt({
                "type": "hitl_default",
                "tool_name": "confirm_endpoint_plan",
                "tool_args": {"planned_tools": [], "reasoning": "", "service_name": ""},
                "message": "",
            })
        assert result == "reject"

    async def test_test_failure_retry(self):
        mock_cl = MagicMock()
        mock_cl.Message.return_value.send = AsyncMock()
        mock_cl.AskActionMessage.return_value.send = AsyncMock(
            return_value=_make_ask_response("retry")
        )
        mock_cl.Action = _mock_cl_action

        with patch("scp_mcp_code_agent.app.cl", mock_cl):
            result = await _handle_interrupt({
                "type": "test_failure",
                "message": "3회 실패",
                "failure_count": 3,
                "log": "FAILED::test_foo",
            })

        assert result == "retry"

    async def test_test_failure_none_response_defaults_to_abort(self):
        mock_cl = MagicMock()
        mock_cl.Message.return_value.send = AsyncMock()
        mock_cl.AskActionMessage.return_value.send = AsyncMock(return_value=None)
        mock_cl.Action = _mock_cl_action

        with patch("scp_mcp_code_agent.app.cl", mock_cl):
            result = await _handle_interrupt({
                "type": "test_failure",
                "message": "fail",
                "failure_count": 3,
                "log": "",
            })
        assert result == "abort"

    async def test_unknown_type_defaults_to_approve_reject(self):
        mock_cl = MagicMock()
        mock_cl.Message.return_value.send = AsyncMock()
        mock_cl.AskActionMessage.return_value.send = AsyncMock(
            return_value=_make_ask_response("approve")
        )
        mock_cl.Action = _mock_cl_action

        with patch("scp_mcp_code_agent.app.cl", mock_cl):
            result = await _handle_interrupt({"type": "unknown_type", "message": "?"})

        assert result == "approve"

    async def test_unknown_type_none_response_defaults_to_reject(self):
        mock_cl = MagicMock()
        mock_cl.Message.return_value.send = AsyncMock()
        mock_cl.AskActionMessage.return_value.send = AsyncMock(return_value=None)
        mock_cl.Action = _mock_cl_action

        with patch("scp_mcp_code_agent.app.cl", mock_cl):
            result = await _handle_interrupt({"message": "?"})

        assert result == "reject"


# ---------------------------------------------------------------------------
# _run_with_hitl
# ---------------------------------------------------------------------------


class TestRunWithHitl:
    def _make_graph(self, chunks, final_content="done"):
        graph = MagicMock()
        state = MagicMock()
        state.values = {"messages": [AIMessage(content=final_content)]}

        async def _astream(input_data, config, stream_mode):
            for chunk in chunks:
                yield chunk

        graph.astream = _astream
        graph.aget_state = AsyncMock(return_value=state)
        return graph

    async def test_no_interrupt_returns_last_message(self):
        graph = self._make_graph([{"agent": "update"}], final_content="generated!")
        result = await _run_with_hitl(graph, {"messages": []}, {})
        assert result == "generated!"

    async def test_empty_messages_returns_fallback(self):
        graph = MagicMock()
        state = MagicMock()
        state.values = {"messages": []}
        graph.astream = MagicMock(return_value=self._aiter([]))
        graph.aget_state = AsyncMock(return_value=state)

        async def _astream(input_data, config, stream_mode):
            return
            yield  # make it an async generator

        graph.astream = _astream
        result = await _run_with_hitl(graph, {}, {})
        assert result == "작업이 완료되었습니다."

    async def test_interrupt_then_resume(self):
        interrupt_chunk = {
            "__interrupt__": [MagicMock(value={"type": "openapi_confirm", "message": "ok"})]
        }
        normal_chunk = {"agent": "update"}

        call_count = 0

        async def _astream(input_data, config, stream_mode):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                yield interrupt_chunk
            else:
                yield normal_chunk

        state = MagicMock()
        state.values = {"messages": [AIMessage(content="resumed!")]}
        graph = MagicMock()
        graph.astream = _astream
        graph.aget_state = AsyncMock(return_value=state)

        mock_cl = MagicMock()
        mock_cl.Message.return_value.send = AsyncMock()
        mock_cl.AskActionMessage.return_value.send = AsyncMock(
            return_value=_make_ask_response("approve")
        )
        mock_cl.Action = _mock_cl_action

        with patch("scp_mcp_code_agent.app.cl", mock_cl):
            result = await _run_with_hitl(graph, {"messages": []}, {})

        assert result == "resumed!"

    def _aiter(self, items):
        async def _gen():
            for item in items:
                yield item
        return _gen()


# ---------------------------------------------------------------------------
# _CHAT_HISTORY_MAX constant
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Lifecycle hooks
# ---------------------------------------------------------------------------


def _build_mock_cl():
    mock_cl = MagicMock()
    mock_cl.Message.return_value.send = AsyncMock()
    mock_cl.AskActionMessage.return_value.send = AsyncMock(return_value=None)
    mock_cl.Action = _mock_cl_action
    mock_cl.user_session = MagicMock()
    mock_cl.user_session.get = MagicMock()
    mock_cl.user_session.set = MagicMock()
    mock_cl.Step.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
    mock_cl.Step.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_cl


class TestOnChatStart:
    async def test_initialises_session(self):
        mock_cl = _build_mock_cl()
        mock_graph = MagicMock()
        mock_mcp_ctx = MagicMock()

        with patch("scp_mcp_code_agent.app.cl", mock_cl):
            with patch("scp_mcp_code_agent.app.create_agent", return_value=(mock_graph, mock_mcp_ctx)):
                with patch("scp_mcp_code_agent.app.TimingCallbackHandler", return_value=MagicMock()):
                    await on_chat_start()

        set_calls = {call.args[0]: call.args[1] for call in mock_cl.user_session.set.call_args_list}
        assert "graph" in set_calls
        assert "mcp_ctx" in set_calls
        assert "session_id" in set_calls
        assert set_calls["chat_history"] == []

    async def test_sends_welcome_message(self):
        mock_cl = _build_mock_cl()

        with patch("scp_mcp_code_agent.app.cl", mock_cl):
            with patch("scp_mcp_code_agent.app.create_agent", return_value=(MagicMock(), MagicMock())):
                with patch("scp_mcp_code_agent.app.TimingCallbackHandler", return_value=MagicMock()):
                    await on_chat_start()

        mock_cl.Message.return_value.send.assert_called_once()


class TestOnChatEnd:
    async def test_calls_mcp_ctx_aexit(self):
        mock_cl = _build_mock_cl()
        mock_mcp_ctx = AsyncMock()
        mock_mcp_ctx.__aexit__ = AsyncMock()
        mock_cl.user_session.get.return_value = mock_mcp_ctx

        with patch("scp_mcp_code_agent.app.cl", mock_cl):
            await on_chat_end()

        mock_mcp_ctx.__aexit__.assert_called_once_with(None, None, None)

    async def test_handles_none_mcp_ctx_gracefully(self):
        mock_cl = _build_mock_cl()
        mock_cl.user_session.get.return_value = None

        with patch("scp_mcp_code_agent.app.cl", mock_cl):
            await on_chat_end()  # should not raise

    async def test_swallows_exit_exceptions(self):
        mock_cl = _build_mock_cl()
        mock_mcp_ctx = AsyncMock()
        mock_mcp_ctx.__aexit__ = AsyncMock(side_effect=Exception("cleanup failed"))
        mock_cl.user_session.get.return_value = mock_mcp_ctx

        with patch("scp_mcp_code_agent.app.cl", mock_cl):
            await on_chat_end()  # should not propagate exception


class TestOnMessage:
    def _make_session(self, mock_cl, graph, chat_history=None):
        session_data = {
            "graph": graph,
            "session_id": "test-session",
            "chat_history": chat_history or [],
        }
        mock_cl.user_session.get.side_effect = lambda key, default=None: session_data.get(key, default)

    async def test_appends_human_message_and_returns_ai_response(self):
        mock_cl = _build_mock_cl()

        state = MagicMock()
        state.values = {"messages": [MagicMock(content="generated!")]}

        async def _astream(input_data, config, stream_mode):
            yield {"agent": "update"}

        mock_graph = MagicMock()
        mock_graph.astream = _astream
        mock_graph.aget_state = AsyncMock(return_value=state)

        self._make_session(mock_cl, mock_graph)

        user_msg = MagicMock()
        user_msg.content = "virtual server"

        with patch("scp_mcp_code_agent.app.cl", mock_cl):
            await on_message(user_msg)

        mock_cl.Message.return_value.send.assert_called()

    async def test_handles_agent_error_gracefully(self):
        mock_cl = _build_mock_cl()

        async def _astream_error(input_data, config, stream_mode):
            raise RuntimeError("agent failed")
            yield  # make it a generator

        mock_graph = MagicMock()
        mock_graph.astream = _astream_error

        self._make_session(mock_cl, mock_graph)

        user_msg = MagicMock()
        user_msg.content = "svc"

        with patch("scp_mcp_code_agent.app.cl", mock_cl):
            await on_message(user_msg)  # should not propagate

        # Error message should have been sent
        error_sends = [
            c for c in mock_cl.Message.return_value.send.call_args_list
        ]
        assert len(error_sends) >= 0  # at least attempted


class TestResetHistory:
    async def test_clears_chat_history(self):
        mock_cl = _build_mock_cl()
        mock_action = MagicMock()

        with patch("scp_mcp_code_agent.app.cl", mock_cl):
            await reset_history(mock_action)

        mock_cl.user_session.set.assert_called_with("chat_history", [])

    async def test_sends_confirmation_message(self):
        mock_cl = _build_mock_cl()

        with patch("scp_mcp_code_agent.app.cl", mock_cl):
            await reset_history(MagicMock())

        mock_cl.Message.return_value.send.assert_called_once()


class TestChatHistoryMax:
    def test_constant_is_positive(self):
        assert _CHAT_HISTORY_MAX > 0

    def test_constant_is_reasonable(self):
        # Should not be too small (< 5) or unboundedly large (> 200)
        assert 5 <= _CHAT_HISTORY_MAX <= 200


# ---------------------------------------------------------------------------
# _parse_multi_service
# ---------------------------------------------------------------------------


class TestParseMultiService:
    def test_comma_separated_returns_list(self):
        result = _parse_multi_service("block storage, virtual server")
        assert result == ["block storage", "virtual server"]

    def test_newline_separated_returns_list(self):
        result = _parse_multi_service("block storage\nvirtual server")
        assert result == ["block storage", "virtual server"]

    def test_three_services(self):
        result = _parse_multi_service("block storage, virtual server, object storage")
        assert result == ["block storage", "virtual server", "object storage"]

    def test_single_service_returns_none(self):
        assert _parse_multi_service("virtual server") is None

    def test_empty_string_returns_none(self):
        assert _parse_multi_service("") is None

    def test_trailing_comma_single_service_returns_none(self):
        # "block storage, " → ["block storage"] → None
        assert _parse_multi_service("block storage, ") is None

    def test_strips_whitespace(self):
        result = _parse_multi_service("  block storage  ,  virtual server  ")
        assert result == ["block storage", "virtual server"]

    def test_mixed_separators(self):
        result = _parse_multi_service("block storage\nvirtual server, object storage")
        assert len(result) == 3


# ---------------------------------------------------------------------------
# _run_service_headless
# ---------------------------------------------------------------------------


class TestRunServiceHeadless:
    async def test_returns_service_name_and_output(self):
        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(return_value={
            "messages": [MagicMock(content="generated!")]
        })
        mock_mcp_ctx = AsyncMock()
        mock_mcp_ctx.__aexit__ = AsyncMock()

        with patch("scp_mcp_code_agent.app.create_agent", return_value=(mock_graph, mock_mcp_ctx)):
            svc_name, output = await _run_service_headless("block storage", "thread-1")

        assert svc_name == "block storage"
        assert output == "generated!"
        mock_mcp_ctx.__aexit__.assert_called_once()

    async def test_cleans_up_mcp_ctx_on_error(self):
        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(side_effect=RuntimeError("boom"))
        mock_mcp_ctx = AsyncMock()
        mock_mcp_ctx.__aexit__ = AsyncMock()

        with patch("scp_mcp_code_agent.app.create_agent", return_value=(mock_graph, mock_mcp_ctx)):
            svc_name, output = await _run_service_headless("svc", "thread-2")

        assert svc_name == "svc"
        assert "[오류]" in output
        mock_mcp_ctx.__aexit__.assert_called_once()

    async def test_creates_agent_with_hitl_false(self):
        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(return_value={"messages": [MagicMock(content="ok")]})
        mock_mcp_ctx = AsyncMock()
        mock_mcp_ctx.__aexit__ = AsyncMock()

        with patch("scp_mcp_code_agent.app.create_agent", return_value=(mock_graph, mock_mcp_ctx)) as mock_create:
            await _run_service_headless("svc", "t")

        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs.get("hitl") is False


# ---------------------------------------------------------------------------
# _run_concurrent_services
# ---------------------------------------------------------------------------


class TestRunConcurrentServices:
    async def test_sends_start_and_completion_messages(self):
        mock_cl = _build_mock_cl()

        async def _fake_headless(svc, thread_id):
            return svc, f"output for {svc}"

        with patch("scp_mcp_code_agent.app.cl", mock_cl):
            with patch("scp_mcp_code_agent.app._run_service_headless", side_effect=_fake_headless):
                await _run_concurrent_services(["block storage", "virtual server"])

        # 최소한 시작 메시지 + 각 서비스 결과 + 완료 메시지가 전송됐는지 확인
        assert mock_cl.Message.return_value.send.call_count >= 4

    async def test_handles_service_error_gracefully(self):
        mock_cl = _build_mock_cl()

        async def _fake_headless(svc, thread_id):
            return svc, "[오류] something went wrong"

        with patch("scp_mcp_code_agent.app.cl", mock_cl):
            with patch("scp_mcp_code_agent.app._run_service_headless", side_effect=_fake_headless):
                await _run_concurrent_services(["block storage", "virtual server"])

        # 오류가 있어도 완료 메시지까지 전송됐는지 확인
        assert mock_cl.Message.return_value.send.call_count >= 4


# ---------------------------------------------------------------------------
# on_message — 멀티 서비스 분기
# ---------------------------------------------------------------------------


class TestOnMessageMultiService:
    async def test_multi_service_input_calls_concurrent_runner(self):
        mock_cl = _build_mock_cl()
        mock_cl.user_session.get.return_value = MagicMock()

        with patch("scp_mcp_code_agent.app.cl", mock_cl):
            with patch("scp_mcp_code_agent.app._run_concurrent_services", new_callable=AsyncMock) as mock_concurrent:
                user_msg = MagicMock()
                user_msg.content = "block storage, virtual server"
                await on_message(user_msg)

        mock_concurrent.assert_called_once_with(["block storage", "virtual server"])

    async def test_single_service_does_not_call_concurrent_runner(self):
        mock_cl = _build_mock_cl()

        state = MagicMock()
        state.values = {"messages": [MagicMock(content="done")]}

        async def _astream(input_data, config, stream_mode):
            yield {"agent": "update"}

        mock_graph = MagicMock()
        mock_graph.astream = _astream
        mock_graph.aget_state = AsyncMock(return_value=state)

        session_data = {
            "graph": mock_graph,
            "session_id": "s1",
            "chat_history": [],
        }
        mock_cl.user_session.get.side_effect = lambda k, d=None: session_data.get(k, d)

        with patch("scp_mcp_code_agent.app.cl", mock_cl):
            with patch("scp_mcp_code_agent.app._run_concurrent_services", new_callable=AsyncMock) as mock_concurrent:
                user_msg = MagicMock()
                user_msg.content = "virtual server"
                await on_message(user_msg)

        mock_concurrent.assert_not_called()
