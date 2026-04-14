"""Unit tests for agent.py helper functions."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scp_mcp_code_agent.agent import (
    _MCP_TOOL_NAMES,
    _SPEC_CACHE_TTL,
    _build_middleware,
    _wrap_spec_tool_with_cache,
    create_agent,
    run_agent,
)


# ---------------------------------------------------------------------------
# _wrap_spec_tool_with_cache
# ---------------------------------------------------------------------------


def _make_spec_tool(sync_result="spec-content", async_result=None):
    """_wrap_spec_tool_with_cache는 tool._run/_arun을 plain function으로 교체하므로
    call 카운터를 직접 추적하는 클로저를 사용한다."""
    _async_result = async_result or sync_result
    sync_calls: list[str] = []
    async_calls: list[str] = []

    tool = MagicMock()
    tool.name = "get_openapi_spec"
    tool._run = lambda service_name, **kw: (sync_calls.append(service_name), sync_result)[-1]
    tool._arun = AsyncMock(side_effect=lambda service_name, **kw: async_calls.append(service_name) or _async_result)
    tool._sync_calls = sync_calls
    tool._async_calls = async_calls
    return tool


class TestWrapSpecToolWithCache:
    def test_cache_miss_calls_original_run(self):
        tool = _make_spec_tool("spec-v1")
        wrapped = _wrap_spec_tool_with_cache(tool)

        result = wrapped._run("my-service")
        assert result == "spec-v1"
        assert tool._sync_calls == ["my-service"]

    def test_cache_hit_skips_original_run(self):
        tool = _make_spec_tool("spec-v1")
        wrapped = _wrap_spec_tool_with_cache(tool)

        wrapped._run("my-service")
        wrapped._run("my-service")

        assert len(tool._sync_calls) == 1  # second call should hit cache

    def test_different_keys_do_not_share_cache(self):
        tool = _make_spec_tool()
        wrapped = _wrap_spec_tool_with_cache(tool)

        wrapped._run("service-a")
        wrapped._run("service-b")

        assert len(tool._sync_calls) == 2

    def test_cache_returns_correct_value_on_hit(self):
        tool = _make_spec_tool("spec-content")
        wrapped = _wrap_spec_tool_with_cache(tool)

        wrapped._run("svc")
        result = wrapped._run("svc")

        assert result == "spec-content"

    def test_cache_expires_after_ttl(self):
        tool = _make_spec_tool("spec")
        wrapped = _wrap_spec_tool_with_cache(tool)

        wrapped._run("svc")

        with patch("scp_mcp_code_agent.agent.time.monotonic", return_value=time.monotonic() + _SPEC_CACHE_TTL + 1):
            wrapped._run("svc")

        assert len(tool._sync_calls) == 2

    async def test_async_cache_miss_calls_original_arun(self):
        tool = _make_spec_tool(async_result="async-spec")
        wrapped = _wrap_spec_tool_with_cache(tool)

        result = await wrapped._arun("svc")
        assert result == "async-spec"
        assert tool._async_calls == ["svc"]

    async def test_async_cache_hit_skips_original_arun(self):
        tool = _make_spec_tool(async_result="async-spec")
        wrapped = _wrap_spec_tool_with_cache(tool)

        await wrapped._arun("svc")
        await wrapped._arun("svc")

        assert len(tool._async_calls) == 1


# ---------------------------------------------------------------------------
# _build_middleware
# ---------------------------------------------------------------------------


class TestBuildMiddleware:
    # SummarizationMiddleware.__init__이 내부적으로 init_chat_model을 호출해
    # LLM 초기화를 시도하므로 패치 후 테스트한다.
    def _build(self, hitl: bool = True):
        with patch("scp_mcp_code_agent.agent.SummarizationMiddleware", return_value=MagicMock()):
            return _build_middleware(hitl=hitl)

    def test_returns_list(self):
        assert isinstance(self._build(), list)

    def test_returns_non_empty_list(self):
        assert len(self._build()) > 0

    def test_contains_expected_middleware_types(self):
        from langchain.agents.middleware import (
            ModelCallLimitMiddleware,
            ModelRetryMiddleware,
            ToolRetryMiddleware,
        )
        from scp_mcp_code_agent.middleware import (
            GatherRequirementsMiddleware,
            OpenAPISpecConfirmMiddleware,
            TestFailureHandlerMiddleware,
            WriteFileConfirmMiddleware,
        )

        result = self._build()
        types = [type(m) for m in result]

        assert ModelRetryMiddleware in types
        assert ToolRetryMiddleware in types
        assert ModelCallLimitMiddleware in types
        assert GatherRequirementsMiddleware in types
        assert OpenAPISpecConfirmMiddleware in types
        assert WriteFileConfirmMiddleware in types
        assert TestFailureHandlerMiddleware in types

    def test_hitl_false_excludes_hitl_middleware(self):
        from langchain.agents.middleware import (
            ModelCallLimitMiddleware,
            ModelRetryMiddleware,
            ToolRetryMiddleware,
        )
        from scp_mcp_code_agent.middleware import (
            GatherRequirementsMiddleware,
            OpenAPISpecConfirmMiddleware,
            TestFailureHandlerMiddleware,
            WriteFileConfirmMiddleware,
        )

        result = self._build(hitl=False)
        types = [type(m) for m in result]

        # 안정성 / 비용 제어 미들웨어는 포함
        assert ModelRetryMiddleware in types
        assert ToolRetryMiddleware in types
        assert ModelCallLimitMiddleware in types

        # HITL 미들웨어는 제외
        assert GatherRequirementsMiddleware not in types
        assert OpenAPISpecConfirmMiddleware not in types
        assert WriteFileConfirmMiddleware not in types
        assert TestFailureHandlerMiddleware not in types

    def test_hitl_false_has_fewer_items_than_hitl_true(self):
        full = self._build(hitl=True)
        headless = self._build(hitl=False)
        assert len(headless) < len(full)


# ---------------------------------------------------------------------------
# _MCP_TOOL_NAMES / _SPEC_CACHE_TTL
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# create_agent / run_agent
# ---------------------------------------------------------------------------


def _patch_agent_deps(mock_graph=None, mock_tools=None):
    """create_agent 실행에 필요한 외부 의존성 일괄 패치."""
    mock_graph = mock_graph or MagicMock()
    mock_client = MagicMock()
    mock_client.get_tools.return_value = mock_tools or []

    mock_mcp_ctx = AsyncMock()
    mock_mcp_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_mcp_ctx.__aexit__ = AsyncMock(return_value=None)

    return (
        patch("scp_mcp_code_agent.agent.create_mcp_client", return_value=mock_mcp_ctx),
        patch("scp_mcp_code_agent.agent.ChatOpenAI", return_value=MagicMock()),
        patch("scp_mcp_code_agent.agent.SummarizationMiddleware", return_value=MagicMock()),
        patch("scp_mcp_code_agent.agent._langchain_create_agent", return_value=mock_graph),
    )


class TestCreateAgent:
    async def test_returns_graph_and_mcp_ctx(self):
        mock_graph = MagicMock()
        p1, p2, p3, p4 = _patch_agent_deps(mock_graph=mock_graph)
        with p1, p2, p3, p4:
            graph, mcp_ctx = await create_agent()
        assert graph is mock_graph

    async def test_wraps_spec_tool_with_cache(self):
        spec_tool = MagicMock()
        spec_tool.name = "get_openapi_spec"
        other_tool = MagicMock()
        other_tool.name = "read_file"

        p1, p2, p3, p4 = _patch_agent_deps(mock_tools=[spec_tool, other_tool])
        with p1, p2, p3, p4:
            await create_agent()

        # get_openapi_spec 툴에 캐시 래퍼가 적용됐으면 _run이 교체됐을 것
        assert callable(spec_tool._run)

    async def test_accepts_extra_callbacks(self):
        cb = MagicMock()
        p1, p2, p3, p4 = _patch_agent_deps()
        with p1, p2, p3, p4:
            graph, _ = await create_agent(extra_callbacks=[cb])
        assert graph is not None


class TestRunAgent:
    async def test_invokes_graph_and_returns_content(self):
        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(return_value={
            "messages": [MagicMock(content="generated code")]
        })
        mock_mcp_ctx = AsyncMock()
        mock_mcp_ctx.__aexit__ = AsyncMock()

        with patch("scp_mcp_code_agent.agent.create_agent", return_value=(mock_graph, mock_mcp_ctx)):
            result = await run_agent("virtual server")

        assert result == "generated code"
        mock_mcp_ctx.__aexit__.assert_called_once()

    async def test_mcp_ctx_cleaned_up_on_error(self):
        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(side_effect=RuntimeError("boom"))
        mock_mcp_ctx = AsyncMock()
        mock_mcp_ctx.__aexit__ = AsyncMock()

        with patch("scp_mcp_code_agent.agent.create_agent", return_value=(mock_graph, mock_mcp_ctx)):
            with pytest.raises(RuntimeError):
                await run_agent("svc")

        mock_mcp_ctx.__aexit__.assert_called_once()


class TestMain:
    def test_exits_without_args(self):
        with patch("sys.argv", ["scp-agent"]):
            with pytest.raises(SystemExit) as exc_info:
                from scp_mcp_code_agent.agent import main
                main()
        assert exc_info.value.code == 1

    def test_runs_with_service_name(self):
        with patch("sys.argv", ["scp-agent", "virtual", "server"]):
            with patch("scp_mcp_code_agent.agent.run_agent", return_value="output") as mock_run:
                with patch("asyncio.run", return_value="output"):
                    from scp_mcp_code_agent.agent import main
                    main()


class TestConstants:
    def test_mcp_tool_names_includes_spec_tool(self):
        assert "get_openapi_spec" in _MCP_TOOL_NAMES

    def test_mcp_tool_names_includes_filesystem_tools(self):
        for name in ["read_file", "write_file", "list_directory", "create_directory", "file_exists"]:
            assert name in _MCP_TOOL_NAMES

    def test_mcp_tool_names_includes_read_multiple_files(self):
        assert "read_multiple_files" in _MCP_TOOL_NAMES

    def test_spec_cache_ttl_is_positive(self):
        assert _SPEC_CACHE_TTL > 0
