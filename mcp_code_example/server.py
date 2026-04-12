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
from typing import Annotated, Any

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import Field

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
    region: Annotated[
        str,
        Field(
            description=(
                "Cloud region identifier to query (e.g. 'kr-central-1', 'kr-central-2'). "
                "Determines which availability zone the servers are retrieved from."
            ),
        ),
    ] = "kr-central-1",
    status: Annotated[
        str | None,
        Field(
            description=(
                "Filter servers by lifecycle status. "
                "Accepted values: 'running', 'stopped', 'error'. "
                "Omit or pass null to return servers in all statuses."
            ),
        ),
    ] = None,
) -> list[dict[str, Any]]:
    """List virtual servers in the specified region.

    Use this tool when:
    - You need to enumerate all virtual servers owned by the tenant.
    - You want to check which servers are running or stopped before taking an action.
    - You need to look up a server_id by name to call get/start/stop/delete tools.

    Workflow:
    1. Call with the desired region (default: kr-central-1).
    2. Optionally filter by status to narrow results.
    3. Use the returned id values with get_virtual_server or action tools.

    Common scenarios:
    - Audit all running servers: status="running"
    - Find a stopped server before restarting: status="stopped"
    - List all servers regardless of state: omit status

    Returns:
        List of virtual server summary objects.
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
async def get_virtual_server(
    server_id: Annotated[
        str,
        Field(
            description=(
                "Unique identifier of the virtual server (UUID format). "
                "Obtain this from list_virtual_servers if you only know the server name."
            ),
        ),
    ],
) -> dict[str, Any]:
    """Get full details of a specific virtual server.

    Use this tool when:
    - You need detailed information about a single server (network, disk, flavor).
    - You want to verify the current status before performing an action.
    - You need to retrieve attached network or storage IDs.

    Workflow:
    1. If you only know the server name, call list_virtual_servers first to get the id.
    2. Call get_virtual_server with the id.
    3. Inspect the returned object for network_interfaces, block_devices, or current status.

    Returns:
        Full virtual server detail object including network and disk configuration.
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
    name: Annotated[
        str,
        Field(
            description=(
                "Display name for the new server. Must be unique within the tenant. "
                "Allowed characters: letters, numbers, hyphens. Max 63 characters."
            ),
        ),
    ],
    flavor: Annotated[
        str,
        Field(
            description=(
                "Server flavor (instance type) that determines CPU and memory. "
                "Examples: 'm1.small' (1 vCPU / 2 GB), 'c2.large' (8 vCPU / 16 GB). "
                "Use the flavors API to list all available options."
            ),
        ),
    ],
    image_id: Annotated[
        str,
        Field(
            description=(
                "OS image UUID to boot from (e.g. Ubuntu 22.04, Rocky Linux 8). "
                "Use the images API to list available image IDs."
            ),
        ),
    ],
    region: Annotated[
        str,
        Field(
            description="Cloud region where the server will be provisioned.",
        ),
    ] = "kr-central-1",
    network_id: Annotated[
        str | None,
        Field(
            description=(
                "VPC network UUID to attach the primary NIC to. "
                "If omitted, the tenant's default network is used."
            ),
        ),
    ] = None,
    user_data: Annotated[
        str | None,
        Field(
            description=(
                "Cloud-init script executed on first boot. "
                "Accepts plain text or base64-encoded content. "
                "Use this to install packages, configure services, or add SSH keys."
            ),
        ),
    ] = None,
) -> dict[str, Any]:
    """Create a new virtual server (instance).

    Use this tool when:
    - The user requests provisioning a new server or instance.
    - You need to deploy a workload that requires a dedicated VM.

    Workflow:
    1. Confirm the flavor, image, and region with the user if not specified.
    2. Optionally resolve network_id by listing VPC networks.
    3. Call create_virtual_server — the server starts in 'building' status.
    4. Poll get_virtual_server until status transitions to 'running' (~60–120 s).

    Common scenarios:
    - Minimal creation: provide name, flavor, image_id; region/network use defaults.
    - Custom network: supply network_id to attach to a specific VPC subnet.
    - Bootstrap scripts: pass user_data to run cloud-init on first boot.

    Returns:
        Created virtual server object with the assigned id and initial 'building' status.
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
async def start_virtual_server(
    server_id: Annotated[
        str,
        Field(
            description=(
                "Unique identifier of the virtual server to start. "
                "The server must be in 'stopped' status; starting a running server is a no-op."
            ),
        ),
    ],
) -> dict[str, str]:
    """Start (power on) a stopped virtual server.

    Use this tool when:
    - The user asks to start, boot, or power on a server.
    - A server is in 'stopped' status and needs to resume workloads.

    Workflow:
    1. Verify the server is in 'stopped' status via get_virtual_server.
    2. Call start_virtual_server with the server id.
    3. Poll get_virtual_server until status becomes 'running'.

    Returns:
        Operation result dict with 'message' and 'task_id' fields.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{BASE_URL}/virtual-servers/{server_id}/start",
            headers=_headers(),
        )
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def stop_virtual_server(
    server_id: Annotated[
        str,
        Field(
            description=(
                "Unique identifier of the virtual server to stop. "
                "The server must be in 'running' status."
            ),
        ),
    ],
    force: Annotated[
        bool,
        Field(
            description=(
                "If True, performs an immediate hard power-off (equivalent to pulling the power cord). "
                "May cause data loss or filesystem corruption. "
                "Use only when a graceful shutdown is unresponsive. Default: False (graceful)."
            ),
        ),
    ] = False,
) -> dict[str, str]:
    """Stop (power off) a running virtual server.

    Use this tool when:
    - The user asks to shut down, stop, or power off a server.
    - You need to stop a server before resizing, snapshotting, or deleting it.

    Workflow:
    1. Verify the server is 'running' via get_virtual_server.
    2. Call stop_virtual_server (force=False for graceful shutdown).
    3. Poll get_virtual_server until status becomes 'stopped'.

    Common scenarios:
    - Graceful shutdown: force=False (default) — OS receives ACPI shutdown signal.
    - Emergency stop: force=True — hard power-off when OS is unresponsive.

    Returns:
        Operation result dict with 'message' and 'task_id' fields.
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
async def delete_virtual_server(
    server_id: Annotated[
        str,
        Field(
            description=(
                "Unique identifier of the virtual server to permanently delete. "
                "The server should be in 'stopped' status before deletion. "
                "This action is irreversible — all local disks are destroyed."
            ),
        ),
    ],
) -> dict[str, str]:
    """Permanently delete a virtual server and its local storage.

    Use this tool when:
    - The user explicitly asks to delete or terminate a server.
    - A server is no longer needed and resources should be released.

    Workflow:
    1. Confirm the server_id with the user — deletion is irreversible.
    2. Stop the server first if it is still running (stop_virtual_server).
    3. Call delete_virtual_server.
    4. Verify deletion by confirming the server no longer appears in list_virtual_servers.

    Common scenarios:
    - Clean up test servers after a demo.
    - Decommission servers that have been replaced by newer instances.

    Returns:
        Confirmation dict with 'message' and 'id' of the deleted server.
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