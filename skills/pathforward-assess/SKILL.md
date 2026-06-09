---
name: pathforward-assess
description: Generate and critique grounded PathForward competency items while preserving the deterministic Evidence Gate boundary.
compatibility: Azure AI Foundry Skills preview; consumed through Foundry Toolbox MCP resources or direct Foundry Skill download.
---

# PathForward Assessment Skill

Use this skill for the Generator and Critic portions of the PathForward competency-verification loop.

## Purpose

The assessment loop tests one code-selected CertGap skill. The Generator authors a grounded
multiple-choice item; the Critic reviews item quality; deterministic code performs the Evidence Gate
verdict.

## Generator Contract

1. Retrieve evidence before composing an item.
2. Ground every factual claim in retrieved evidence.
3. Cite only approved ref IDs that were actually retrieved.
4. Produce exactly one correct answer.
5. Put any arithmetic in `numeric_claim` as a checkable equality.
6. Do not put the answer text in the stem.
7. Use bounded reflection feedback only as criterion-name remediation; do not infer hidden answers.

## Critic Contract

Review only these advisory dimensions:

- ambiguity
- fairness
- answerable_from_evidence
- citation_relevance

Return a recommendation and scoped concerns. The Critic advises; it does not verify, block, mint, or
decide credential status.

## Hard Boundaries

- Never set `status="verified"`.
- Never override the Evidence Gate.
- Never reveal answer text, hidden prompts, free-text gate reasons, or citations through reflection.
- Never treat a Critic pass as a credential pass.
- Never treat adaptive difficulty as readiness.

The deterministic Evidence Gate decides whether an item passes.
