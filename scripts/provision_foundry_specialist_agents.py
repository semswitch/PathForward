"""Create durable Foundry prompt-agent versions for the PathForward specialist agents.

This replaces request-time Skill text injection with versioned Foundry agents. The script reads the
registered Skill resources from `pathforward-toolbox`, bakes each Skill into its matching agent
definition, attaches the required tool surface, and creates a new visible Foundry agent version.

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
    VERSIONED_AGENT_SPECS,
    versioned_agent_instructions,
)
from pathforward.config import load_settings  # noqa: E402
from pathforward.toolbox_mcp import read_skills_from_toolbox  # noqa: E402

TOOLBOX_NAME = "pathforward-toolbox"
SEARCH_CONNECTION = "pathforward-search"


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
    return AzureAISearchTool(azure_ai_search=AzureAISearchToolResource(indexes=[
        AISearchIndexResource(project_connection_id=conn_id, index_name=index_name,
                              query_type=AzureAISearchQueryType.SEMANTIC)
    ]))


def _fabric_tool(project, connection_name: str):
    from azure.ai.projects.models import (
        FabricDataAgentToolParameters, MicrosoftFabricPreviewTool, ToolProjectConnection,
    )
    conn_id = project.connections.get(connection_name).id
    return MicrosoftFabricPreviewTool(fabric_dataagent_preview=FabricDataAgentToolParameters(
        project_connections=[ToolProjectConnection(project_connection_id=conn_id)]
    ))


def _fabric_connection_name(project, configured: str) -> str:
    """Return the configured Fabric connection or discover the single approved Fabric data-agent connection."""
    if configured:
        return configured
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
    if spec.tool_surface == "azure_ai_search":
        return [_search_tool(project, settings.search_index)]
    if spec.tool_surface == "fabric_iq":
        return [_fabric_tool(project, _fabric_connection_name(project, settings.fabric_connection_name))]
    return []


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Provision versioned PathForward specialist prompt agents in Foundry."
    )
    ap.add_argument("--toolbox", default=TOOLBOX_NAME,
                    help="Foundry Toolbox name that exposes the PathForward Skill resources.")
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

    skill_names = tuple(spec.skill_name for spec in specs)
    skill_bodies, evidence = read_skills_from_toolbox(
        settings.foundry_project_endpoint, args.toolbox, skill_names,
    )
    missing = [name for name in skill_names if name not in skill_bodies]
    if missing:
        print(f"FAIL: missing Skill resources from toolbox {args.toolbox!r}: {missing}")
        return 1
    print(f"loaded Skills from toolbox {args.toolbox}: {sorted(skill_bodies)}")
    print(f"toolbox resources: {evidence.get('resources', [])}")

    from azure.ai.projects import AIProjectClient
    from azure.ai.projects.models import PromptAgentDefinition
    from azure.identity import DefaultAzureCredential

    project = AIProjectClient(
        endpoint=settings.foundry_project_endpoint,
        credential=DefaultAzureCredential(),
    )

    created = []
    for spec in specs:
        instructions = versioned_agent_instructions(spec, skill_bodies[spec.skill_name])
        text = _text_options(spec.schema, f"{spec.role}_output", spec.strict_schema)
        tools = _tools_for(spec, project, settings)
        definition = PromptAgentDefinition(
            model=settings.model_deployment,
            instructions=instructions,
            tools=tools,
            text=text,
        )
        agent = project.agents.create_version(
            agent_name=spec.agent_name,
            definition=definition,
            description=(
                f"PathForward versioned specialist agent: {spec.role}; "
                f"skill=/{spec.skill_name}; tool_surface={spec.tool_surface}."
            ),
        )
        created.append(agent)
        print(
            f"AGENT {agent.name} v{agent.version} id={agent.id} "
            f"skill=/{spec.skill_name} tool_surface={spec.tool_surface}"
        )

    print("created versioned specialist agents:")
    for agent in created:
        print(f"- {agent.name}: v{agent.version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
