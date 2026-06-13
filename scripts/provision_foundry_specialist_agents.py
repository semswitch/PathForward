"""Create durable Foundry prompt-agent versions for PathForward product agents.

This replaces request-time Skill text injection with versioned Foundry agents. The script reads each
agent's Skill from its repo-local `skills/<name>/SKILL.md` source, bakes the Skill into its matching
agent definition, attaches the required tool surface directly to the definition, and creates a new
visible Foundry agent version. Toolboxes are not used: Skills are injected at provision time and the
tool surface (Azure AI Search, the A2A links, and the route/gate/mint/fabric MCP tools) is attached
directly to each `PromptAgentDefinition`.

Usage:
    .venv\\Scripts\\python.exe scripts\\provision_foundry_specialist_agents.py
"""
from __future__ import annotations

import argparse
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from pathforward.agents.versioned import (  # noqa: E402
    VERSIONED_AGENT_BY_ROLE,
    VERSIONED_AGENT_SPECS,
    versioned_agent_instructions,
)
from pathforward.config import load_settings  # noqa: E402
from pathforward.skills import read_skill_file  # noqa: E402

SEARCH_CONNECTION = "pathforward-search"
MINT_CONNECTION = "pathforward-mint-mcp"
GATE_CONNECTION = "pathforward-gate-mcp"
ROUTE_CONNECTION = "pathforward-route-mcp"
FABRIC_MCP_CONNECTION = "pathforward-fabric-mcp"
A2A_CONNECTION_PREFIX = "pathforward-a2a"
A2A_ROLES = ("curator", "generator", "critic", "planner", "insights")


def _orchestrator_instructions(skill_body: str) -> str:
    # The `/pathforward` skill is the complete operational runbook (A2A specialist links + the
    # deterministic route/gate/mint tools); it IS the orchestrator's system instruction. No wrapper.
    return skill_body.strip()


def _a2a_base_url(project_endpoint: str, agent_name: str) -> str:
    return f"{project_endpoint.rstrip('/')}/agents/{agent_name}/endpoint/protocols/a2a/"


def _text_options(schema: dict | None, name: str, strict: bool):
    if not schema:
        return None
    from azure.ai.projects.models import (
        PromptAgentDefinitionTextOptions, TextResponseFormatJsonSchema,
    )
    return PromptAgentDefinitionTextOptions(format=TextResponseFormatJsonSchema(
        type="json_schema",
        name=name,
        schema=schema,
        strict=strict,
    ))


def _search_tool(project, index_name: str):
    from azure.ai.projects.models import (
        AISearchIndexResource, AzureAISearchQueryType, AzureAISearchTool, AzureAISearchToolResource,
    )
    conn_id = project.connections.get(SEARCH_CONNECTION).id
    return AzureAISearchTool(
        name="pathforward_search",
        description="Search the PathForward IQ corpus for grounded assessment evidence.",
        azure_ai_search=AzureAISearchToolResource(indexes=[
            AISearchIndexResource(project_connection_id=conn_id, index_name=index_name,
                                  query_type=AzureAISearchQueryType.SEMANTIC)
        ]),
    )


def _derived_fabric_mcp_url(settings) -> str:
    if settings.fabric_mcp_url:
        return settings.fabric_mcp_url
    if settings.mcp_mint_url and settings.mcp_mint_url.rstrip("/").endswith("/api/mcp"):
        return settings.mcp_mint_url.rstrip("/")[:-len("/api/mcp")] + "/api/fabric-mcp"
    return ""


def _derived_gate_mcp_url(settings) -> str:
    if settings.mcp_gate_url:
        return settings.mcp_gate_url
    if settings.mcp_mint_url and settings.mcp_mint_url.rstrip("/").endswith("/api/mcp"):
        return settings.mcp_mint_url.rstrip("/")[:-len("/api/mcp")] + "/api/gate-mcp"
    return ""


