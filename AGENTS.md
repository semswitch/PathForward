# AGENTS.md — Working agreement for AI agents

> Read this before doing anything in this repo. It defines the intent, the ground rules, and
> the verification protocol for any AI agent (Kiro, Claude, Copilot, etc.) working on
> PathForward. **This file is the single source of truth; `CLAUDE.md` points here.**

## What PathForward is (the North Star)

PathForward is a submission to the **Microsoft Agents League — Reasoning Agents** track. It
reasons over a skill-adjacency ontology to map a worker's transferable skills to in-demand
certifications, then runs a **grounded, cheat-resistant competency-verification loop** that
mints a citation-backed credential — and **refuses (ABSTAINs)** when it cannot ground and
verify. The differentiator is honesty: it would rather say "not yet" than issue a fake credential.

## Prime directives (do not violate)

1. **Verify platform facts against live docs — never assume.** Microsoft/Azure/Foundry
   capabilities, API versions, GA-vs-preview status, and SDK fields change often, and this
   repo's own docs have already drifted (see `.agents/docs/current-state-assessment.md` §10).
   Before asserting or coding against any such fact, verify it via the **Microsoft Learn MCP**
   and record the correction with a **source URL + date**.
2. **The target is a real agentic reasoning loop — not a one-off GPT call.** See
   "Current state → Target state."
3. **The Fake LLM and other stubs are TEMPORARY scaffolding.** Preserve the swap-in seams; do
   not design as if the stubs are permanent.
4. **Never weaken the trust boundary.** See "Invariants you must not break."
5. **Synthetic data only; no secrets or real resource IDs in tracked files.**

## Trust hierarchy (what to believe when sources conflict)

1. **Live Microsoft Learn docs** (via the Learn MCP) — authoritative for platform/SDK facts.
2. **Running code + passing tests in this repo** — authoritative for what the system *actually* does.
3. **`.agents/docs/current-state-assessment.md`** — the maintained snapshot of "what's real."
4. **`ARCHITECTURE.md` and `.agents/decisions/*`** — intent + rationale, but **may be dated**
   (they carry update notes; trust the notes over the original body).
5. **Model training data** — least trusted for version/feature specifics. Verify before relying.

## Verification protocol (the MCP)

- The grounding tool is the **Microsoft Learn MCP** — endpoint `https://learn.microsoft.com/api/mcp`
  (public, no auth). Configure it as a remote server in `.kiro/settings/mcp.json` (gitignored):
  ```json
  { "mcpServers": { "microsoft-learn": { "url": "https://learn.microsoft.com/api/mcp" } } }
  ```
  Tools: `microsoft_docs_search`, `microsoft_docs_fetch`, `microsoft_code_sample_search`. If the
  MCP is unavailable, fall back to web search restricted to `learn.microsoft.com`.
- Use it for: API versions, GA/preview status, SDK class/field existence, agent/tool
  capabilities, and region/model availability.
- When repo docs disagree with live docs: update `current-state-assessment.md` with the
  correction + source + date, and add a **dated note** to the relevant ADR rather than
  rewriting its history.

## Current state → Target state

**Current (verified 2026-06-08):**
- **Five code-orchestrated reasoning agents** — Curator, Generator, Critic, Planner, and the
  read-only Program Insights agent (`pathforward/agents/`), all live-capable on gpt-5.5
  (Generator search-grounded via `FoundryLLMClient`; the rest tool-less via
  `ReasoningFoundryClient`). The Evidence Gate (deterministic notary, formerly "Verifier"),
  the reflection/adaptive controllers, and the orchestrator are **deterministic code**, not agents.
- The default demo (`scripts/run_demo.py`) and the web fixture run on **`FakeLLMClient`**
  (deterministic stub). The **live gpt-5.5 path** is proven via `scripts/smoke_loop_live.py`,
  `scripts/eval_groundedness.py`, and `scripts/redteam_live.py` (16/16 grounded, 0% ASR).
- Numeric checks use `LocalNumericChecker` — the **sole** gate oracle, offline AND live. Code
  Interpreter is wired as a distinct **non-gating** advisory analyst (`agents/analyst.py`:
  `LocalAnalyst` offline / `CodeInterpreterAnalyst` live), NOT a gate-oracle swap-in (ADR 008).
  Voice Live, MCP mint, and the live Fabric data agent are config-only.

