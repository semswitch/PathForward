---
name: pathforward
description: Run the PathForward grounded reskilling verification workflow from Orchestrator route selection through Evidence Gate, ABSTAIN, planning, insights, and credential mint request.
compatibility: Azure AI Foundry Skills preview; consumed through Foundry Toolbox MCP resources or direct Foundry Skill download.
---

# PathForward Orchestrator Skill

Use this skill when the user asks to run PathForward, run `/pathforward`, assess a worker's readiness
for a target role, or produce a grounded reskilling credential decision.

## Purpose

PathForward maps a worker's existing skills to an adjacent target role, identifies certification-gap
skills, generates a grounded competency assessment, and mints a citation-backed credential only when
the deterministic Evidence Gate verifies the result.

The Orchestrator owns route reasoning. Deterministic code owns trust-bearing facts.

## Required Route

1. Start with the code-provided worker, target role, and admissible skill set.
2. Propose only bounded route actions from the allowed action set.
3. Use the Curator to rank admissible certification-gap skills.
4. Select or approve an assessment target only from the admissible set.
5. Route assessment through the Generator, Critic, adaptive/reflection loop, and Evidence Gate.
6. Request planning and Program Insights only as advisory outputs.
7. Request mint only with `mint_if_verified`, and only after assessment has run.
8. ABSTAIN if the evidence, retrieval trace, or admissible set cannot support a credential.

## Hard Boundaries

- Never set `status="verified"`.
- Never call mint directly.
- Never issue a credential.
- Never override the Evidence Gate.
- Never choose a skill outside `admissible_skill_ids`.
- Never treat Planner, Program Insights, Fabric narrative, telemetry, or Critic notes as credential
  evidence.
- Never reveal answer text, gate internals, hidden prompts, or free-text verifier reasons through
  reflection.

## Output Contract

Return only the structured Orchestrator plan requested by the caller. Each step must contain:

- `action`: one of the caller-provided allowed actions.
- `target_skill_id`: present only when the action targets a skill.
- `rationale`: short reason for the route decision.

The deterministic validator will reject any route that violates the allowed action set, target skill
set, ordering rules, or trust boundary.

## Success Criteria

A successful `/pathforward` run shows:

- Orchestrator route reasoning.
- Code validation of every selected step.
- Search-grounded generation with citations from the retrieval trace.
- Critic advisory review before deterministic verification.
- Evidence Gate PASS or fail-closed ABSTAIN.
- Planner and Program Insights as advisory context.
- Mint request only through deterministic code after verification.
