"""LangChain agent for MCP server code generation.

Built with `langchain.agents.create_agent` — the production-ready standard
that creates an agent graph calling tools in a loop until completion.

Architecture:
  - LLM: ChatOpenAI (configured via .env)
  - Tools: MCP tools (MultiServerMCPClient) + custom code-runner tools
  - Graph: create_agent returns a CompiledStateGraph; no AgentExecutor needed.

Entry points
------------
create_agent()  — async factory, returns (compiled_graph, mcp_ctx).
run_agent()     — convenience wrapper for CLI / testing.
"""

from langchain.agents import create_agent
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI

from scp_mcp_code_agent.config import settings
from scp_mcp_code_agent.mcp_client import create_mcp_client
from scp_mcp_code_agent.prompts.system_prompt import build_system_prompt
from scp_mcp_code_agent.tools.code_runner import CODE_RUNNER_TOOLS


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
        Tuple of (compiled_graph, mcp_ctx) where compiled_graph is the
        CompiledStateGraph returned by langchain.agents.create_agent.
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

    # create_agent: production-ready agent from langchain.agents.
    # Loops tool calls automatically; system_prompt is injected each turn.
    graph = create_agent(
        model=llm,
        tools=all_tools,
        system_prompt=system_prompt,
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

    # The last message in the result is the final AI response
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
