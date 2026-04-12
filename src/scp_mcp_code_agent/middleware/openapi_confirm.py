"""Scenario 1 — OpenAPI 스펙 확인 미들웨어.

get_openapi_spec 툴이 실행된 직후 가져온 스펙 내용을 사용자에게 보여주고
실제 대상 서비스가 맞는지 확인을 받는다. 사용자가 거절하면 에이전트에게
명확한 거절 메시지를 반환하여 작업을 중단시킨다.
"""

from typing import Callable

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage
from langgraph.types import interrupt


class OpenAPISpecConfirmMiddleware(AgentMiddleware):
    """get_openapi_spec 실행 후 스펙 내용을 사용자에게 확인."""

    def wrap_tool_call(self, request, handler: Callable) -> ToolMessage:
        result = handler(request)

        if request.name != "get_openapi_spec":
            return result

        spec_content = result.content if hasattr(result, "content") else str(result)

        # interrupt()는 LangGraph 실행을 일시 중단하고 Chainlit에 값을 전달한다.
        # Command(resume=decision)으로 재개될 때 decision 값이 반환된다.
        decision = interrupt({
            "type": "openapi_confirm",
            "message": "OpenAPI 스펙을 가져왔습니다. 이 서비스로 계속 진행할까요?",
            "spec_preview": spec_content[:3000],
        })

        if decision == "reject":
            return ToolMessage(
                content=(
                    "[사용자 거절] 해당 OpenAPI 스펙으로 진행하지 않습니다. "
                    "작업을 중단합니다."
                ),
                tool_call_id=request.id,
            )

        return result