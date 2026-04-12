"""Chainlit application entry point for the MCP Code Generation Agent.

Run with:
    uv run chainlit run src/scp_mcp_code_agent/app.py

Each chat session gets its own agent instance so that MCP connections
are isolated and conversation history is preserved per user.

create_agent (langchain.agents) uses a messages-based interface:
  input:  {"messages": [HumanMessage(...)]}
  output: {"messages": [..., AIMessage(...)]}
"""

import chainlit as cl
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from scp_mcp_code_agent.agent import create_agent

# ---------------------------------------------------------------------------
# Lifecycle hooks
# ---------------------------------------------------------------------------


@cl.on_chat_start
async def on_chat_start() -> None:
    """Initialise the agent and MCP connections for this chat session."""
    await cl.Message(
        content=(
            "**MCP Code Generator** is ready!\n\n"
            "Enter a cloud service name to generate an MCP server from its OpenAPI spec.\n\n"
            "**Examples:**\n"
            "- `virtual server`\n"
            "- `block storage`\n"
            "- `kubernetes`\n"
            "- `object storage`"
        )
    ).send()

    # Build agent — keep MCP context alive for the whole session
    graph, mcp_ctx = await create_agent()

    cl.user_session.set("graph", graph)
    cl.user_session.set("mcp_ctx", mcp_ctx)
    cl.user_session.set("chat_history", [])


@cl.on_chat_end
async def on_chat_end() -> None:
    """Clean up MCP server subprocesses when the user closes the chat."""
    mcp_ctx = cl.user_session.get("mcp_ctx")
    if mcp_ctx is not None:
        try:
            await mcp_ctx.__aexit__(None, None, None)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Message handler
# ---------------------------------------------------------------------------


@cl.on_message
async def on_message(message: cl.Message) -> None:
    """Process an incoming user message through the agent."""
    graph = cl.user_session.get("graph")
    chat_history: list[BaseMessage] = cl.user_session.get("chat_history", [])

    # Append new user message to history
    chat_history.append(HumanMessage(content=message.content))

    async with cl.Step(name="Generating MCP Server", type="run") as step:
        step.input = message.content

        try:
            result = await graph.ainvoke(
                {"messages": chat_history},
                config={"callbacks": [cl.LangchainCallbackHandler()]},
            )

            # Final AI message is always the last item in result["messages"]
            ai_message: AIMessage = result["messages"][-1]
            output: str = ai_message.content

            # Persist the full updated message list for next turn
            cl.user_session.set("chat_history", result["messages"])

            step.output = output

        except Exception as exc:
            error_msg = f"Agent encountered an error: {exc}"
            step.output = error_msg
            await cl.Message(content=f"**Error:** {error_msg}").send()
            return

    await cl.Message(content=output).send()


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------


@cl.action_callback("reset_history")
async def reset_history(_action: cl.Action) -> None:
    """Clear conversation history for the current session."""
    cl.user_session.set("chat_history", [])
    await cl.Message(content="Conversation history cleared.").send()
