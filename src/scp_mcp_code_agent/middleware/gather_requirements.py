"""요구사항 수집 미들웨어.

에이전트가 gather_requirements 툴을 호출하면 실행을 일시 중단하고
Chainlit UI를 통해 사용자에게 질문을 표시한다. 사용자의 답변이 도구의
반환값으로 에이전트에 전달되어 이후 코드 생성에 반영된다.
"""

from typing import Callable

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage
from langgraph.types import interrupt


class GatherRequirementsMiddleware(AgentMiddleware):
    """gather_requirements 툴 호출을 가로채 사용자 답변을 수집한다."""

    def wrap_tool_call(self, request, handler: Callable) -> ToolMessage:
        if request.name != "gather_requirements":
            return handler(request)

        service_name = request.args.get("service_name", "")
        questions: list[str] = request.args.get("questions", [])

        # interrupt()로 Chainlit에 질문 목록 전달. 재개 시 answers 문자열이 반환된다.
        answers: str = interrupt({
            "type": "gather_requirements",
            "message": f"`{service_name}` MCP 서버 생성 전 요구사항을 확인합니다.",
            "service_name": service_name,
            "questions": questions,
        })

        return ToolMessage(
            content=f"[수집된 요구사항]\n{answers}",
            tool_call_id=request.id,
        )
