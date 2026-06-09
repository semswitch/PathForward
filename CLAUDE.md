# CLAUDE.md

This repository uses **[`AGENTS.md`](./AGENTS.md)** as the single source of truth for AI-agent
guidance. **Read `AGENTS.md` first** — it defines the project intent, the prime directives, the
trust hierarchy, the verification protocol, the current-vs-target state, and the invariants.

Then read **`.agents/plans/000-non-negotiable-agentic-architecture-contract.md`** before any
architecture, workflow, agent, Foundry-tooling, demo-proof, or scope decision. That contract
supersedes older plans, ADR interpretations, and summaries where they conflict. No workaround is
permitted unless the user explicitly authorizes it or a documented critical infrastructure blocker
prevents the required shape.

Claude-specific reminders (the substance lives in `AGENTS.md`):

- **Ground platform facts with the Microsoft Learn MCP** (`microsoft_docs_search` /
  `microsoft_docs_fetch`) before asserting any Azure / Foundry / SDK specifics. Do not rely on
  training data for version, feature, or GA-vs-preview details — verify, then cite source + date.
- Treat **`.agents/docs/current-state-assessment.md`** as the maintained ground-truth snapshot;
  its §10 lists repo claims that have already drifted from live docs (proof that assumptions are
  unsafe here).
- The end goal is the **real multi-agent reasoning loop**, not the one-off GPT call and not the
  `FakeLLMClient` stub. The chosen architecture is the Foundry-visible `/pathforward`
  Orchestrator Skill route. Agent Framework Workflow is locked out unless the user explicitly
  re-authorizes it. Do not call the full architecture
  complete while Orchestrator Skill/toolbox/MCP approval/Voice surfaces remain unproven or unbuilt
  under the hard contract. Preserve the `LLMClient` / `NumericChecker` swap-in seams and the
  deterministic Evidence Gate (never let an LLM judge its own grounding).
- Telemetry is available and should be used before inventing stream-output captures or local
  observability workarounds. Use `scripts/trace_full_flow.py` for the Orchestrator-driven proof
  trace and `scripts/trace_demo.py` for the focused assessment-loop trace; both export to Azure
  Monitor when configured. Azure-side query access was verified with the service principal identity
  from `.env` on
  2026-06-09. If a normal user CLI login gets `InsufficientAccessError`, switch to the service
  principal before concluding telemetry is blocked.

> Keep this file thin. Put substantive guidance in `AGENTS.md` so the two never drift.
