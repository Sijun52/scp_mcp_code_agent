"""Integration tests for the code generation agent.

Strategy: mock the MCP client so no real MCP servers need to be running,
and mock the LLM to return deterministic tool calls.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scp_mcp_code_agent.prompts.system_prompt import build_system_prompt


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------


class TestBuildSystemPrompt:
    def test_contains_example_dir_path(self, tmp_path: Path):
        """System prompt should reference the example directory path — not embed file contents."""
        example_dir = tmp_path / "mcp_code_example"
        output_dir = tmp_path / "generated"

        prompt = build_system_prompt(example_dir, output_dir)

        assert str(example_dir) in prompt

    def test_contains_output_dir_path(self, tmp_path: Path):
        """System prompt should reference the output directory path."""
        example_dir = tmp_path / "mcp_code_example"
        output_dir = tmp_path / "generated"

        prompt = build_system_prompt(example_dir, output_dir)

        assert str(output_dir) in prompt

    def test_does_not_embed_file_contents(self, tmp_path: Path):
        """File contents must NOT be injected — agent reads them via MCP tools."""
        example_dir = tmp_path / "mcp_code_example"
        example_dir.mkdir()
        (example_dir / "server.py").write_text("SENTINEL_CONTENT_XYZ", encoding="utf-8")
        output_dir = tmp_path / "generated"

        prompt = build_system_prompt(example_dir, output_dir)

        assert "SENTINEL_CONTENT_XYZ" not in prompt

    def test_contains_workflow_instructions(self, tmp_path: Path):
        """Prompt should contain the numbered workflow steps."""
        prompt = build_system_prompt(tmp_path / "example", tmp_path / "generated")

        assert "get_openapi_spec" in prompt
        assert "run_ruff_check" in prompt
        assert "run_pytest" in prompt
        assert "read_file" in prompt
        assert "list_directory" in prompt


# ---------------------------------------------------------------------------
# MCP client config builder
# ---------------------------------------------------------------------------


class TestMcpClientConfig:
    def test_filesystem_server_always_included(self):
        from scp_mcp_code_agent.mcp_client import _build_server_configs

        configs = _build_server_configs()
        assert "filesystem" in configs
        assert configs["filesystem"]["transport"] == "stdio"

    def test_openapi_server_stdio_config(self):
        from scp_mcp_code_agent.config import settings
        from scp_mcp_code_agent.mcp_client import _build_server_configs

        original = settings.openapi_mcp_transport
        settings.openapi_mcp_transport = "stdio"
        try:
            configs = _build_server_configs()
            assert "openapi" in configs
            assert configs["openapi"]["transport"] == "stdio"
        finally:
            settings.openapi_mcp_transport = original

    def test_openapi_server_sse_config(self):
        from scp_mcp_code_agent.config import settings
        from scp_mcp_code_agent.mcp_client import _build_server_configs

        original_transport = settings.openapi_mcp_transport
        original_url = settings.openapi_mcp_url
        settings.openapi_mcp_transport = "sse"
        settings.openapi_mcp_url = "http://localhost:8080/mcp"
        try:
            configs = _build_server_configs()
            assert configs["openapi"]["transport"] == "sse"
            assert configs["openapi"]["url"] == "http://localhost:8080/mcp"
        finally:
            settings.openapi_mcp_transport = original_transport
            settings.openapi_mcp_url = original_url

    def test_unsupported_transport_raises(self):
        from scp_mcp_code_agent.config import settings
        from scp_mcp_code_agent.mcp_client import _build_server_configs

        original = settings.openapi_mcp_transport
        settings.openapi_mcp_transport = "grpc"
        try:
            with pytest.raises(ValueError, match="Unsupported"):
                _build_server_configs()
        finally:
            settings.openapi_mcp_transport = original


# ---------------------------------------------------------------------------
# Settings / config
# ---------------------------------------------------------------------------


class TestSettings:
    def test_openapi_mcp_args_list_splits_correctly(self):
        from scp_mcp_code_agent.config import settings

        original = settings.openapi_mcp_args
        settings.openapi_mcp_args = "-m openapi_mcp_server --debug"
        try:
            assert settings.openapi_mcp_args_list == ["-m", "openapi_mcp_server", "--debug"]
        finally:
            settings.openapi_mcp_args = original

    def test_output_dir_defaults_to_home(self):
        from scp_mcp_code_agent.config import settings

        assert isinstance(settings.output_dir, Path)
        # 기본값은 홈 디렉토리 하위여야 한다
        assert str(Path.home()) in str(settings.output_dir)

    def test_example_dir_is_code_relative(self):
        from scp_mcp_code_agent.config import settings

        assert isinstance(settings.example_dir, Path)
        # example_dir은 env가 아닌 코드 위치 기준으로 결정된다
        assert settings.example_dir.name == "mcp_code_example"
