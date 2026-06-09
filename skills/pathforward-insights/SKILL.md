---
name: pathforward-insights
description: Explain PathForward cohort and program insights from code-owned aggregates or live Fabric data without affecting credential trust.
compatibility: Azure AI Foundry Skills preview; consumed through Foundry Toolbox MCP resources or direct Foundry Skill download.
---

# PathForward Program Insights Skill

Use this skill for read-only cohort and program reasoning.

## Purpose

Program Insights explains how a worker compares with peers targeting the same role and which skills
are program bottlenecks. It is advisory and off the credential mint path.

## Derivation-Floor Contract

When code provides aggregates, narrate only those aggregates:

- `worker_comparison`
- `role_cohort`
- `program`

Do not recompute, rename, or alter numbers.

## Fabric-Live Contract

When a Fabric data agent is connected, query Fabric for cohort/program questions and label the result
as Fabric-live. The code-owned cohort aggregates remain the reconciliation anchor.

## Hard Boundaries

- Never fabricate a statistic.
- Never use cohort narrative as credential evidence.
- Never decide verification, readiness, or mint eligibility.
- Never override the Evidence Gate or mint.
- Always distinguish `derivation-floor` from `fabric-live`.
