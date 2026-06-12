"""Versioned Foundry specialist-agent registry.

This module defines the durable Foundry prompt agents that back the product agent route. Skills are
loaded when these agents are provisioned, not at request time, so each specialist agent is visible as
a versioned Foundry agent with its own baked instructions/schema/tool surface.
"""
from __future__ import annotations

from dataclasses import dataclass

from .conductor import CONDUCTOR_INSTRUCTIONS, CONDUCTOR_SCHEMA
from .critic import CRITIC_SCHEMA, CRIT_INSTRUCTIONS
from .curator import CURATOR_SCHEMA, CUR_INSTRUCTIONS
from .generator import GEN_INSTRUCTIONS, ITEM_SCHEMA
from .insights import FABRIC_INS_INSTRUCTIONS
from .planner import PLAN_INSTRUCTIONS, PLANNER_SCHEMA


@dataclass(frozen=True)
class VersionedAgentSpec:
    role: str
    agent_name: str
    skill_name: str
    toolbox_name: str
    base_instructions: str
    schema: dict | None = None
    strict_schema: bool = False
    tool_surface: str = "reasoning"


VERSIONED_AGENT_SPECS: tuple[VersionedAgentSpec, ...] = (
    VersionedAgentSpec(
        role="orchestrator",
        agent_name="pathforward-orchestrator",
        skill_name="pathforward",
        toolbox_name="pathforward-orchestrator-toolbox",
        base_instructions=CONDUCTOR_INSTRUCTIONS,
        schema=CONDUCTOR_SCHEMA,
        tool_surface="reasoning",
    ),
    VersionedAgentSpec(
        role="curator",
        agent_name="pathforward-specialist-curator",
        skill_name="pathforward-curate",
        toolbox_name="pathforward-curator-toolbox",
        base_instructions=CUR_INSTRUCTIONS,
        schema=CURATOR_SCHEMA,
        tool_surface="reasoning",
    ),
    VersionedAgentSpec(
        role="generator",
        agent_name="pathforward-specialist-generator",
        skill_name="pathforward-assess",
        toolbox_name="pathforward-generator-toolbox",
        base_instructions=GEN_INSTRUCTIONS,
        schema=ITEM_SCHEMA,
        strict_schema=True,
        tool_surface="azure_ai_search",
    ),
    VersionedAgentSpec(
        role="critic",
        agent_name="pathforward-specialist-critic",
        skill_name="pathforward-assess",
        toolbox_name="pathforward-critic-toolbox",
        base_instructions=CRIT_INSTRUCTIONS,
        schema=CRITIC_SCHEMA,
        tool_surface="reasoning",
    ),
    VersionedAgentSpec(
        role="planner",
        agent_name="pathforward-specialist-planner",
        skill_name="pathforward-plan",
        toolbox_name="pathforward-planner-toolbox",
        base_instructions=PLAN_INSTRUCTIONS,
        schema=PLANNER_SCHEMA,
        tool_surface="reasoning",
    ),
    VersionedAgentSpec(
        role="insights",
        agent_name="pathforward-specialist-insights-fabric",
        skill_name="pathforward-insights",
        toolbox_name="pathforward-insights-fabric-toolbox",
        base_instructions=FABRIC_INS_INSTRUCTIONS,
        schema=None,
        tool_surface="fabric_mcp",
    ),
)


VERSIONED_AGENT_BY_ROLE = {spec.role: spec for spec in VERSIONED_AGENT_SPECS}


def versioned_agent_evidence() -> dict:
    """Serializable evidence that product roles map to versioned Foundry prompt agents."""
    return {
        "source": "foundry-versioned-agents",
        "agents": [
            {
                "role": spec.role,
                "agent_name": spec.agent_name,
                "skill": f"/{spec.skill_name}",
                "toolbox": spec.toolbox_name,
                "tool_surface": spec.tool_surface,
            }
            for spec in VERSIONED_AGENT_SPECS
        ],
    }


def versioned_agent_instructions(spec: VersionedAgentSpec, skill_body: str) -> str:
    """Compose the system instructions stored on the durable Foundry agent version."""
    return (
        f"{spec.base_instructions}\n\n"
        f"Loaded Foundry Skill `/{spec.skill_name}`:\n"
        f"{skill_body.strip()}\n\n"
        "This Skill is part of this versioned Foundry agent definition. Follow it exactly, while "
        "the structured output schema, deterministic validators, Evidence Gate, and mint boundary "
        "remain authoritative."
    )
