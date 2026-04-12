"""LangChain agent for MCP server code generation.

Built with `langchain.agents.create_agent` — the production-ready standard
that creates an agent graph calling tools in a loop until completion.

Architecture:
  - LLM: ChatOpenAI (configured via .env)
  - Tools: MCP tools (MultiServerMCPClient) + custom code-runner tools
  - Graph: create_agent returns a CompiledStateGraph; no AgentExecutor needed.

Middleware stack (실행 순서):
  1. ModelRetryMiddleware    — OpenAI API 일시적 오류 자동 재시도
  2. ToolRetryMiddleware     — MCP 툴 호출 일시적 오류 자동 재시도
  3. ModelCallLimitMiddleware — 무한루프 / 비용 폭주 방지
  4. SummarizationMiddleware — lint/테스트 반복 시 컨텍스트 압축

Entry points
------------
create_agent()  — async factory, returns (compiled_graph, mcp_ctx).
run_agent()     — convenience wrapper for CLI / testing.
"""

from langchain.agents import create_agent
from langchain.agents.middleware import (
    ModelCallLimitMiddleware,
    ModelRetryMiddleware,
    SummarizationMiddleware,
    ToolRetryMiddleware,
)
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI

from scp_mcp_code_agent.config import settings
from scp_mcp_code_agent.mcp_client import create_mcp_client
from scp_mcp_code_agent.prompts.system_prompt import build_system_prompt
from scp_mcp_code_agent.tools.code_runner import CODE_RUNNER_TOOLS

# MCP 툴 이름 — ToolRetryMiddleware가 재시도할 대상
_MCP_TOOL_NAMES = ["get_openapi_spec", "read_file", "write_file", "list_directory", "create_directory", "file_exists"]


# ---------------------------------------------------------------------------
# Middleware factory
# ---------------------------------------------------------------------------


def _build_middleware() -> list:
    """Build the ordered middleware stack from settings."""
    return [
        # 1. OpenAI API 일시적 오류(rate limit, 5xx 등) 자동 재시도
        ModelRetryMiddleware(
            max_retries=settings.middleware_retry_max,
            backoff_factor=settings.middleware_retry_backoff_factor,
        ),
        # 2. MCP 툴 호출 일시적 오류(subprocess 재시작, HTTP timeout 등) 자동 재시도
        ToolRetryMiddleware(
            max_retries=settings.middleware_retry_max,
            backoff_factor=settings.middleware_retry_backoff_factor,
            initial_delay=1.0,
            tools=_MCP_TOOL_NAMES,
        ),
        # 3. 단일 서비스 생성 당 최대 모델 호출 횟수 제한
        #    lint/테스트 수정 루프가 끝나지 않을 때 비용 폭주 방지
        ModelCallLimitMiddleware(
            run_limit=settings.middleware_model_call_run_limit,
            exit_behavior="end",  # 초과 시 에러 대신 현재까지 결과 반환
        ),
        # 4. 컨텍스트 토큰이 임계치 초과 시 오래된 메시지 요약 압축
        #    반복 수정 루프에서 누적되는 ruff/pytest 출력 정리
        SummarizationMiddleware(
            model=settings.middleware_summarization_model,
            trigger=("tokens", settings.middleware_summarization_trigger_tokens),
            keep=("messages", settings.middleware_summarization_keep_messages),
        ),
    ]


# ---------------------------------------------------------------------------
# Agent factory
# ---------------------------------------------------------------------------


async def create_agent(extra_callbacks: list | None = None):  # noqa: RUF029
    """Create and return a compiled agent graph plus the live MCP context.

    The caller MUST keep the returned `mcp_ctx` alive for the duration of
    agent use (it holds open the MCP server subprocesses).

    Args:
        extra_callbacks: Additional LangChain callbacks (e.g. Chainlit handler).

    Returns:
        Tuple of (compiled_graph, mcp_ctx).
    """
    # System prompt provides directory paths only.
    # The agent reads the example files itself via filesystem MCP tools at runtime.
    system_prompt = build_system_prompt(settings.example_dir, settings.output_dir)

    # LLM
    llm = ChatOpenAI(
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        openai_api_key=settings.openai_api_key,
    )

    # Open MCP connections — caller is responsible for closing via mcp_ctx
    mcp_ctx = create_mcp_client()
    client = await mcp_ctx.__aenter__()

    mcp_tools: list[BaseTool] = client.get_tools()
    all_tools: list[BaseTool] = mcp_tools + CODE_RUNNER_TOOLS

    graph = create_agent(
        model=llm,
        tools=all_tools,
        system_prompt=system_prompt,
        middleware=_build_middleware(),
    )

    return graph, mcp_ctx


# ---------------------------------------------------------------------------
# Convenience runner (CLI / testing)
# ---------------------------------------------------------------------------


async def run_agent(
    service_name: str,
    chat_history: list[BaseMessage] | None = None,
) -> str:
    """Run the agent for a single service name and return the final output text.

    Args:
        service_name: Name of the cloud service to generate an MCP server for.
        chat_history: Optional prior conversation messages.

    Returns:
        Final AI message content string.
    """
    graph, mcp_ctx = await create_agent()
    try:
        messages: list[BaseMessage] = list(chat_history or [])
        messages.append(HumanMessage(content=service_name))

        result = await graph.ainvoke({"messages": messages})
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