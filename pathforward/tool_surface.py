"""Mainline tool-surface contract for the Prompt Agent `/pathforward` Orchestrator route.

This module is documentation-as-code: it records which Microsoft Foundry surface each live
capability is allowed to use. Approval/mint architecture is intentionally not decided here; follow
`.agents/plans/000-non-negotiable-agentic-architecture-contract.md` for that boundary.
"""
from __future__ import annotations

from dataclasses import dataclass


MAINLINE_ROUTE = "foundry-prompt-orchestrator"


@dataclass(frozen=True)
class ToolSurfaceDecision:
    capability: str
    surface: str
    status: str
    rationale: str
    proof: tuple[str, ...]


TOOL_SURFACE_DECISIONS: tuple[ToolSurfaceDecision, ...] = (
    ToolSurfaceDecision(
        capability="prompt-orchestrator",
        surface="Foundry Prompt Agent (`pathforward-orchestrator`) on the `reasoning` deployment",
        status="mainline-a2a-toolbox-live",
        rationale=(
            "`pathforward-orchestrator` is a Foundry Prompt Agent connected to the existing "
            "`reasoning` model deployment. Its A2A links to the five specialist prompt agents and "
            "its route/gate/mint MCP tools are attached directly to its PromptAgentDefinition; no "
            "toolbox is involved at runtime."
        ),
        proof=(
            "pathforward/agents/versioned.py",
            "scripts/provision_foundry_specialist_agents.py --roles orchestrator",
            "scripts/provision_specialist_a2a.py",
            ".agents/evidence/orchestrator-a2a-toolbox-live-2026-06-11.md",
            "tests/test_tool_surface.py",
        ),
    ),
    ToolSurfaceDecision(
        capability="orchestrator-and-specialist-skills",
        surface="Versioned Foundry specialist prompt agents with their registered Skill content baked in",
        status="mainline-supporting-surface",
        rationale=(
            "The `/pathforward` Orchestrator Skill and specialist Skill files are registered in "
            "Foundry for portal visibility (register_skills.py) and injected directly into durable "
            "Foundry specialist-agent versions from their local skills/<name>/SKILL.md sources at "
            "provision time. Product runtime calls named agent references; it does not inject Skill "
            "text at inference time and does not use toolboxes."
        ),
        proof=(
            "scripts/register_skills.py",
            "scripts/provision_foundry_specialist_agents.py",
            "scripts/provision_specialist_a2a.py",
            "pathforward/agents/versioned.py",
            "tests/test_skills.py",
        ),
    ),
    ToolSurfaceDecision(
        capability="generator-search-grounding",
        surface="Foundry PromptAgentDefinition Azure AI Search trace attached directly to the generator agent",
        status="accepted-mainline-seam",
        rationale=(
            "The generator specialist agent attaches Azure AI Search directly to its "
            "PromptAgentDefinition because the assessment loop needs "
            "`azure_ai_search_call_output.documents[].id` for the `corpus ∩ retrieved` anti-bluff "
            "gate. The Search tool is attached directly to the agent definition, not delivered "
            "through a toolbox."
        ),
        proof=(
            "pathforward/agents/foundry.py:FoundryLLMClient",
            "scripts/provision_foundry_specialist_agents.py",
            "scripts/eval_orchestrator_live.py --no-judge",
        ),
    ),
    ToolSurfaceDecision(
        capability="fabric-program-insights",
        surface=("Foundry MCP tool backed by the published Fabric data-agent REST endpoint using "
                 "service-principal authentication"),
        status="accepted-mainline-seam",
        rationale=(
            "Fabric Program Insights is advisory and off the credential mint path. The live product "
            "tool calls the published Fabric data-agent REST endpoint with an isolated "
            "service-principal token through the `pathforward-fabric` MCP server. `iq/cohort.py` "
            "remains the reconciliation anchor."
        ),
        proof=(
            "pathforward/mcp/fabric_server.py",
            "pathforward/agents/foundry.py:FabricDataAgentClient",
            "functions/mint_mcp/function_app.py:pathforward_fabric_mcp",
            "tests/test_fabric_insights.py",
            "tests/test_mcp_fabric_server.py",
        ),
    ),
    ToolSurfaceDecision(
        capability="agent-framework-workflow",
        surface="Locked-out architecture surface",
        status="locked-out-not-used",
        rationale=(
            "The user locked the decision on 2026-06-09: PathForward is not using Agent Framework "
            "Workflow as an architecture surface. Do not build on it without explicit "
            "re-authorization."
        ),
        proof=("architecture contract",),
    ),
)


def decisions_by_capability() -> dict[str, ToolSurfaceDecision]:
    return {d.capability: d for d in TOOL_SURFACE_DECISIONS}