def _derived_route_mcp_url(settings) -> str:
    if settings.mcp_route_url:
        return settings.mcp_route_url
    if settings.mcp_mint_url and settings.mcp_mint_url.rstrip("/").endswith("/api/mcp"):
        return settings.mcp_mint_url.rstrip("/")[:-len("/api/mcp")] + "/api/route-mcp"
    return ""


def _fabric_tool(project, settings):
    from azure.ai.projects.models import MCPTool
    from pathforward.mcp.fabric_server import SERVER_LABEL, TOOL_NAME

    server_url = _derived_fabric_mcp_url(settings)
    if not server_url:
        raise RuntimeError("pathforward-specialist-insights-fabric requires FABRIC_MCP_URL")
    conn = project.connections.get(FABRIC_MCP_CONNECTION)
    return MCPTool(
        server_label=SERVER_LABEL,
        server_url=server_url,
        require_approval="never",
        allowed_tools=[TOOL_NAME],
        project_connection_id=conn.id,
    )


def _orchestrator_tools(project, settings):
    from azure.ai.projects.models import A2APreviewTool, MCPTool

    if not settings.mcp_mint_url:
        raise RuntimeError("pathforward-orchestrator requires MCP_MINT_URL")
    gate_url = _derived_gate_mcp_url(settings)
    if not gate_url:
        raise RuntimeError("pathforward-orchestrator requires MCP_GATE_URL or derivable MCP_MINT_URL")
    route_url = _derived_route_mcp_url(settings)
    if not route_url:
        raise RuntimeError("pathforward-orchestrator requires MCP_ROUTE_URL or derivable MCP_MINT_URL")

    from pathforward.mcp.route_server import SERVER_LABEL as ROUTE_LABEL, TOOL_NAME as ROUTE_TOOL

    route_conn = project.connections.get(ROUTE_CONNECTION)
    tools = [
        MCPTool(
            server_label=ROUTE_LABEL,
            server_url=route_url,
            require_approval="never",
            allowed_tools=[ROUTE_TOOL],
            project_connection_id=route_conn.id,
        )
    ]
    for role in A2A_ROLES:
        spec = VERSIONED_AGENT_BY_ROLE[role]
        conn = project.connections.get(f"{A2A_CONNECTION_PREFIX}-{role}")
        tools.append(
            A2APreviewTool(
                name=f"pathforward-a2a-{role}",
                description=f"Call the PathForward {role} specialist prompt agent.",
                base_url=_a2a_base_url(settings.foundry_project_endpoint, spec.agent_name),
                agent_card_path="agentCard/v0.3",
                project_connection_id=conn.id,
            )
        )

    from pathforward.mcp.gate_server import SERVER_LABEL as GATE_LABEL, TOOL_NAME as GATE_TOOL

    gate_conn = project.connections.get(GATE_CONNECTION)
    tools.append(
        MCPTool(
            server_label=GATE_LABEL,
            server_url=gate_url,
            require_approval="never",
            allowed_tools=[GATE_TOOL],
            project_connection_id=gate_conn.id,
        )
    )

    from pathforward.mcp.mint_server import SERVER_LABEL, TOOL_NAME

    mint_conn = project.connections.get(MINT_CONNECTION)
    tools.append(
        MCPTool(
            server_label=SERVER_LABEL,
            server_url=settings.mcp_mint_url,
            require_approval="always",
            allowed_tools=[TOOL_NAME],
            project_connection_id=mint_conn.id,
        )
    )
    return tools


