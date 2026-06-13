"""Create the Foundry RemoteTool connection for the deterministic route-facts MCP server.

The orchestrator agent attaches the route-facts MCP tool directly to its definition (see
`_orchestrator_tools` in `provision_foundry_specialist_agents.py`), referencing this connection by
name. This script creates/updates that connection against the deployed Azure Function `/api/route-mcp`
route. It uses the same function key as the gate/mint tools (same Function App) and exposes no new
secret. The route tool is READ-ONLY: it never mints, verifies, or issues a token.

Run AFTER the Function App is deployed with the `route-mcp` route, and BEFORE reprovisioning the
orchestrator agent.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from azure.identity import DefaultAzureCredential  # noqa: E402

from pathforward.config import load_settings  # noqa: E402
from pathforward.mcp.route_server import SERVER_LABEL, TOOL_NAME  # noqa: E402


CONNECTION_NAME = "pathforward-route-mcp"


def _exe(name: str) -> str:
    found = shutil.which(name) or shutil.which(f"{name}.cmd") or shutil.which(f"{name}.exe")
    if not found:
        raise FileNotFoundError(f"could not find executable {name!r} on PATH")
    return found


def _run(cmd: list[str]) -> str:
    proc = subprocess.run(cmd, cwd=_ROOT, check=True, text=True, capture_output=True)
    if proc.stdout.strip():
        print(proc.stdout.strip())
    if proc.stderr.strip():
        print(proc.stderr.strip())
    return proc.stdout


def _create_connection(project_endpoint: str, server_url: str, function_key: str) -> None:
    _run([
        _exe("azd"), "ai", "connection", "create", CONNECTION_NAME,
        "--project-endpoint", project_endpoint,
        "--kind", "remote-tool",
        "--target", server_url,
        "--auth-type", "custom-keys",
        "--custom-key", f"x-functions-key={function_key}",
        "--metadata", "PathForwardRole=route-facts-resolver",
        "--metadata", "ToolProtocol=MCP",
        "--force",
        "--no-prompt",
    ])


def _connection_id(project_endpoint: str) -> str:
    from azure.ai.projects import AIProjectClient

    project = AIProjectClient(
        endpoint=project_endpoint,
        credential=DefaultAzureCredential(),
    )
    return project.connections.get(CONNECTION_NAME).id


def _derived_route_url(settings) -> str:
    if settings.mcp_route_url:
        return settings.mcp_route_url
    if settings.mcp_mint_url and settings.mcp_mint_url.rstrip("/").endswith("/api/mcp"):
        return settings.mcp_mint_url.rstrip("/")[:-len("/api/mcp")] + "/api/route-mcp"
    return ""


def main() -> int:
    ap = argparse.ArgumentParser(description="Create the MCP route-facts RemoteTool connection.")
    ap.add_argument("--server-url", default="", help="Azure Function route MCP URL. Defaults to MCP_ROUTE_URL or derived.")
    ap.add_argument("--function-key", default="",
                    help="Azure Function key. Defaults to MCP_MINT_FUNCTION_KEY/PATHFORWARD_MINT_FUNCTION_KEY.")
    args = ap.parse_args()

    settings = load_settings(str(_ROOT / ".env"))
    project_endpoint = settings.foundry_project_endpoint.strip()
    server_url = (args.server_url or _derived_route_url(settings)).strip()
    function_key = (
        args.function_key
        or os.environ.get("MCP_MINT_FUNCTION_KEY", "")
        or os.environ.get("PATHFORWARD_MINT_FUNCTION_KEY", "")
    ).strip()
    if not project_endpoint:
        print("FAIL: AZURE_AI_PROJECT_ENDPOINT / FOUNDRY_PROJECT_ENDPOINT is required")
        return 1
    if not server_url:
        print("FAIL: MCP_ROUTE_URL or derivable MCP_MINT_URL is required")
        return 1
    if not function_key:
        print("FAIL: MCP_MINT_FUNCTION_KEY / PATHFORWARD_MINT_FUNCTION_KEY or --function-key is required")
        return 1

    _create_connection(project_endpoint, server_url, function_key)
    conn_id = _connection_id(project_endpoint)
    print(f"created connection {CONNECTION_NAME} id={conn_id}")
    print(f"route tool: {SERVER_LABEL}.{TOOL_NAME} require_approval=never (read-only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
