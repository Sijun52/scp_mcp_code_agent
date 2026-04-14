"""LangChain callback handlers for the MCP Code Generation Agent.

TimingCallbackHandler  — wall-clock timing logs per tool/LLM call.
ChainlitStepCallbackHandler — shows each tool call as a nested Chainlit Step.

Usage::

    from scp_mcp_code_agent.callbacks import TimingCallbackHandler, ChainlitStepCallbackHandler
    graph, mcp_ctx = await create_agent(
        extra_callbacks=[TimingCallbackHandler(), ChainlitStepCallbackHandler()]
    )
"""

import json
import logging
import time
from pathlib import Path
from typing import Any
from uuid import UUID

from langchain_core.callbacks import AsyncCallbackHandler, BaseCallbackHandler
from langchain_core.outputs import LLMResult

try:
    import chainlit as cl  # optional Chainlit dep
    _CHAINLIT_AVAILABLE = True
except ImportError:
    cl = None  # type: ignore[assignment]
    _CHAINLIT_AVAILABLE = False

logger = logging.getLogger("scp_agent.timing")


class TimingCallbackHandler(BaseCallbackHandler):
    """Records wall-clock time for each LLM inference and tool call.

    Each event is logged at INFO level in the format::

        [timing] <label> completed in X.XXs
        [timing] <label> failed after X.XXs — <error>
    """

    def __init__(self) -> None:
        super().__init__()
        # run_id (UUID) → (label, start_monotonic)
        self._starts: dict[UUID, tuple[str, float]] = {}

    # ------------------------------------------------------------------
    # LLM
    # ------------------------------------------------------------------

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        model = serialized.get("kwargs", {}).get("model_name", "llm")
        self._starts[run_id] = (f"LLM({model})", time.monotonic())

    def on_llm_end(self, response: LLMResult, *, run_id: UUID, **kwargs: Any) -> None:
        self._finish(run_id)

    def on_llm_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        self._finish(run_id, error=error)

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        tool_name = serialized.get("name", "tool")
        self._starts[run_id] = (f"tool:{tool_name}", time.monotonic())

    def on_tool_end(self, output: Any, *, run_id: UUID, **kwargs: Any) -> None:
        self._finish(run_id)

    def on_tool_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        self._finish(run_id, error=error)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _finish(self, run_id: UUID, *, error: BaseException | None = None) -> None:
        entry = self._starts.pop(run_id, None)
        if entry is None:
            return
        label, started = entry
        elapsed = time.monotonic() - started
        if error:
            logger.info("[timing] %s failed after %.2fs — %s", label, elapsed, error)
        else:
            logger.info("[timing] %s completed in %.2fs", label, elapsed)


# ---------------------------------------------------------------------------
# ChainlitStepCallbackHandler
# ---------------------------------------------------------------------------

# Tools shown as Chainlit Steps.
# HITL tools (gather_requirements, get_openapi_spec, write_file, confirm_endpoint_plan)
# are intentionally excluded — they already have dedicated Chainlit UI widgets.
_TRACKED_TOOLS: frozenset[str] = frozenset({
    "get_openapi_spec_endpoints",
    "get_openapi_spec_detail",
    "read_file",
    "read_multiple_files",
    "list_directory",
    "create_directory",
    "file_exists",
    "run_ruff_check",
    "run_ruff_format_check",
    "run_ruff_all",
    "run_pytest",
    "set_output_directory",
})

_TOOL_DISPLAY: dict[str, str] = {
    "get_openapi_spec_endpoints": "스펙 엔드포인트 목록 조회",
    "get_openapi_spec_detail": "스펙 상세 조회",
    "read_file": "파일 읽기",
    "read_multiple_files": "파일 배치 읽기",
    "list_directory": "디렉터리 목록",
    "create_directory": "디렉터리 생성",
    "file_exists": "파일 존재 확인",
    "run_ruff_check": "Lint 검사",
    "run_ruff_format_check": "포맷 검사",
    "run_ruff_all": "Lint + 포맷 검사",
    "run_pytest": "테스트 실행",
    "set_output_directory": "출력 경로 설정",
}

