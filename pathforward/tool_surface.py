"""Mainline tool-surface contract for the Hosted `/pathforward` Orchestrator route.

This module is documentation-as-code: it records which Microsoft Foundry surface each live
capability is allowed to use. Tests lock these decisions so future work does not reopen optional
surfaces, especially Agent Framework Workflow, as if they were required architecture work.
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
            "preserving the deterministic Evidence Gate and mint spine. Hosted Agent version 11 "
            "completed the full live `/pathforward` route through the Foundry responses endpoint."
        ),
        proof=(
            "agent.yaml",
            "Dockerfile",
            "hosted/pathforward_orchestrator/main.py",
            "pathforward/hosted_orchestrator.py",
            "Hosted Agent pathforward-orchestrator:11",
            "tests/test_hosted_orchestrator.py",
        ),
    ),
    ToolSurfaceDecision(
        capability="orchestrator-and-specialist-skills",
        surface="Foundry Toolbox MCP resources (`resources/list` + `resources/read`)",
        status="mainline-supporting-surface",
        rationale=(
            "The `/pathforward` Orchestrator Skill and specialist Skill files are registered in "
            "Foundry, attached to `pathforward-toolbox`, read through the toolbox MCP endpoint, and "
            "loaded by the Hosted Orchestrator path before it runs the specialist agents."
        ),
        proof=(
            "scripts/build_toolbox.py --recreate",
            "scripts/smoke_toolbox_skill_live.py",
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
            "Hosted Agent pathforward-orchestrator:11",
            "tests/test_fabric_insights.py",
        ),
    ),
    ToolSurfaceDecision(
        capability="credential-approval",
        surface="Hosted Agent governed approval wrapper",
        status="hosted-live-approval-request-proven",
        rationale=(
            "`credential.approval` correctly fails closed before mint. The Hosted Orchestrator now "
            "creates a mint approval request and mints only with explicit runtime approval. Hosted "
            "Agent version 11 proved the live approval-request path; hosted evals and an explicit "
            "approval-approved live run remain separate proof work."
        ),
        proof=(
            "pathforward/credential/approval.py",
            "pathforward/hosted_orchestrator.py",
            "Hosted Agent pathforward-orchestrator:11",
            "scripts/smoke_mint_approval.py",
            "tests/test_hosted_orchestrator.py",
            "tests/test_mint_approval.py",
        ),
    ),
    ToolSurfaceDecision(
        capability="agent-framework-workflow",
        surface="Locked-out historical reference only",
        status="locked-out-not-used",
        rationale=(
            "The user locked the decision on 2026-06-09: PathForward is not using Agent Framework "
            "Workflow as an architecture surface. Keep old graph proof code only as historical "
            "reference; do not build on it without explicit re-authorization."
        ),
        proof=(
            "pathforward/agents/workflow.py",
            "scripts/smoke_workflow_live.py",
        ),
    ),
)


def decisions_by_capability() -> dict[str, ToolSurfaceDecision]:
    return {d.capability: d for d in TOOL_SURFACE_DECISIONS}
