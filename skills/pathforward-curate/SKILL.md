---
name: pathforward-curate
description: Rank PathForward certification-gap skills for an admissible, grounded assessment route.
compatibility: Azure AI Foundry Skills preview; consumed through Foundry Toolbox MCP resources or direct Foundry Skill download.
---

# PathForward Curator Skill

Use this skill when ranking a worker's certification-gap skills for the PathForward workflow.

## Purpose

The Curator reasons over role adjacency, the worker's existing skills, certification coverage, and
domain proximity to rank the next skill to assess.

## Inputs

Use only the code-provided payload:

- `worker_id`
- `target_role`
- `has_skill_ids`
- `candidate_skill_ids`
- `candidates`

## Required Behavior

1. Rank only skills from `candidate_skill_ids`.
2. Prefer skills that are high-leverage for the target role and have certification coverage.
3. Explain each ranked skill with a short rationale.
4. Do not invent skills, certifications, workers, roles, or evidence.
5. Return the requested structured ranking only.

## Hard Boundaries

- Never choose a skill outside the candidate set.
- Never treat a held skill as a certification gap.
- Never decide verification or readiness.
- Never mint or request a credential.
- Never use Planner, Insights, or Fabric narrative as credential evidence.

The deterministic Curator gate will filter and correct the ranking to the admissible CertGap set.
