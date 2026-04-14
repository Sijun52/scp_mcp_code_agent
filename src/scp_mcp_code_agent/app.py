"""Chainlit application entry point for the MCP Code Generation Agent.

Run with:
    uv run chainlit run src/scp_mcp_code_agent/app.py

HITL (Human-in-the-Loop) 처리 흐름:
  1. graph.astream()으로 스트리밍 실행
  2. __interrupt__ 감지 시 interrupt type에 따라 Chainlit UI 표시
  3. 사용자 결정을 Command(resume=decision)으로 그래프에 전달해 재개
  4. 최종 AIMessage content를 사용자에게 전달

Interrupt types:
  - gather_requirements (Scenario 0) : 코드 생성 전 요구사항 수집 (텍스트 질의)
  - openapi_confirm     (Scenario 1) : 스펙 확인 → approve / reject
  - write_file_confirm  (Scenario 2+3): 코드 프리뷰 + 덮어쓰기 → approve / reject
  - hitl_default        (Scenario 4) : 엔드포인트 계획 확인 → approve / reject
  - test_failure        (Scenario 5) : pytest 실패 → retry / save_as_is / abort
"""

import logging
import uuid

_CHAT_HISTORY_MAX = 30  # 세션당 유지할 최대 메시지 수

import chainlit as cl
from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.types import Command

from scp_mcp_code_agent.agent import create_agent
from scp_mcp_code_agent.callbacks import TimingCallbackHandler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

# ---------------------------------------------------------------------------
# Interrupt 핸들러
# ---------------------------------------------------------------------------


async def _handle_interrupt(interrupt_value: dict) -> str:
    """interrupt_value의 type에 따라 적절한 Chainlit UI를 표시하고 사용자 결정을 반환."""
    interrupt_type = interrupt_value.get("type", "hitl_default")
    message = interrupt_value.get("message", "계속 진행할까요?")

    # ── Scenario 0: 요구사항 수집 ────────────────────────────────────────
    if interrupt_type == "gather_requirements":
        questions: list[str] = interrupt_value.get("questions", [])
        service_name = interrupt_value.get("service_name", "")

        await cl.Message(
            content=f"**[요구사항 수집]** {message}\n\n아래 질문에 답해주세요."
        ).send()

        answers: list[str] = []
        for i, question in enumerate(questions, 1):
            resp = await cl.AskUserMessage(
                content=f"**Q{i}.** {question}",
                timeout=300,
            ).send()
            answers.append(resp.output if resp else "(답변 없음)")

        formatted = "\n".join(
            f"Q{i}. {q}\nA{i}. {a}"
            for i, (q, a) in enumerate(zip(questions, answers), 1)
        )
        return formatted

    # ── Scenario 1: OpenAPI 스펙 확인 ────────────────────────────────────
    if interrupt_type == "openapi_confirm":
        spec_preview = interrupt_value.get("spec_preview", "")
        await cl.Message(
            content=f"**[스펙 확인]** {message}\n\n```\n{spec_preview}\n```"
        ).send()

        res = await cl.AskActionMessage(
            content="이 OpenAPI 스펙으로 MCP 서버를 생성할까요?",
            actions=[
                cl.Action(name="approve", label="✅ 진행", value="approve"),
                cl.Action(name="reject", label="❌ 중단", value="reject"),
            ],
        ).send()
        return res.value if res else "reject"

    # ── Scenario 2+3: 코드 프리뷰 + 덮어쓰기 경고 ───────────────────────
    if interrupt_type == "write_file_confirm":
        path = interrupt_value.get("path", "")
        preview = interrupt_value.get("content_preview", "")
        file_exists = interrupt_value.get("file_exists", False)

        header = f"**[파일 저장 확인]** {message}"
        await cl.Message(
            content=f"{header}\n\n**경로:** `{path}`\n\n```python\n{preview}\n```"
        ).send()

        actions = [
            cl.Action(name="approve", label="✅ 저장", value="approve"),
            cl.Action(name="reject", label="❌ 취소", value="reject"),
        ]
        if file_exists:
            actions.insert(1, cl.Action(name="overwrite", label="⚠️ 덮어쓰기", value="approve"))

        res = await cl.AskActionMessage(
            content="이 코드를 파일로 저장할까요?",
            actions=actions,
        ).send()
        return res.value if res else "reject"

    # ── Scenario 4: 엔드포인트 계획 확인 (HumanInTheLoopMiddleware 기본 형식) ──
    if interrupt_type == "hitl_default":
        tool_name = interrupt_value.get("tool_name", "")
        tool_args = interrupt_value.get("tool_args", {})

        if tool_name == "confirm_endpoint_plan":
            planned_tools = tool_args.get("planned_tools", [])
            reasoning = tool_args.get("reasoning", "")
            service_name = tool_args.get("service_name", "")

            tools_md = "\n".join(f"- `{t}`" for t in planned_tools)
            await cl.Message(
                content=(
                    f"**[엔드포인트 계획 확인]** `{service_name}` 서비스에 대해 "
                    f"아래 {len(planned_tools)}개 MCP 툴을 구현할 예정입니다.\n\n"
                    f"{tools_md}\n\n"
                    f"**선택 이유:** {reasoning}"
                )
            ).send()

            res = await cl.AskActionMessage(
                content="이 계획으로 코드를 생성할까요?",
                actions=[
                    cl.Action(name="approve", label="✅ 승인", value="approve"),
                    cl.Action(name="reject", label="🔄 재계획 요청", value="reject"),
                ],
            ).send()
            return res.value if res else "reject"

    # ── Scenario 5: pytest 반복 실패 ─────────────────────────────────────
    if interrupt_type == "test_failure":
        failure_count = interrupt_value.get("failure_count", 0)
        log = interrupt_value.get("log", "")

        await cl.Message(
            content=(
                f"**[테스트 실패]** {message}\n\n"
                f"```\n{log}\n```"
            )
        ).send()

        res = await cl.AskActionMessage(
            content=f"{failure_count}회 실패 후 어떻게 진행할까요?",
            actions=[
                cl.Action(name="retry", label="🔄 재시도", value="retry"),
                cl.Action(name="save_as_is", label="💾 현재 상태로 저장", value="save_as_is"),
                cl.Action(name="abort", label="🛑 중단", value="abort"),
            ],
        ).send()
        return res.value if res else "abort"

    # ── 알 수 없는 타입 — 기본 approve/reject ────────────────────────────
    await cl.Message(content=f"**[확인 요청]** {message}").send()
    res = await cl.AskActionMessage(
        content="계속 진행할까요?",
        actions=[
            cl.Action(name="approve", label="✅ 진행", value="approve"),
            cl.Action(name="reject", label="❌ 중단", value="reject"),
        ],
    ).send()
    return res.value if res else "reject"


