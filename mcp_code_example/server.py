"""Virtual Server MCP Server.

Example MCP server that wraps a Virtual Server REST API.
This file serves as the CODE GENERATION TEMPLATE — the agent reads
this file to understand the expected structure and style for new servers.

Structure overview:
  1. Module-level docstring
  2. Imports (stdlib → third-party → local)
  3. FastMCP app initialization
  4. Config / helper functions
  5. @mcp.tool() definitions — one per API operation
  6. Entry-point guard
"""

import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# App initialisation
# ---------------------------------------------------------------------------

mcp = FastMCP("virtual-server")

# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------

BASE_URL: str = os.getenv("VIRTUAL_SERVER_API_URL", "https://api.example.com")
API_KEY: str = os.getenv("VIRTUAL_SERVER_API_KEY", "")
TENANT_ID: str = os.getenv("VIRTUAL_SERVER_TENANT_ID", "")


def _headers() -> dict[str, str]:
    """Return common HTTP headers for every request."""
    return {
        "Authorization": f"Bearer {API_KEY}",
        "X-Tenant-ID": TENANT_ID,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


# ---------------------------------------------------------------------------
# Tools — list / get / create / update / delete
# ---------------------------------------------------------------------------


@mcp.tool()
async def list_virtual_servers(
    region: str = "kr-central-1",
    status: str | None = None,
) -> list[dict[str, Any]]:
    """List virtual servers in the specified region.

    Args:
        region: Cloud region identifier (e.g. "kr-central-1").
        status: Filter by server status (running | stopped | error).
                Pass None to return all statuses.

    Returns:
        List of virtual server objects.
        Each object includes: id, name, status, flavor, region, created_at.
    """
    params: dict[str, str] = {"region": region}
    if status:
        params["status"] = status

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{BASE_URL}/virtual-servers",
            params=params,
            headers=_headers(),
        )
        response.raise_for_status()
        return response.json().get("virtual_servers", [])


@mcp.tool()
async def get_virtual_server(server_id: str) -> dict[str, Any]:
    """Get details of a specific virtual server.

    Args:
        server_id: Unique identifier of the virtual server.

    Returns:
        Full virtual server detail object including network and disk info.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{BASE_URL}/virtual-servers/{server_id}",
            headers=_headers(),
        )
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def create_virtual_server(
    name: str,
    flavor: str,
    image_id: str,
    region: str = "kr-central-1",
    network_id: str | None = None,
    user_data: str | None = None,
) -> dict[str, Any]:
    """Create a new virtual server.

    Args:
        name: Display name for the server (must be unique within tenant).
        flavor: Server flavor / size (e.g. "m1.small", "c2.large").
        image_id: OS image ID to boot from.
        region: Cloud region identifier.
        network_id: VPC network ID to attach. Uses default network if None.
        user_data: Cloud-init script (base64-encoded or plain text).

    Returns:
        Created virtual server object with assigned id and initial status.
    """
    payload: dict[str, Any] = {
        "name": name,
        "flavor": flavor,
        "image_id": image_id,
        "region": region,
    }
    if network_id:
        payload["network_id"] = network_id
    if user_data:
        payload["user_data"] = user_data

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{BASE_URL}/virtual-servers",
            json=payload,
            headers=_headers(),
        )
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def start_virtual_server(server_id: str) -> dict[str, str]:
    """Start (power on) a stopped virtual server.

    Args:
        server_id: Unique identifier of the virtual server.

    Returns:
        Operation result with message and task_id.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{BASE_URL}/virtual-servers/{server_id}/start",
            headers=_headers(),
        )
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def stop_virtual_server(server_id: str, force: bool = False) -> dict[str, str]:
    """Stop (power off) a running virtual server.

    Args:
        server_id: Unique identifier of the virtual server.
        force: If True, performs a hard power-off (may cause data loss).

    Returns:
        Operation result with message and task_id.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{BASE_URL}/virtual-servers/{server_id}/stop",
            json={"force": force},
            headers=_headers(),
        )
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def delete_virtual_server(server_id: str) -> dict[str, str]:
    """Delete a virtual server permanently.

    Args:
        server_id: Unique identifier of the virtual server to delete.

    Returns:
        Confirmation message with deleted server id.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.delete(
            f"{BASE_URL}/virtual-servers/{server_id}",
            headers=_headers(),
        )
        response.raise_for_status()
        return {"message": f"Virtual server {server_id} deleted successfully.", "id": server_id}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
