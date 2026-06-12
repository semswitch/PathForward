"""Enable incoming A2A on specialists and attach them to the orchestrator toolbox.

This is the prompt-agent replacement for the removed container route:

1. PATCH each specialist prompt agent with an agent card and `responses` + `a2a` protocols.
2. Create RemoteA2A project connections pointing at each specialist A2A endpoint.
3. Create/promote a new `pathforward-orchestrator-toolbox` version with `/pathforward`, Tool Search,
   and the specialist A2A connections.

The A2A endpoints use Foundry prompt-agent endpoints, not custom containers.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from urllib import request

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from azure.identity import DefaultAzureCredential  # noqa: E402

from pathforward.agents.versioned import VERSIONED_AGENT_BY_ROLE  # noqa: E402
from pathforward.config import load_settings  # noqa: E402


A2A_AUDIENCE = "https://ai.azure.com"
ORCHESTRATOR_TOOLBOX = "pathforward-orchestrator-toolbox"
A2A_ROLES = ("curator", "generator", "critic", "planner", "insights")


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
    with request.urlopen(req, timeout=60) as resp:  # noqa: S310 - Azure project endpoint
        body = resp.read().decode("utf-8")
    return json.loads(body) if body else {}


def _run(cmd: list[str]) -> str:
    proc = subprocess.run(cmd, cwd=_ROOT, check=True, text=True, capture_output=True)
    if proc.stdout.strip():
        print(proc.stdout.strip())
    if proc.stderr.strip():
        print(proc.stderr.strip())
    return proc.stdout


def _a2a_url(project_endpoint: str, agent_name: str) -> str:
    return f"{project_endpoint.rstrip('/')}/agents/{agent_name}/endpoint/protocols/a2a/"


def _agent_card(role: str, agent_name: str) -> dict:
    skill_id = f"pathforward-{role}"
    return {
        "description": f"PathForward {role} specialist prompt agent.",
        "version": "1.0",
        "skills": [
            {
                "id": skill_id,
                "name": skill_id,
                "description": f"Handles the PathForward {role} responsibility through its Foundry Skill.",
            }
        ],
        "metadata": {
            "agent_name": agent_name,
            "pathforward_role": role,
            "protocol": "a2a",
        },
    }


def enable_incoming_a2a(project_endpoint: str, role: str, agent_name: str) -> dict:
    body = {
        "agent_card": _agent_card(role, agent_name),
        "agent_endpoint": {"protocols": ["responses", "a2a"]},
    }
    url = f"{project_endpoint.rstrip('/')}/agents/{agent_name}?api-version=v1"
    result = _json_request("PATCH", url, body)
    card = _json_request("GET", f"{_a2a_url(project_endpoint, agent_name)}agentCard/v0.3")
    print(f"A2A enabled: {agent_name} card_protocol={card.get('protocolVersion')}")
    return result


def create_a2a_connections(project_endpoint: str) -> list[str]:
    names = []
    for role in A2A_ROLES:
        agent_name = VERSIONED_AGENT_BY_ROLE[role].agent_name
        conn_name = f"pathforward-a2a-{role}"
        names.append(conn_name)
        _run([
            _exe("azd"), "ai", "connection", "create", conn_name,
            "--project-endpoint", project_endpoint,
            "--kind", "remote-a2a",
            "--target", _a2a_url(project_endpoint, agent_name),
            # User Entra Token is the working Foundry dashboard/OBO path. Agentic identity caused
            # toolbox card fetches to fail with 403 in local MCP validation.
            "--auth-type", "user-entra-token",
            "--audience", A2A_AUDIENCE,
            "--metadata", "agentCardPath=agentCard/v0.3",
            "--metadata", f"PathForwardRole={role}",
            "--force",
            "--no-prompt",
        ])
    return names


def create_orchestrator_toolbox(project_endpoint: str, connection_names: list[str]) -> None:
    connections_file = _ROOT / ".agents" / "temp" / "pathforward-orchestrator-a2a-connections.yaml"
    connections_file.parent.mkdir(parents=True, exist_ok=True)
    connection_lines = "\n".join(f"  - name: {name}" for name in connection_names)
    connections_file.write_text(
        "\n".join([
            "connections:",
            connection_lines,
            "",
        ]),
        encoding="utf-8",
    )
    output = _run([
        _exe("azd"), "ai", "toolbox", "connection", "add", ORCHESTRATOR_TOOLBOX,
        "--project-endpoint", project_endpoint,
        "--from-file", str(connections_file),
        "--output", "json",
        "--no-prompt",
    ])
    created = json.loads(output)
    raw_version = created.get("version")
    if isinstance(raw_version, dict):
        raw_version = raw_version.get("version")
    version = str(raw_version or "")
    if version:
        _run([
            _exe("azd"), "ai", "toolbox", "publish", ORCHESTRATOR_TOOLBOX, version,
            "--project-endpoint", project_endpoint,
            "--output", "json",
            "--no-prompt",
        ])
        print(f"Promoted {ORCHESTRATOR_TOOLBOX} default_version -> {version}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Provision PathForward specialist A2A tools.")
    ap.parse_args()

    settings = load_settings(str(_ROOT / ".env"))
    project_endpoint = settings.foundry_project_endpoint.strip()
    if not project_endpoint:
        print("FAIL: AZURE_AI_PROJECT_ENDPOINT / FOUNDRY_PROJECT_ENDPOINT is required")
        return 1

    for role in A2A_ROLES:
        spec = VERSIONED_AGENT_BY_ROLE[role]
        enable_incoming_a2a(project_endpoint, role, spec.agent_name)
    connections = create_a2a_connections(project_endpoint)
    create_orchestrator_toolbox(project_endpoint, connections)
    print("done. orchestrator toolbox now has Tool Search + specialist A2A connections.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
