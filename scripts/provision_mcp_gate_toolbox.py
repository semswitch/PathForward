"""Attach the Evidence Gate token issuer MCP tool to the orchestrator toolbox."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib import request

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from azure.identity import DefaultAzureCredential  # noqa: E402

from pathforward.config import load_settings  # noqa: E402
from pathforward.mcp.gate_server import SERVER_LABEL, TOOL_NAME  # noqa: E402


TOOLBOX_NAME = "pathforward-orchestrator-toolbox"
CONNECTION_NAME = "pathforward-gate-mcp"


def _exe(name: str) -> str:
    found = shutil.which(name) or shutil.which(f"{name}.cmd") or shutil.which(f"{name}.exe")
    if not found:
        raise FileNotFoundError(f"could not find executable {name!r} on PATH")
    return found


def _token() -> str:
    return DefaultAzureCredential().get_token("https://ai.azure.com/.default").token


def _json_request(method: str, url: str, payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {_token()}",
            "Content-Type": "application/json",
        },
    )
    with request.urlopen(req, timeout=90) as resp:  # noqa: S310 - Azure project endpoint
        body = resp.read().decode("utf-8")
    return json.loads(body) if body else {}


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
        "--metadata", "PathForwardRole=evidence-gate-token-issuer",
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


def _current_toolbox(project_endpoint: str) -> dict:
    toolbox = _json_request("GET", f"{project_endpoint.rstrip('/')}/toolboxes/{TOOLBOX_NAME}?api-version=v1")
    default_version = toolbox.get("default_version")
    if not default_version:
        raise RuntimeError(f"{TOOLBOX_NAME} has no default_version")
    version = _json_request(
        "GET",
        f"{project_endpoint.rstrip('/')}/toolboxes/{TOOLBOX_NAME}/versions/{default_version}?api-version=v1",
    )
    return {"toolbox": toolbox, "version": version}


def _gate_tool(server_url: str, connection_id: str) -> dict:
    return {
        "type": "mcp",
        "server_label": SERVER_LABEL,
        "server_url": server_url,
        "require_approval": "never",
        "allowed_tools": [TOOL_NAME],
        "project_connection_id": connection_id,
    }


def _without_existing_gate_tool(tools: list[dict]) -> list[dict]:
    kept = []
    for tool in tools:
        if tool.get("type") == "mcp" and tool.get("server_label") == SERVER_LABEL:
            continue
        kept.append(tool)
    return kept


def _publish_toolbox(project_endpoint: str, server_url: str, connection_id: str) -> str:
    current = _current_toolbox(project_endpoint)["version"]
    tools = _without_existing_gate_tool(list(current.get("tools") or []))
    tools.append(_gate_tool(server_url, connection_id))
    payload = {
        "description": current.get("description") or (
            "PathForward Prompt Orchestrator toolbox with A2A specialists and governed MCP tools."
        ),
        "tools": tools,
        "skills": current.get("skills") or [],
        "metadata": {
            **(current.get("metadata") or {}),
            "gate_tool": TOOL_NAME,
            "gate_server_label": SERVER_LABEL,
        },
    }
    created = _json_request(
        "POST",
        f"{project_endpoint.rstrip('/')}/toolboxes/{TOOLBOX_NAME}/versions?api-version=v1",
        payload,
    )
    version = str(created.get("version") or created.get("id", "").rsplit(":", 1)[-1])
    if not version:
        raise RuntimeError(f"could not determine created toolbox version: {created}")
    _json_request(
        "PATCH",
        f"{project_endpoint.rstrip('/')}/toolboxes/{TOOLBOX_NAME}?api-version=v1",
        {"default_version": version},
    )
    return version


def _derived_gate_url(settings) -> str:
    if settings.mcp_gate_url:
        return settings.mcp_gate_url
    if settings.mcp_mint_url and settings.mcp_mint_url.rstrip("/").endswith("/api/mcp"):
        return settings.mcp_mint_url.rstrip("/")[:-len("/api/mcp")] + "/api/gate-mcp"
    return ""


def main() -> int:
    ap = argparse.ArgumentParser(description="Attach MCP Evidence Gate issuer to the orchestrator toolbox.")
    ap.add_argument("--server-url", default="", help="Azure Function Gate MCP URL. Defaults to MCP_GATE_URL.")
    ap.add_argument("--function-key", default="",
                    help="Azure Function key. Defaults to MCP_MINT_FUNCTION_KEY/PATHFORWARD_MINT_FUNCTION_KEY.")
    args = ap.parse_args()

    settings = load_settings(str(_ROOT / ".env"))
    project_endpoint = settings.foundry_project_endpoint.strip()
    server_url = (args.server_url or _derived_gate_url(settings)).strip()
    function_key = (
        args.function_key
        or os.environ.get("MCP_MINT_FUNCTION_KEY", "")
        or os.environ.get("PATHFORWARD_MINT_FUNCTION_KEY", "")
    ).strip()
    if not project_endpoint:
        print("FAIL: AZURE_AI_PROJECT_ENDPOINT / FOUNDRY_PROJECT_ENDPOINT is required")
        return 1
    if not server_url:
        print("FAIL: MCP_GATE_URL or derivable MCP_MINT_URL is required")
        return 1
    if not function_key:
        print("FAIL: MCP_MINT_FUNCTION_KEY / PATHFORWARD_MINT_FUNCTION_KEY or --function-key is required")
        return 1

    _create_connection(project_endpoint, server_url, function_key)
    conn_id = _connection_id(project_endpoint)
    version = _publish_toolbox(project_endpoint, server_url, conn_id)
    print(f"published {TOOLBOX_NAME} default_version -> {version}")
    print(f"gate tool: {SERVER_LABEL}.{TOOL_NAME} require_approval=never")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
