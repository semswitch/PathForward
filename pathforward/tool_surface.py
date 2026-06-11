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
            "`reasoning` model deployment. Its orchestrator toolbox exposes Tool Search and A2A "
            "SendMessage tools for the five specialist prompt agents."
        ),
        proof=(
            "pathforward/agents/versioned.py",
            "scripts/provision_foundry_specialist_agents.py --roles orchestrator",
            "scripts/provision_a2a_orchestrator_toolbox.py",
            ".agents/evidence/orchestrator-a2a-toolbox-live-2026-06-11.md",
            "tests/test_tool_surface.py",
        ),
    ),
    ToolSurfaceDecision(
        capability="orchestrator-and-specialist-skills",
        surface="Versioned Foundry specialist prompt agents with scoped Toolbox Skill content baked in",
        status="mainline-supporting-surface",
        rationale=(
            "The `/pathforward` Orchestrator Skill and specialist Skill files are registered in "
            "Foundry, attached to per-agent toolboxes, read through those toolbox MCP endpoints, "
            "and baked into durable Foundry specialist-agent versions. Product runtime calls named "
            "agent references; it does not inject Skill text at inference time."
        ),
        proof=(
            "scripts/build_toolbox.py --recreate",
            "scripts/provision_foundry_specialist_agents.py",
            "scripts/smoke_toolbox_skill_live.py",
            "pathforward/agents/versioned.py",
            "tests/test_skills.py",
        ),
    ),
    ToolSurfaceDecision(
        capability="generator-search-grounding",
        surface="Scoped generator toolbox plus Foundry PromptAgentDefinition Azure AI Search trace",
        status="accepted-mainline-seam",
        rationale=(
            "The generator has a scoped toolbox containing /pathforward-assess and Azure AI Search. "
            "The current specialist agent definition also attaches Azure AI Search directly because "
            "the assessment loop needs `azure_ai_search_call_output.documents[].id` for the "
            "`corpus ∩ retrieved` anti-bluff gate. Replacing that trace with toolbox MCP output "
            "requires a dedicated retrieval parser before it can be product-safe."
        ),
        proof=(
            "pathforward/agents/foundry.py:FoundryLLMClient",
            "scripts/smoke_toolbox_skill_live.py",
            "scripts/eval_orchestrator_live.py --no-judge",
        ),
    ),
    ToolSurfaceDecision(
        capability="fabric-program-insights",
        surface=("Foundry MicrosoftFabricPreviewTool for OBO/user runs; direct published Fabric "
                 "data-agent endpoint for service/background runs"),
        status="accepted-mainline-seam",
        rationale=(
            "Fabric Program Insights is advisory and off the credential mint path. User/OBO smoke "
            "runs use the documented prompt-agent Fabric tool; service/background runs use the "
            "published Fabric data-agent endpoint with an isolated service-principal token because "
            "the OBO preview tool cannot run under a background service identity. "
            "`iq/cohort.py` remains the reconciliation anchor in both routes."
        ),
        proof=(
            "pathforward/agents/foundry.py:FabricInsightsClient",
            "pathforward/agents/foundry.py:FabricDataAgentClient",
            "scripts/smoke_fabric_live.py",
            "prompt-agent migration pending live proof",
            "tests/test_fabric_insights.py",
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
