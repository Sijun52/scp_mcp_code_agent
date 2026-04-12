"""Planning tools — 에이전트가 코드 생성 전/중에 사용하는 워크플로우 툴."""

from pathlib import Path

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
    return "approved"


@tool
def set_output_directory(path: str) -> str:
    """생성된 MCP 서버 파일이 저장될 출력 디렉토리를 변경한다.

    사용자가 대화 중 저장 경로를 바꾸고 싶을 때 호출한다.
    이 툴을 호출한 이후의 모든 write_file 작업은 반환된 경로를 기준으로 한다.

    Args:
        path: 새 출력 디렉토리 경로. 절대경로 또는 '~' 포함 경로 모두 허용.

    Returns:
        유효성 검증된 절대경로 문자열.
        이후 파일 저장 시 이 경로를 기준으로 사용할 것.
    """
    resolved = Path(path).expanduser().resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    return str(resolved)


PLANNING_TOOLS = [confirm_endpoint_plan, set_output_directory]