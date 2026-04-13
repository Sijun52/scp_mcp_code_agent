"""Unit tests for planning tools."""

import pytest

from scp_mcp_code_agent.tools.planning import confirm_endpoint_plan, set_output_directory


class TestConfirmEndpointPlan:
    def test_returns_approved(self):
        result = confirm_endpoint_plan.invoke({
            "service_name": "virtual server",
            "planned_tools": ["list_servers", "get_server"],
            "reasoning": "These are the main CRUD endpoints.",
        })
        assert result == "approved"

    def test_accepts_empty_tools_list(self):
        result = confirm_endpoint_plan.invoke({
            "service_name": "svc",
            "planned_tools": [],
            "reasoning": "none",
        })
        assert result == "approved"


class TestSetOutputDirectory:
    def test_creates_directory_and_returns_path(self, tmp_path):
        target = tmp_path / "output"
        result = set_output_directory.invoke({"path": str(target)})
        assert target.is_dir()
        assert result == str(target.resolve())

    def test_creates_nested_directories(self, tmp_path):
        target = tmp_path / "a" / "b" / "c"
        result = set_output_directory.invoke({"path": str(target)})
        assert target.is_dir()
        assert result == str(target.resolve())

    def test_idempotent_on_existing_directory(self, tmp_path):
        target = tmp_path / "exists"
        target.mkdir()
        result = set_output_directory.invoke({"path": str(target)})
        assert result == str(target.resolve())

    def test_expands_home_tilde(self):
        import os
        result = set_output_directory.invoke({"path": "~/test_scp_output_tmp"})
        assert not result.startswith("~")
        # Clean up
        import shutil
        shutil.rmtree(result, ignore_errors=True)