def _fabric_connection_name(project, configured: str) -> str:
    """Return the configured Fabric connection or discover the single approved Fabric data-agent connection."""
    if configured:
        return configured
    try:
        project.connections.get("pathforward-fabric-user")
        return "pathforward-fabric-user"
    except Exception:  # noqa: BLE001
        pass
    candidates = []
    for conn in project.connections.list():
        if getattr(conn, "type", "") == "MicrosoftFabric":
            candidates.append(getattr(conn, "name", ""))
    preferred = [name for name in candidates
                 if name in {"pathforward-fabric-cohort", "pathforward-fabric-user"}]
    if len(preferred) == 1:
        return preferred[0]
    if "pathforward-fabric-cohort" in preferred:
        return "pathforward-fabric-cohort"
    if "pathforward-fabric-user" in preferred:
        return "pathforward-fabric-user"
    if len(candidates) == 1:
        return candidates[0]
    raise RuntimeError(
        "pathforward-specialist-insights-fabric requires FABRIC_CONNECTION_NAME when "
        f"Foundry has {len(candidates)} MicrosoftFabric connections: {candidates}"
    )


def _tools_for(spec, project, settings):
    if spec.role == "orchestrator":
        return _orchestrator_tools(project, settings)
    if spec.tool_surface == "azure_ai_search":
        return [_search_tool(project, settings.search_index)]
    if spec.tool_surface == "fabric_mcp":
        return [_fabric_tool(project, settings)]
    return []


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Provision versioned PathForward specialist prompt agents in Foundry."
    )
    ap.add_argument("--roles", nargs="*", default=None,
                    help="Optional subset of roles to provision, e.g. --roles insights.")
    args = ap.parse_args()

    settings = load_settings(os.path.join(_ROOT, ".env"))
    if not settings.foundry_project_endpoint:
        print("FAIL: AZURE_AI_PROJECT_ENDPOINT / FOUNDRY_PROJECT_ENDPOINT is required")
        return 1
    if not settings.model_deployment:
        print("FAIL: AZURE_AI_MODEL_DEPLOYMENT_NAME is required")
        return 1

    specs = VERSIONED_AGENT_SPECS
    if args.roles:
        wanted = set(args.roles)
        specs = tuple(spec for spec in VERSIONED_AGENT_SPECS if spec.role in wanted)
        missing_roles = sorted(wanted - {spec.role for spec in specs})
        if missing_roles:
            print(f"FAIL: unknown roles: {missing_roles}")
            return 1

    skill_bodies = {}
    for spec in specs:
        skill_path = os.path.join(_ROOT, "skills", spec.skill_name, "SKILL.md")
        try:
            skill = read_skill_file(skill_path)
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL: could not load /{spec.skill_name} from {skill_path}: "
                  f"{type(exc).__name__}: {exc}")
            return 1
        skill_bodies[spec.role] = skill.instructions
        print(f"loaded /{spec.skill_name} from "
              f"{os.path.relpath(skill_path, _ROOT).replace(os.sep, '/')}: "
              f"chars={len(skill.instructions)}")

    from azure.ai.projects import AIProjectClient
    from azure.ai.projects.models import PromptAgentDefinition, Reasoning
    from azure.identity import DefaultAzureCredential

    project = AIProjectClient(
        endpoint=settings.foundry_project_endpoint,
        credential=DefaultAzureCredential(),
    )

    created = []
    for spec in specs:
        if spec.role == "orchestrator":
            instructions = _orchestrator_instructions(skill_bodies[spec.role])
            text = None
        else:
            instructions = versioned_agent_instructions(spec, skill_bodies[spec.role])
            text = _text_options(spec.schema, f"{spec.role}_output", spec.strict_schema)
        tools = _tools_for(spec, project, settings)
        definition = PromptAgentDefinition(
            model=settings.model_deployment,
            instructions=instructions,
            tools=tools,
            reasoning=Reasoning(effort="low"),
            text=text,
        )
        agent = project.agents.create_version(
            agent_name=spec.agent_name,
            definition=definition,
            description=(
                f"PathForward versioned prompt agent: {spec.role}; "
                f"skill=/{spec.skill_name}; tool_surface={spec.tool_surface}."
            ),
        )
        created.append(agent)
        print(
            f"AGENT {agent.name} v{agent.version} id={agent.id} "
            f"skill=/{spec.skill_name} tool_surface={spec.tool_surface}"
        )

    print("created versioned prompt agents:")
    for agent in created:
        print(f"- {agent.name}: v{agent.version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
