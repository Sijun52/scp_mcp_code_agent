"""Custom HITL (Human-in-the-Loop) middleware for the code generation agent."""

from scp_mcp_code_agent.middleware.gather_requirements import GatherRequirementsMiddleware
from scp_mcp_code_agent.middleware.openapi_confirm import OpenAPISpecConfirmMiddleware
from scp_mcp_code_agent.middleware.test_failure import TestFailureHandlerMiddleware
from scp_mcp_code_agent.middleware.write_file_confirm import WriteFileConfirmMiddleware

__all__ = [
    "GatherRequirementsMiddleware",
    "OpenAPISpecConfirmMiddleware",
    "WriteFileConfirmMiddleware",
    "TestFailureHandlerMiddleware",
]