_CODE_RUNNER_TOOLS: frozenset[str] = frozenset({
    "run_ruff_check", "run_ruff_format_check", "run_ruff_all", "run_pytest",
})

_OUTPUT_PREVIEW_LEN = 400  # chars to show in step output


def _step_name(tool_name: str, input_str: str) -> str:
    """Derive a descriptive step name from tool name + serialised input."""
    base = _TOOL_DISPLAY.get(tool_name, tool_name)
    try:
        args = json.loads(input_str)
    except (json.JSONDecodeError, TypeError, ValueError):
        return base
    if not isinstance(args, dict):
        return base

    if tool_name == "get_openapi_spec_endpoints":
        svc = args.get("service_name", "")
        return f"{base} ({svc})" if svc else base

    if tool_name == "get_openapi_spec_detail":
        svc = args.get("service_name", "")
        ops = args.get("operation_ids", [])
        parts = [p for p in (svc, f"{len(ops)}개" if ops else "") if p]
        return f"{base} ({', '.join(parts)})" if parts else base

    if tool_name in ("read_file", "file_exists"):
        path = args.get("path", "")
        return f"{base}: {Path(path).name}" if path else base

    if tool_name == "read_multiple_files":
        paths = args.get("paths", [])
        return f"{base}: {len(paths)}개 파일" if paths else base

    if tool_name in ("run_ruff_check", "run_ruff_format_check", "run_ruff_all"):
        target = args.get("target_path", "")
        return f"{base}: {Path(target).name}" if target else base

    if tool_name == "run_pytest":
        test_path = args.get("test_path", "")
        return f"{base}: {Path(test_path).name}" if test_path else base

    return base


def _is_tool_failure(tool_name: str, output: str) -> bool:
    """Return True when a code-runner tool reports a non-zero exit code."""
    if tool_name in _CODE_RUNNER_TOOLS:
        return "[exit code: 0]" not in output
    return False


def _format_step_output(tool_name: str, output: str) -> str:
    """Return a display-friendly (truncated) output string."""
    text = output.strip()
    if tool_name in _CODE_RUNNER_TOOLS:
        # Show tail — pytest/ruff summary lines appear last
        return ("...\n" + text[-_OUTPUT_PREVIEW_LEN:]) if len(text) > _OUTPUT_PREVIEW_LEN else text
    return (text[:_OUTPUT_PREVIEW_LEN] + "...") if len(text) > _OUTPUT_PREVIEW_LEN else text


class ChainlitStepCallbackHandler(AsyncCallbackHandler):
    """Renders each tracked tool call as a nested ``cl.Step`` in the Chainlit UI.

    Each step shows:
    - Name enriched with context (service name, file name, operation count, …)
    - Input string
    - Truncated output (code-runner tools show tail for summary lines)
    - Error state for non-zero exit codes from ruff / pytest

    Tools with dedicated HITL UI (gather_requirements, get_openapi_spec,
    write_file, confirm_endpoint_plan) are intentionally excluded.

    Requires Chainlit to be installed.  Silently does nothing when run outside
    a Chainlit context (e.g. in unit tests) so that the handler can always be
    registered without import guards at the call site.
    """

    def __init__(self) -> None:
        super().__init__()
        # run_id → (cl.Step, tool_name)
        self._steps: dict[UUID, tuple[Any, str]] = {}

    async def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        tool_name = serialized.get("name", "")
        if tool_name not in _TRACKED_TOOLS or not _CHAINLIT_AVAILABLE:
            return
        name = _step_name(tool_name, input_str)
        step = cl.Step(name=name, type="tool")  # type: ignore[union-attr]
        step.input = input_str
        await step.__aenter__()
        self._steps[run_id] = (step, tool_name)

    async def on_tool_end(
        self,
        output: Any,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        entry = self._steps.pop(run_id, None)
        if entry is None:
            return
        step, tool_name = entry
        output_str = str(output)
        step.output = _format_step_output(tool_name, output_str)
        step.is_error = _is_tool_failure(tool_name, output_str)
        await step.__aexit__(None, None, None)

    async def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        entry = self._steps.pop(run_id, None)
        if entry is None:
            return
        step, _tool_name = entry
        step.output = f"오류: {error}"
        step.is_error = True
        await step.__aexit__(type(error), error, None)
