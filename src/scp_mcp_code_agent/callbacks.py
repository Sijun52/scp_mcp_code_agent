"""LangChain callback handler for timing instrumentation.

Logs execution time for LLM calls and tool calls so that real bottlenecks
can be identified in production without guessing.

Usage::

    from scp_mcp_code_agent.callbacks import TimingCallbackHandler
    graph, mcp_ctx = await create_agent(extra_callbacks=[TimingCallbackHandler()])
"""

import logging
import time
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

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
