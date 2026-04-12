"""Scenario 4 — 엔드포인트 계획 확인 툴.

에이전트가 OpenAPI 스펙을 분석한 뒤 어떤 엔드포인트를 MCP 툴로
구현할지 계획을 세우면, 코드 작성 전에 반드시 이 툴을 호출해야 한다.

HumanInTheLoopMiddleware가 이 툴 호출을 가로채 사용자에게 계획을 보여주고
approve / reject 선택을 요청한다. 에이전트는 툴 반환값으로 사용자 결정을
알 수 있다 (approved / rejected).
"""

from langchain_core.tools import tool


@tool
def confirm_endpoint_plan(
    service_name: str,
    planned_tools: list[str],
    reasoning: str,
) -> str:
    """OpenAPI 스펙 분석 후 구현할 MCP 툴 목록을 사용자에게 확인받는다.

    코드 생성을 시작하기 전에 반드시 이 툴을 호출해야 한다.
    사용자가 거절하면 툴 목록을 재검토하여 다시 호출한다.

    Args:
        service_name: 생성 대상 서비스명 (예: "virtual server")
        planned_tools: 구현 예정 MCP 툴 함수명 목록
                       (예: ["list_virtual_servers", "get_virtual_server", ...])
        reasoning: 해당 엔드포인트를 선택한 이유 (간략히)

    Returns:
        "approved"  — 사용자가 계획을 승인함, 코드 작성 시작 가능
        "rejected"  — 사용자가 거절함, 툴 목록을 재검토 후 재호출 필요
    """
    # 실제 반환값은 HumanInTheLoopMiddleware가 사용자 결정으로 대체한다.
    # 이 코드는 middleware가 없는 환경(테스트 등)에서의 기본 동작이다.
    return "approved"


PLANNING_TOOLS = [confirm_endpoint_plan]