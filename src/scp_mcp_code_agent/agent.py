"""LangChain agent for MCP server code generation.

Built with `langchain.agents.create_agent` — the production-ready standard
that creates an agent graph calling tools in a loop until completion.

Architecture:
  - LLM: ChatOpenAI (configured via .env)
  - Tools: MCP tools (MultiServerMCPClient) + code-runner tools + planning tool
  - Graph: create_agent returns a CompiledStateGraph with InMemorySaver checkpointer
           (checkpointer는 HITL interrupt/resume에 필수)

Middleware stack (실행 순서):
  [안정성]
  1. ModelRetryMiddleware      — OpenAI API 일시적 오류 자동 재시도
  2. ToolRetryMiddleware       — MCP 툴 호출 오류 자동 재시도
  [비용/루프 제어]
  3. ModelCallLimitMiddleware  — 무한루프 / 비용 폭주 방지
  4. SummarizationMiddleware   — 컨텍스트 토큰 초과 시 압축
  [HITL — Human-in-the-Loop]
  5. OpenAPISpecConfirmMiddleware  — Scenario 1: 스펙 조회 후 사용자 확인
  6. WriteFileConfirmMiddleware    — Scenario 2+3: 코드 프리뷰 + 덮어쓰기 경고
  7. HumanInTheLoopMiddleware      — Scenario 4: 엔드포인트 계획 확인
  8. TestFailureHandlerMiddleware  — Scenario 5: pytest 반복 실패 시 판단 위임

Entry points
------------
create_agent()  — async factory, returns (compiled_graph, mcp_ctx).
run_agent()     — convenience wrapper for CLI / testing.
"""

from langchain.agents import create_agent
from langchain.agents.middleware import (
    HumanInTheLoopMiddleware,
    ModelCallLimitMiddleware,
    ModelRetryMiddleware,
    SummarizationMiddleware,
    ToolRetryMiddleware,
)
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver

from scp_mcp_code_agent.config import settings
from scp_mcp_code_agent.mcp_client import create_mcp_client
from scp_mcp_code_agent.middleware import (
    OpenAPISpecConfirmMiddleware,
    TestFailureHandlerMiddleware,
    WriteFileConfirmMiddleware,
)
from scp_mcp_code_agent.prompts.system_prompt import build_system_prompt
from scp_mcp_code_agent.tools.code_runner import CODE_RUNNER_TOOLS
from scp_mcp_code_agent.tools.planning import PLANNING_TOOLS

# MCP 툴 이름 — ToolRetryMiddleware 재시도 대상 (로컬 code_runner 툴은 제외)
_MCP_TOOL_NAMES = [
    "get_openapi_spec",
    "read_file",
    "write_file",
    "list_directory",
    "create_directory",
    "file_exists",
]


# ---------------------------------------------------------------------------
# Middleware factory
# ---------------------------------------------------------------------------


def _build_middleware() -> list:
    """Build the ordered middleware stack.

    미들웨어 튜닝 파라미터는 변경 빈도가 낮아 코드에서 직접 관리한다.
    운영 환경에서 변경이 필요한 경우 코드 수정 후 재배포한다.
    """
    return [
        # ── 안정성 ──────────────────────────────────────────────────────────
        ModelRetryMiddleware(
            max_retries=3,
            backoff_factor=2.0,
        ),
        ToolRetryMiddleware(
            max_retries=3,
            backoff_factor=2.0,
            initial_delay=1.0,
            tools=_MCP_TOOL_NAMES,
        ),
        # ── 비용 / 루프 제어 ────────────────────────────────────────────────
        ModelCallLimitMiddleware(
            run_limit=20,
            exit_behavior="end",
        ),
        SummarizationMiddleware(
            model="gpt-4o-mini",
            trigger=("tokens", 60_000),
            keep=("messages", 10),
        ),
        # ── HITL ────────────────────────────────────────────────────────────
        # Scenario 1: get_openapi_spec 실행 후 스펙 내용 확인
        OpenAPISpecConfirmMiddleware(),
        # Scenario 2+3: write_file 전 코드 프리뷰 + 덮어쓰기 경고
        WriteFileConfirmMiddleware(),
        # Scenario 4: 엔드포인트 계획 툴 호출 시 사용자 승인 요청
        HumanInTheLoopMiddleware(
            interrupt_on={
                "confirm_endpoint_plan": {
                    "allowed_decisions": ["approve", "reject"],
                },
            }
        ),
        # Scenario 5: pytest 연속 실패 시 사용자 판단 위임
        TestFailureHandlerMiddleware(),
    ]


# ---------------------------------------------------------------------------
# Agent factory
# ---------------------------------------------------------------------------


async def create_agent(extra_callbacks: list | None = None):  # noqa: RUF029
    """Create and return a compiled agent graph plus the live MCP context.

    InMemorySaver checkpointer를 사용하여 HITL interrupt/resume을 지원한다.
    세션 간 대화 상태는 유지되지 않는다 (프로세스 재시작 시 초기화).

    The caller MUST keep the returned `mcp_ctx` alive for the duration of
    agent use (it holds open the MCP server subprocesses).

    Args:
        extra_callbacks: Additional LangChain callbacks (e.g. Chainlit handler).

    Returns:
        Tuple of (compiled_graph, mcp_ctx).
    """
    system_prompt = build_system_prompt(settings.example_dir, settings.output_dir)

    llm = ChatOpenAI(
        model=settings.llm_model,
        temperature=0.2,
        openai_api_key=settings.openai_api_key,
    )

    mcp_ctx = create_mcp_client()
    client = await mcp_ctx.__aenter__()

    mcp_tools: list[BaseTool] = client.get_tools()
    all_tools: list[BaseTool] = mcp_tools + CODE_RUNNER_TOOLS + PLANNING_TOOLS

    graph = create_agent(
        model=llm,
        tools=all_tools,
        system_prompt=system_prompt,
        middleware=_build_middleware(),
        # HITL interrupt/resume을 위한 checkpointer (필수)
        checkpointer=InMemorySaver(),
    )

    return graph, mcp_ctx


# ---------------------------------------------------------------------------
# Convenience runner (CLI / testing — HITL 없이 실행)
# ---------------------------------------------------------------------------


async def run_agent(
    service_name: str,
    chat_history: list[BaseMessage] | None = None,
    thread_id: str = "cli",
) -> str:
    """Run the agent for a single service name and return the final output text.

    Args:
        service_name: Name of the cloud service to generate an MCP server for.
        chat_history: Optional prior conversation messages.
        thread_id: Unique thread identifier for the checkpointer.

    Returns:
        Final AI message content string.
    """
    graph, mcp_ctx = await create_agent()
    config = {"configurable": {"thread_id": thread_id}}

    try:
        messages: list[BaseMessage] = list(chat_history or [])
        messages.append(HumanMessage(content=service_name))
        result = await graph.ainvoke({"messages": messages}, config=config)
    finally:
        await mcp_ctx.__aexit__(None, None, None)

    return result["messages"][-1].content


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point: `scp-agent "<service name>"`."""
    import asyncio
    import sys

    if len(sys.argv) < 2:
        print("Usage: scp-agent '<service name>'")
        sys.exit(1)

    service_name = " ".join(sys.argv[1:])
    output = asyncio.run(run_agent(service_name))
    print("\n=== Agent Output ===")
    print(output)