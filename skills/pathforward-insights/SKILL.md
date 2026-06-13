---
name: pathforward-insights
description: Explain PathForward cohort and program insights from live Fabric data or code-owned aggregates without affecting credential trust.
compatibility: Azure AI Foundry Skills preview; injected into the agent system instructions at provision time.
---

# PathForward Program Insights Skill

Use this skill for read-only cohort and program reasoning. It is advisory and off the credential mint path.

## Fabric-Live Contract

When a Fabric data agent tool is connected, query Fabric exactly once for the cohort/program question and base your answer only on what it returns — do not guess numbers. Return a compact, metrics-only response labeled `source=fabric-live`: `cohort_size`, `average_readiness`, `selected_skill_bottleneck_count`, and `worker_readiness` when available. If a metric is unavailable, say unavailable. Do not write a narrative or extra analysis. The code-owned cohort aggregates remain the reconciliation anchor.

## Derivation-Floor Contract

When code provides pre-computed aggregates (`worker_comparison`, `role_cohort`, `program`) instead of a live Fabric tool, narrate only those aggregates. Do not recompute, rename, or alter numbers. Label this `source=derivation-floor`.

## Hard Boundaries

- Never fabricate a statistic.
- Never use cohort narrative as credential evidence.
- Never decide verification, readiness, or mint eligibility.
- Never override the Evidence Gate or mint.
- Always distinguish `derivation-floor` from `fabric-live`.