# ---------------------------------------------------------------------------
# 그래프 실행 (interrupt 루프 포함)
# ---------------------------------------------------------------------------


async def _run_with_hitl(
    graph,
    input_data: dict | Command,
    config: dict,
) -> str:
    """interrupt가 발생할 때마다 사용자 결정을 받아 그래프를 재개한다."""
    while True:
        interrupted = False
        interrupt_value = None

        async for chunk in graph.astream(input_data, config=config, stream_mode="updates"):
            if "__interrupt__" in chunk:
                interrupted = True
                interrupt_value = chunk["__interrupt__"][0].value
                break

        if not interrupted:
            state = await graph.aget_state(config)
            msgs = state.values.get("messages", [])
            return msgs[-1].content if msgs else "작업이 완료되었습니다."

        # 사용자 결정 획득
        decision = await _handle_interrupt(interrupt_value)

        # 그래프 재개: 다음 루프에서 Command를 input으로 사용
        input_data = Command(resume=decision)


# ---------------------------------------------------------------------------
# Chainlit lifecycle hooks
# ---------------------------------------------------------------------------


@cl.on_chat_start
async def on_chat_start() -> None:
    """Initialise the agent and MCP connections for this chat session."""
    await cl.Message(
        content=(
            "**MCP Code Generator** is ready!\n\n"
            "생성하고 싶은 클라우드 서비스명을 입력하면 에이전트가 요구사항을 먼저 확인하고\n"
            "OpenAPI 스펙 기반으로 MCP 서버 코드를 자동 생성합니다.\n\n"
            "**예시:**\n"
            "- `virtual server`\n"
            "- `block storage`\n"
            "- `kubernetes`"
        )
    ).send()

    graph, mcp_ctx = await create_agent(extra_callbacks=[TimingCallbackHandler()])
    session_id = str(uuid.uuid4())

    cl.user_session.set("graph", graph)
    cl.user_session.set("mcp_ctx", mcp_ctx)
    cl.user_session.set("session_id", session_id)
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
    """Process an incoming user message through the agent with HITL support."""
    graph = cl.user_session.get("graph")
    session_id = cl.user_session.get("session_id")
    chat_history: list[BaseMessage] = cl.user_session.get("chat_history", [])

    config = {"configurable": {"thread_id": session_id}}

    chat_history.append(HumanMessage(content=message.content))

    async with cl.Step(name="Generating MCP Server", type="run") as step:
        step.input = message.content
        try:
            output = await _run_with_hitl(
                graph=graph,
                input_data={"messages": chat_history},
                config=config,
            )
            # 전체 메시지 이력 갱신 (최대 _CHAT_HISTORY_MAX 개로 제한)
            state = await graph.aget_state(config)
            all_messages = state.values.get("messages", chat_history)
            cl.user_session.set("chat_history", all_messages[-_CHAT_HISTORY_MAX:])

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
