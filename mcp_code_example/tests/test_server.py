"""Tests for the Virtual Server MCP server example.

This test file is also a TEMPLATE that the code generation agent uses
when writing tests for newly generated MCP servers.

Testing strategy:
  - Mock httpx.AsyncClient to avoid real API calls.
  - Test happy path for each tool.
  - Test that request parameters are forwarded correctly.
  - Test error propagation (non-2xx HTTP responses).
"""

import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_response(data: dict | list, status_code: int = 200) -> MagicMock:
    """Build a mock httpx.Response that returns *data* from .json()."""
    mock = MagicMock(spec=httpx.Response)
    mock.status_code = status_code
    mock.json.return_value = data
    mock.raise_for_status = MagicMock()  # no-op on 2xx
    return mock


def _mock_error_response(status_code: int = 500) -> MagicMock:
    """Build a mock httpx.Response that raises HTTPStatusError on raise_for_status()."""
    mock = MagicMock(spec=httpx.Response)
    mock.status_code = status_code
    mock.raise_for_status.side_effect = httpx.HTTPStatusError(
        message=f"HTTP {status_code}",
        request=MagicMock(),
        response=mock,
    )
    return mock


# ---------------------------------------------------------------------------
# list_virtual_servers
# ---------------------------------------------------------------------------


class TestListVirtualServers:
    @pytest.mark.asyncio
    async def test_returns_server_list(self):
        servers = [{"id": "srv-001", "name": "web-01", "status": "running"}]
        mock_resp = _mock_response({"virtual_servers": servers})

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            from mcp_code_example.server import list_virtual_servers

            result = await list_virtual_servers(region="kr-central-1")

        assert result == servers

    @pytest.mark.asyncio
    async def test_status_filter_forwarded(self):
        mock_resp = _mock_response({"virtual_servers": []})

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            from mcp_code_example.server import list_virtual_servers

            await list_virtual_servers(region="kr-central-1", status="stopped")

            call_kwargs = mock_client.get.call_args.kwargs
            assert call_kwargs["params"]["status"] == "stopped"

    @pytest.mark.asyncio
    async def test_no_status_filter_omits_param(self):
        mock_resp = _mock_response({"virtual_servers": []})

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            from mcp_code_example.server import list_virtual_servers

            await list_virtual_servers()

            call_kwargs = mock_client.get.call_args.kwargs
            assert "status" not in call_kwargs["params"]

    @pytest.mark.asyncio
    async def test_http_error_propagated(self):
        mock_resp = _mock_error_response(status_code=403)

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            from mcp_code_example.server import list_virtual_servers

            with pytest.raises(httpx.HTTPStatusError):
                await list_virtual_servers()


# ---------------------------------------------------------------------------
# get_virtual_server
# ---------------------------------------------------------------------------


class TestGetVirtualServer:
    @pytest.mark.asyncio
    async def test_returns_server_detail(self):
        detail = {"id": "srv-001", "name": "web-01", "flavor": "m1.small"}
        mock_resp = _mock_response(detail)

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            from mcp_code_example.server import get_virtual_server

            result = await get_virtual_server("srv-001")

        assert result == detail


# ---------------------------------------------------------------------------
# create_virtual_server
# ---------------------------------------------------------------------------


class TestCreateVirtualServer:
    @pytest.mark.asyncio
    async def test_create_returns_server(self):
        created = {"id": "srv-new", "name": "test-server", "status": "building"}
        mock_resp = _mock_response(created)

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            from mcp_code_example.server import create_virtual_server

            result = await create_virtual_server(
                name="test-server",
                flavor="m1.small",
                image_id="img-ubuntu-22",
            )

        assert result["id"] == "srv-new"

    @pytest.mark.asyncio
    async def test_optional_network_id_included_when_provided(self):
        mock_resp = _mock_response({"id": "srv-new"})

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            from mcp_code_example.server import create_virtual_server

            await create_virtual_server(
                name="test",
                flavor="m1.small",
                image_id="img-001",
                network_id="net-abc",
            )

            payload = mock_client.post.call_args.kwargs["json"]
            assert payload["network_id"] == "net-abc"


# ---------------------------------------------------------------------------
# delete_virtual_server
# ---------------------------------------------------------------------------


class TestDeleteVirtualServer:
    @pytest.mark.asyncio
    async def test_delete_returns_confirmation(self):
        mock_resp = _mock_response(
            {"message": "Virtual server srv-001 deleted successfully.", "id": "srv-001"}
        )

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.delete = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            from mcp_code_example.server import delete_virtual_server

            result = await delete_virtual_server("srv-001")

        assert result["id"] == "srv-001"
        assert "deleted" in result["message"]
