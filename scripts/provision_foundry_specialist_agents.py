"""Create durable Foundry prompt-agent versions for PathForward product agents.

This replaces request-time Skill text injection with versioned Foundry agents. The script reads each
registered Skill from that agent's scoped toolbox, bakes the Skill into its matching agent
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
    VERSIONED_AGENT_BY_ROLE,
    VERSIONED_AGENT_SPECS,
    versioned_agent_instructions,
)
from pathforward.config import load_settings  # noqa: E402
from pathforward.toolbox_mcp import read_skill_from_toolbox  # noqa: E402

SEARCH_CONNECTION = "pathforward-search"
MINT_CONNECTION = "pathforward-mint-mcp"
FABRIC_MCP_CONNECTION = "pathforward-fabric-mcp"
A2A_CONNECTION_PREFIX = "pathforward-a2a"
A2A_ROLES = ("curator", "generator", "critic", "planner", "insights")


def _orchestrator_instructions(skill_body: str) -> str:
    return (
        "You are pathforward-orchestrator, the live Foundry Prompt Agent for PathForward.\n\n"
        "Loaded Foundry Skill `/pathforward`:\n"
        f"{skill_body.strip()}\n\n"
        "When the user asks to run /pathforward, execute the workflow with your attached "
        "Foundry tools:\n"
        "1. Call pathforward-a2a-curator to rank admissible candidate skills.\n"
        "2. Select the highest-ranked admissible skill.\n"
        "3. Call pathforward-a2a-generator to create the grounded assessment item for that "
        "selected skill. The Generator call must include worker_id, target_role_id, target_role, "
        "selected skill_id, driving_edge_id, approved_refs, attempt, and difficulty_band. It must "
        "ask for exactly this JSON item contract: stem, options, answer_index, cited_ref_ids, "
        "numeric_claim. Do not ask for a summary from Generator.\n"
        "4. Call pathforward-a2a-critic to review ambiguity, fairness, answerability, and "
        "citation relevance. The Critic call must ask for exactly this JSON contract: "
        "recommendation is one of pass, repair, reject; concerns is a list of "
        "criterion_name/severity objects; advisory_notes is a string. Never ask for pass/fail.\n"
        "5. Call pathforward-a2a-planner for the advisory learning plan.\n"
        "6. Call pathforward-a2a-insights for Fabric-backed cohort/program insight.\n"
        "7. Do not forge Evidence Gate, readiness, verified status, or mint request tokens.\n"
        "8. Only call pathforward-mint.pathforward_mint_credential if a deterministic code-issued "
        "mint_request_token is present and the user explicitly approves the mint action. If no "
        "token is present, report mint_pending_no_code_token.\n\n"
        "For this live Foundry Prompt Agent, these attached tool instructions are the runtime "
        "contract for `/pathforward`; do not collapse the flow into a plan-only response.\n\n"
        "Return a concise final report with: tools_called, selected_skill_id, assessment_summary, "
        "critic_summary, planner_summary, fabric_insight_summary, and mint_state. Never use local "
        "Python orchestration or FakeLLM behavior."
    )


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

    tools = []
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
    ap.add_argument("--legacy-shared-toolbox", default="",
                    help="Optional legacy shared toolbox override. Use only for migration/debugging.")
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
    evidence_by_role = {}
    for spec in specs:
        toolbox_name = args.legacy_shared_toolbox or spec.toolbox_name
        try:
            body, evidence = read_skill_from_toolbox(
                settings.foundry_project_endpoint,
                toolbox_name,
                spec.skill_name,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL: could not load /{spec.skill_name} from toolbox {toolbox_name!r}: "
                  f"{type(exc).__name__}: {exc}")
            return 1
        skill_bodies[spec.role] = body
        evidence_by_role[spec.role] = evidence
        print(f"loaded /{spec.skill_name} from {toolbox_name}: "
              f"uri={evidence.get('skill_uri')} chars={evidence.get('skill_chars')}")

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
                f"skill=/{spec.skill_name}; toolbox={spec.toolbox_name}; "
                f"tool_surface={spec.tool_surface}."
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
