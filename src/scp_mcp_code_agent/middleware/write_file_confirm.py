"""Scenarios 2+3 — 파일 저장 확인 미들웨어.

write_file 툴 호출 전 두 가지를 동시에 처리한다:
  - Scenario 2: 대상 경로에 파일이 이미 존재하면 덮어쓰기 경고
  - Scenario 3: 생성된 코드 내용을 항상 프리뷰로 보여주고 사용자 승인 요청

두 시나리오를 단일 interrupt로 통합하여 UX 단절을 최소화한다.
"""

from pathlib import Path
from typing import Callable

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage
from langgraph.types import interrupt

# 코드 파일만 확인 대상 (빈 __init__.py 등은 건너뜀)
_CONFIRM_EXTENSIONS = {".py"}
_MIN_CONTENT_LENGTH = 50  # 이 길이 미만은 확인 없이 바로 저장


class WriteFileConfirmMiddleware(AgentMiddleware):
    """write_file 실행 전 코드 프리뷰 및 덮어쓰기 경고."""

    def wrap_tool_call(self, request, handler: Callable) -> ToolMessage:
        if request.name != "write_file":
            return handler(request)

        path: str = request.args.get("path", "")
        content: str = request.args.get("content", "")

        # 짧은 파일(__init__.py 등)이나 비코드 파일은 확인 생략
        if (
            Path(path).suffix not in _CONFIRM_EXTENSIONS
            or len(content) < _MIN_CONTENT_LENGTH
        ):
            return handler(request)

        file_exists = Path(path).exists()

        decision = interrupt({
            "type": "write_file_confirm",
            "path": path,
            "content_preview": content[:4000],
            "file_exists": file_exists,
            "message": (
                f"⚠️ `{path}` 파일이 이미 존재합니다. 덮어쓰시겠습니까?"
                if file_exists
                else f"`{path}` 파일을 생성합니다. 코드를 검토해주세요."
            ),
        })

        if decision == "reject":
            return ToolMessage(
                content=f"[사용자 거절] `{path}` 파일 저장이 취소되었습니다.",
                tool_call_id=request.id,
            )

        # "approve" 또는 "edit" 모두 실제 저장 진행
        # "edit"의 경우 사용자가 Chainlit에서 수정한 content를 Command(resume=)로 돌려보낼 수 있다
        if isinstance(decision, dict) and "content" in decision:
            # 사용자가 내용을 수정한 경우: args를 교체하여 handler 재호출
            request.args["content"] = decision["content"]

        return handler(request)