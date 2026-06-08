# CLAUDE.md

This repository uses **[`AGENTS.md`](./AGENTS.md)** as the single source of truth for AI-agent
guidance. **Read `AGENTS.md` first** — it defines the project intent, the prime directives, the
trust hierarchy, the verification protocol, the current-vs-target state, and the invariants.

Claude-specific reminders (the substance lives in `AGENTS.md`):

- **Ground platform facts with the Microsoft Learn MCP** (`microsoft_docs_search` /
  `microsoft_docs_fetch`) before asserting any Azure / Foundry / SDK specifics. Do not rely on
  training data for version, feature, or GA-vs-preview details — verify, then cite source + date.
- Treat **`.agents/docs/current-state-assessment.md`** as the maintained ground-truth snapshot;
  its §10 lists repo claims that have already drifted from live docs (proof that assumptions are
  unsafe here).
- The end goal is the **real multi-agent reasoning loop**, not the one-off GPT call and not the
  `FakeLLMClient` stub. Preserve the `LLMClient` / `NumericChecker` swap-in seams and the
  deterministic Evidence Gate (never let an LLM judge its own grounding).

> Keep this file thin. Put substantive guidance in `AGENTS.md` so the two never drift.
