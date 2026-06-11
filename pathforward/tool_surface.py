"""Mainline tool-surface contract for the Hosted `/pathforward` Orchestrator route.

This module is documentation-as-code: it records which Microsoft Foundry surface each live
capability is allowed to use. Approval/mint architecture is intentionally not decided here; follow
`.agents/plans/000-non-negotiable-agentic-architecture-contract.md` for that boundary.
"""
from __future__ import annotations

from dataclasses import dataclass


MAINLINE_ROUTE = "foundry-hosted-orchestrator"


@dataclass(frozen=True)
class ToolSurfaceDecision:
    capability: str
    surface: str
    status: str
    rationale: str
    proof: tuple[str, ...]


TOOL_SURFACE_DECISIONS: tuple[ToolSurfaceDecision, ...] = (
    ToolSurfaceDecision(
        capability="hosted-orchestrator",
        surface="Foundry Hosted Agent (`agent.yaml` + Dockerfile + responses protocol)",
        status="mainline-live-proven",
        rationale=(
            "The user locked Hosted Agents as the top-level Orchestrator path. The hosted surface "
            "packages the existing PathForward route into a versionable Foundry Hosted Agent while "
            "preserving the deterministic Evidence Gate and mint spine. Hosted Agent version 18 "
            "completed the full live `/pathforward` route through the Foundry responses endpoint."
        ),
        proof=(
            "agent.yaml",
            "Dockerfile",
            "hosted/pathforward_orchestrator/main.py",
            "pathforward/hosted_orchestrator.py",
            "Hosted Agent pathforward-orchestrator:18",
            "tests/test_hosted_orchestrator.py",
        ),
    ),
    ToolSurfaceDecision(
        capability="orchestrator-and-specialist-skills",
        surface="Versioned Foundry specialist prompt agents with Toolbox Skill content baked in",
        status="mainline-supporting-surface",
        rationale=(
            "The `/pathforward` Orchestrator Skill and specialist Skill files are registered in "
            "Foundry, attached to `pathforward-toolbox`, read through the toolbox MCP endpoint, and "
            "baked into durable Foundry specialist-agent versions. Product runtime calls named "
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
        surface="Direct Foundry PromptAgentDefinition Azure AI Search tool",
        status="accepted-mainline-seam",
        rationale=(
            "Azure AI Search is a documented first-class Foundry prompt-agent tool. The assessment "
            "loop needs the Search tool trace (`azure_ai_search_call_output.documents[].id`) for the "
            "`corpus ∩ retrieved` anti-bluff gate. Moving this to toolbox MCP would require a custom "
            "MCP tool-calling loop or Hosted Agent path and is not the chosen architecture slice."
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
                 "data-agent endpoint for Hosted/background runs"),
        status="accepted-mainline-seam",
        rationale=(
            "Fabric Program Insights is advisory and off the credential mint path. User/OBO smoke "
            "runs use the documented prompt-agent Fabric tool; Hosted/background runs use the "
            "published Fabric data-agent endpoint with an isolated service-principal token because "
            "the OBO preview tool cannot run under a background hosted container identity. "
            "`iq/cohort.py` remains the reconciliation anchor in both routes."
        ),
        proof=(
            "pathforward/agents/foundry.py:FabricInsightsClient",
            "pathforward/agents/foundry.py:FabricDataAgentClient",
            "scripts/smoke_fabric_live.py",
            "Hosted Agent pathforward-orchestrator:18",
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
