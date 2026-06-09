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

**Current (verified 2026-06-09):**
- **Five code-orchestrated reasoning agents** — Curator, Generator, Critic, Planner, and the
  read-only Program Insights agent (`pathforward/agents/`), all live-capable on gpt-5.5
  (Generator search-grounded via `FoundryLLMClient`; the rest tool-less via
  `ReasoningFoundryClient`). The Evidence Gate (deterministic notary, formerly "Verifier"),
  the reflection/adaptive controllers, and the orchestrator are **deterministic code**, not agents.
- The default storyboard demo (`scripts/run_demo.py`) and fixture export (`scripts/export_web_fixture.py`)
  still run on **`FakeLLMClient`** for deterministic local rehearsal, but both now support `--live`
  to use live Foundry/Fabric clients and stamp fixture provenance. The **live gpt-5.5 path** is proven
  via `scripts/smoke_loop_live.py`, `scripts/smoke_multiagent_live.py`,
  `scripts/eval_groundedness.py`, and `scripts/redteam_live.py` (16/16 grounded + spine-intact,
  12/12 red-team held, 0% ASR with Critic + reflection ON).
- Numeric checks use `LocalNumericChecker` — the **sole** gate oracle, offline AND live. Code
  Interpreter is wired as a distinct **non-gating** advisory analyst (`agents/analyst.py`:
  `LocalAnalyst` offline / `CodeInterpreterAnalyst` live), NOT a gate-oracle swap-in (ADR 008).
  The **live Fabric data-agent tier is now proven** through `scripts/smoke_fabric_live.py`
  (`source="fabric-live"`, OBO user identity, MicrosoftFabricPreviewTool). Voice Live and MCP mint
  remain config-only.
- OpenTelemetry is a live-capable proof layer: `scripts/trace_demo.py` prints the local span tree and,
  when `AZURE_MONITOR_CONNECTION_STRING` is present, exports to Azure Monitor / Application Insights
  (`azure_export=on` verified 2026-06-09). It is evidence/demo telemetry, not part of the trust gate.
- The same chain is **also expressed as a Microsoft Agent Framework Workflow** (flag-gated
  `PF_WORKFLOW`; ADR 009). `agents/workflow.py` is a framework-agnostic graph spec whose **no-bypass
  trust property** (no path reaches the credential `mint` without the deterministic, Evidence-Gate-
  bearing `assess` loop) is a **graph-shape test**, proven offline (`tests/test_workflow_graph.py`).
  The live adapter `agents/workflow_foundry.py` projects that spec onto `agent_framework`
  (GA 1.0.0, 2026-04-02) and is **imported lazily** — the SDK is not provisioned here, so the offline
  suite stays green. `run_multiagent` remains the always-green in-process spine; the portal/YAML
  Workflows product is deliberately AVOIDED for the trust path (no first-class code node).

**Target (where changes should head):**
- A genuine **multi-agent reasoning loop** worthy of the "Reasoning Agents" track: keep
  Generator→Evidence Gate; add real reasoning agents (a **Critic** before the gate, a **Curator** for
  adjacency/gap reasoning, a **Planner** for capacity + accessibility, a read-only **Program Insights**
  agent for cohort/why-this-path), orchestrated in code. Plural agents that genuinely reason — not a
  single one-off GPT call. **(Done as of 2026-06-08 — all five exist; see `current-state-assessment.md`.)**
- **Program Insights live tier:** keep the live Fabric data-agent read path repeatable and documented
  (`FABRIC_CONNECTION_NAME` + OBO user identity); do not collapse it back into the derivation floor
  when making evidence claims.
- Keep the **live `FoundryLLMClient` / `ReasoningFoundryClient` / `FabricInsightsClient`** demo and
  web fixture export path working (`scripts/run_demo.py --live`, `scripts/export_web_fixture.py
  --live`), and keep provenance explicit (`live-foundry`, `fabric-live`, `offline-rehearsal`).
- Use Code Interpreter ONLY as a non-gating analyst (`CodeInterpreterAnalyst`) for second-opinion
  recompute + calibration explainability — never as the gate oracle (it is non-deterministic: the
  model writes the code). `LocalNumericChecker` stays the sole oracle. **(Seam landed 2026-06-08, ADR 008.)**
- Keep the deterministic **Evidence Gate** (`pathforward/agents/evidence_gate.py`) as the trust boundary — it must NOT become an LLM
  judging its own work.

## Stubs are temporary — preserve the seams

- `FakeLLMClient` exists for offline development, deterministic demos, and tests. It is **not the
  production agent path**. `LocalNumericChecker` is different: it is the production gate oracle both
  offline and live.
- The swap-in seams are `LLMClient` (`pathforward/agents/client.py`), `NumericChecker`
  (`pathforward/agents/numeric.py`, real impl `LocalNumericChecker` — the gate oracle stays code,
  there is intentionally no model-backed `NumericChecker`), and the non-gating `Analyst`
  (`pathforward/agents/analyst.py`, real impl `CodeInterpreterAnalyst`). Real `LLMClient`:
  `FoundryLLMClient` / `ReasoningFoundryClient`. **Keep these interfaces identical** so the reasoning
  logic is unchanged when swapping. Do not bake fake-only assumptions into the loop.
- The **Agent Framework Workflow** seam is `pathforward/agents/workflow.py` (the framework-agnostic
  spec + the no-bypass `trust_audit`, always offline-safe) and `workflow_foundry.py` (the live
  `agent_framework` projection, imported lazily only). The trust boundary in the Workflow is the
  deterministic `assess` executor (reuses `run_assessment_loop` — the SOLE `status="verified"` writer)
  and the `mint` executor (reuses `credential.mint.mint`). **Never** let the Workflow track write
  `status="verified"` itself or become a second trust authority; it must stay a projection.

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
