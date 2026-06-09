"""Mainline tool-surface contract for the `/pathforward` Orchestrator Skill route.

This module is documentation-as-code: it records which Microsoft Foundry surface each live
capability is allowed to use. Tests lock these decisions so future work does not reopen optional
surfaces, especially Agent Framework Workflow, as if they were required architecture work.
"""
from __future__ import annotations

from dataclasses import dataclass


MAINLINE_ROUTE = "foundry-orchestrator-skill"


@dataclass(frozen=True)
class ToolSurfaceDecision:
    capability: str
    surface: str
    status: str
    rationale: str
    proof: tuple[str, ...]


TOOL_SURFACE_DECISIONS: tuple[ToolSurfaceDecision, ...] = (
    ToolSurfaceDecision(
        capability="orchestrator-and-specialist-skills",
        surface="Foundry Toolbox MCP resources (`resources/list` + `resources/read`)",
        status="mainline",
        rationale=(
            "The `/pathforward` Orchestrator Skill and specialist Skill files are registered in "
            "Foundry, attached to `pathforward-toolbox`, read through the toolbox MCP endpoint, and "
            "injected into the live Orchestrator/agent prompts."
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
        surface="Direct Foundry PromptAgentDefinition MicrosoftFabricPreviewTool",
        status="accepted-mainline-seam",
        rationale=(
            "Fabric Program Insights is advisory and off the credential mint path. The live tier uses "
            "the documented prompt-agent Fabric tool with OBO identity, while `iq/cohort.py` remains "
            "the reconciliation anchor."
        ),
        proof=(
            "pathforward/agents/foundry.py:FabricInsightsClient",
            "scripts/smoke_fabric_live.py",
            "tests/test_fabric_insights.py",
        ),
    ),
    ToolSurfaceDecision(
        capability="credential-approval",
        surface="Local governed approval wrapper; Orchestrator-route MCP/Hosted approval still open",
        status="open-or-explicitly-defer",
        rationale=(
            "`credential.approval` correctly fails closed before mint, but the chosen `/pathforward` "
            "Orchestrator route does not yet expose approval through a Foundry MCP or Hosted surface."
        ),
        proof=(
            "pathforward/credential/approval.py",
            "scripts/smoke_mint_approval.py",
            "tests/test_mint_approval.py",
        ),
    ),
    ToolSurfaceDecision(
        capability="agent-framework-workflow",
        surface="Optional/reference projection only",
        status="do-not-invest-without-user-authorization",
        rationale=(
            "Workflow has a no-bypass graph proof and one HITL smoke, but the chosen architecture is "
            "the Foundry-visible `/pathforward` Orchestrator Skill route."
        ),
        proof=(
            "pathforward/agents/workflow.py",
            "scripts/smoke_workflow_live.py",
        ),
    ),
)


def decisions_by_capability() -> dict[str, ToolSurfaceDecision]:
    return {d.capability: d for d in TOOL_SURFACE_DECISIONS}

