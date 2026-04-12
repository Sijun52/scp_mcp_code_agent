"""Scenario 5 — 테스트 반복 실패 후 사용자 판단 위임 미들웨어.

run_pytest가 N회 연속 실패하면 자동 수정 루프를 멈추고 사용자에게
세 가지 선택지를 제공한다:
  - retry     : 실패 카운트 초기화 후 에이전트가 다시 수정 시도
  - save_as_is: 현재 상태 그대로 저장하고 완료 처리
  - abort     : 전체 작업 중단
"""

from typing import Callable

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage
from langgraph.types import interrupt

_SUCCESS_MARKER = "[exit code: 0]"
_MAX_AUTO_RETRIES = 3  # 이 횟수 초과 시 사용자에게 판단 위임


class TestFailureHandlerMiddleware(AgentMiddleware):
    """pytest 연속 실패 시 사용자에게 진행 방식 선택 요청."""

    def __init__(self) -> None:
        self._failure_count: int = 0

    def wrap_tool_call(self, request, handler: Callable) -> ToolMessage:
        result = handler(request)

        if request.name != "run_pytest":
            return result

        content = result.content if hasattr(result, "content") else str(result)

        if _SUCCESS_MARKER in content:
            self._failure_count = 0  # 성공 시 카운터 초기화
            return result

        self._failure_count += 1

        if self._failure_count < _MAX_AUTO_RETRIES:
            return result  # 아직 자동 수정 허용

        decision = interrupt({
            "type": "test_failure",
            "failure_count": self._failure_count,
            "log": content[-2000:],  # 최근 2000자만 전달
            "message": (
                f"{self._failure_count}회 수정 시도 후에도 테스트가 실패합니다. "
                "어떻게 진행할까요?"
            ),
        })

        if decision == "retry":
            self._failure_count = 0
            return ToolMessage(
                content=content + "\n[사용자 결정] 재시도합니다. 코드를 다시 수정해주세요.",
                tool_call_id=request.id,
            )

        if decision == "save_as_is":
            return ToolMessage(
                content=content + "\n[사용자 결정] 현재 상태로 저장하고 완료합니다.",
                tool_call_id=request.id,
            )

        # abort
        return ToolMessage(
            content=content + "\n[사용자 결정] 작업을 중단합니다.",
            tool_call_id=request.id,
        )