**Target (where changes should head):**
- A genuine **multi-agent reasoning loop** worthy of the "Reasoning Agents" track: keep
  Generator→Evidence Gate; add real reasoning agents (a **Critic** before the gate, a **Curator** for
  adjacency/gap reasoning, a **Planner** for capacity + accessibility, a read-only **Program Insights**
  agent for cohort/why-this-path), orchestrated in code. Plural agents that genuinely reason — not a
  single one-off GPT call. **(Done as of 2026-06-08 — all five exist; see `current-state-assessment.md`.)**
- **Program Insights live tier:** promote the cohort read-path from the derivation floor to a live
  Fabric data agent over OneLake (`FabricTool`, OBO) when F2 capacity is un-paused (ADR 007).
- Wire the **live `FoundryLLMClient`** into the demo and the web UI (not just smoke tests), and
  re-export the web fixture from a live run.
- Use Code Interpreter ONLY as a non-gating analyst (`CodeInterpreterAnalyst`) for second-opinion
  recompute + calibration explainability — never as the gate oracle (it is non-deterministic: the
  model writes the code). `LocalNumericChecker` stays the sole oracle. **(Seam landed 2026-06-08, ADR 008.)**
- Keep the deterministic **Evidence Gate** (`pathforward/agents/evidence_gate.py`) as the trust boundary — it must NOT become an LLM
  judging its own work.

## Stubs are temporary — preserve the seams

- `FakeLLMClient` / `LocalNumericChecker` exist for offline development, deterministic demos, and
  tests. **They are not the product.**
- The swap-in seams are `LLMClient` (`pathforward/agents/client.py`), `NumericChecker`
  (`pathforward/agents/numeric.py`, real impl `LocalNumericChecker` — the gate oracle stays code,
  there is intentionally no model-backed `NumericChecker`), and the non-gating `Analyst`
  (`pathforward/agents/analyst.py`, real impl `CodeInterpreterAnalyst`). Real `LLMClient`:
  `FoundryLLMClient` / `ReasoningFoundryClient`. **Keep these interfaces identical** so the reasoning
  logic is unchanged when swapping. Do not bake fake-only assumptions into the loop.

## Invariants you must not break

- The **`corpus ∩ retrieved`** grounding gate in `loop.py` — a citation counts only if it is both
  approved corpus AND actually returned by the retrieval tool trace. This is the anti-bluff core.
- **Fail-closed**: exhausting attempts (N=3) → **ABSTAIN**, never a silent pass.
- **Causal spine**: the minted credential cites the SAME driving CertGap edge.
- **Voice/text parity**: one scorer over `FinalTurnTranscript` (`pathforward/scorer.py`).
- The **offline test suite must stay green**: `python -m unittest discover -s tests -t .`.

## Build / test / run

```bash
python scripts/generate_data.py            # synthetic ontology + responses -> data/generated/
python scripts/build_mirror.py             # materialize the Search-mirror docs
python scripts/run_demo.py                 # offline end-to-end demo (hero worker EMP-001)
python -m unittest discover -s tests -t .  # the guarantees (derivation, loop, gate, parity, credential)
```
Task runner: `./tasks.ps1 test|demo` (Windows) or `make test|demo`.
Web UI: `cd web && npm install && npm run dev` (reads `web/src/lib/fixture.json`; regenerate with
`python scripts/export_web_fixture.py`).

## Safety / Responsible AI

- **Synthetic data only** (`EMP-001`, `S01`, `AZ-204`, …). No real people or PII.
- **Grounded refusal, fail-closed mint, and human-in-the-loop** are product features, not bugs.
  See `RESPONSIBLE-AI.md`.
- **Secrets:** `.env` is gitignored — never commit it. Do not put real resource IDs, endpoints,
  or keys in tracked files (use placeholders + `.env`). Reference secrets by key name, not value.

## Definition of done for a change

1. Offline tests are green.
2. Any Microsoft/Azure fact the change relies on was verified via the Learn MCP (source + date noted).
3. It does not weaken the trust boundary or break a swap-in seam.
4. If the "what's real" picture changed, `.agents/docs/current-state-assessment.md` was updated.
