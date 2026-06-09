# AGENTS.md — Working agreement for AI agents

> Read this before doing anything in this repo. It defines the intent, the ground rules, and
> the verification protocol for any AI agent (Kiro, Claude, Copilot, etc.) working on
> PathForward. **This file is the single source of truth; `CLAUDE.md` points here.**
>
> **Hard architecture contract:** before planning or implementing architecture work, read
> `.agents/plans/000-non-negotiable-agentic-architecture-contract.md`. That contract supersedes
> older plans, roadmap notes, ADR interpretations, and summaries where they conflict. Do not bypass
> it without explicit user authorization or a documented critical infrastructure blocker.

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
  the reflection/adaptive controllers, and the original `run_multiagent` orchestrator are
  **deterministic code**, not agents.
  This is a real multi-agent live path, but it is still code-orchestrated; it is not the final
  full architecture shape described in the hard contract.
- **Bounded Orchestrator/Conductor is implemented and live-smoke-proven** (`pathforward/agents/conductor.py`,
  `run_orchestrated_multiagent`, `scripts/smoke_orchestrator_live.py`). It is an `LLMClient`-backed
  route reasoner with a deterministic validator: the agent may propose `curate` / `assess` / `plan`
  / `insights` / `mint_if_verified`, but code rejects forbidden actions, non-admissible skills, and
  any attempt to bypass the Evidence Gate. Live smoke on 2026-06-09 used `pathforward-orchestrator`
  to select admissible S08 and mint through the existing code spine. Orchestrator-specific safety was
  re-measured on 2026-06-09 with the MCP-loaded `/pathforward` skill: 16/16 grounded + spine-intact
  and 16/16 red-team defenses held, ASR 0.0% (`scripts/eval_orchestrator_live.py`,
  `eval/orchestrator-groundedness.*`, `eval/orchestrator-redteam-asr.*`).
- **The `/pathforward` Foundry Skill is now real and load-bearing for the Orchestrator path**
  (`skills/pathforward/SKILL.md`, `scripts/build_toolbox.py`, `scripts/smoke_toolbox_skill_live.py`).
  The skill source follows the `agentskills.io` `SKILL.md` shape, is registered as the Foundry Skill
  `pathforward`, attached to `pathforward-toolbox`, exposed through the toolbox MCP endpoint, and
  live-read via `resources/read` as `skill://pathforward/SKILL.md`. A live smoke on 2026-06-09 listed
  toolbox tools, listed/read the skill resource, injected the MCP-loaded skill into the Foundry
  Orchestrator, verified through the Evidence Gate, and minted through the code spine. Toolbox-level
  RAI policy `pathforward-rai` was rejected by the consume endpoint, so `build_toolbox.py` omits
  toolbox-level RAI by default; model/deployment RAI remains separate. `pathforward/tool_surface.py`
  records Generator/Search and Fabric as deliberate direct Foundry prompt-agent tool seams, not
  migration targets.
- **Specialist Skill files are implemented, live-registered, and MCP-readback-proven.**
  `skills/pathforward-curate`, `skills/pathforward-assess`, `skills/pathforward-plan`, and
  `skills/pathforward-insights` follow the same `agentskills.io` `SKILL.md` shape and are wired into
  their corresponding agents when loaded by `scripts/trace_full_flow.py` and
  `scripts/smoke_toolbox_skill_live.py`. On 2026-06-09, `scripts/build_toolbox.py --recreate`
  registered all five Skills in `pathforward-toolbox`, and `scripts/smoke_toolbox_skill_live.py`
  proved `resources/list` / `resources/read` for every Skill plus the skill-loaded Orchestrator route.
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
  (`source="fabric-live"`, OBO user identity, MicrosoftFabricPreviewTool). A local governed mint
  approval wrapper exists (`pathforward/credential/approval.py`): it emits a reviewable
  `require_approval="always"` request, fails closed on denial or replay/tamper, then delegates to
  `mint()` so readiness/spine checks still run. Voice Live and externally hosted MCP mint remain
  config-only.
- OpenTelemetry is a live-capable proof layer. `scripts/trace_demo.py` prints the focused
  assessment-loop trace; `scripts/trace_full_flow.py` prints the Orchestrator-driven proof trace
  including Skill load, Orchestrator routing, Curator, Generator, Critic, adaptive band, bounded
  reflection, Evidence Gate, Planner, Program Insights/Fabric, mint, and fail-closed ABSTAIN. When
  `AZURE_MONITOR_CONNECTION_STRING` is present, both export to Azure Monitor / Application Insights
  (`azure_export=on` verified 2026-06-09). Azure-side telemetry query was also verified on
  2026-06-09 when Azure CLI was logged in as the service principal from `.env`; a normal user login
  may return `InsufficientAccessError` even though the service principal can read the traces. Before
  scaffolding stream-output captures, local log mirrors, or other observability workarounds, use the
  existing telemetry path first: run `scripts/trace_full_flow.py` for the full proof artifact or
  `scripts/trace_demo.py` for the focused loop, then query Azure Monitor / Application Insights with
  the service-principal identity. It is evidence/demo telemetry, not part of the trust gate.
- The same chain is **also expressed as a Microsoft Agent Framework Workflow** (flag-gated
  `PF_WORKFLOW`; ADR 009). `agents/workflow.py` is a framework-agnostic graph spec whose **no-bypass
  trust property** (no path reaches the credential `mint` without the deterministic, Evidence-Gate-
  bearing `assess` loop) is a **graph-shape test**, proven offline (`tests/test_workflow_graph.py`).
  The live adapter `agents/workflow_foundry.py` projects that spec onto `agent_framework`
  (GA 1.0.0+, SDK `1.8.0` installed here as of 2026-06-09) and is **imported lazily** so the offline
  suite stays green with or without the optional SDK. `run_multiagent` remains the always-green
  in-process spine; the portal/YAML Workflows product is deliberately AVOIDED for the trust path
  (no first-class code node). `PF_WORKFLOW=1` was live-exercised on 2026-06-09 with Agent Framework
  HITL: the workflow emitted the approval request, resumed with approval, routed mint through
  `credential.approval.mint_with_approval(...)`, and issued a credential through the existing spine.
  This proves the Workflow projection path, not the mainline product path. Per user instruction on
  2026-06-09, do not spend further architecture effort on Workflow unless explicitly re-authorized;
  keep it as optional/reference infrastructure.

**Target (where changes should head):**
- A genuine **multi-agent reasoning loop** worthy of the "Reasoning Agents" track: keep
  Generator→Evidence Gate; add real reasoning agents (a **Critic** before the gate, a **Curator** for
  adjacency/gap reasoning, a **Planner** for capacity + accessibility, a read-only **Program Insights**
  agent for cohort/why-this-path), and continue toward the stricter architecture contract: a
  Foundry-centered Orchestrator Skill control surface where the agentic route is live-proven, not
  merely a fixed Python sequence. Plural agents that genuinely reason are implemented, but the full
  contract is not done until the missing Orchestrator Skill/tooling surfaces in
  `.agents/plans/000-non-negotiable-agentic-architecture-contract.md` are addressed or explicitly
  deferred by the user.
- **Program Insights live tier:** keep the live Fabric data-agent read path repeatable and documented
  (`FABRIC_CONNECTION_NAME` + OBO user identity); do not collapse it back into the derivation floor
  when making evidence claims.
- **Agentic control:** keep hardening the bounded Conductor/Orchestrator route as the mainline
  `/pathforward` Skill surface. The Orchestrator-specific safety re-measure is complete for the
  skill-loaded route; do not reuse those numbers for future approval/Voice surfaces without a fresh
  run.
- **Foundry tools and skills:** keep expanding the `/pathforward` Skill/Toolbox route. The
  Orchestrator now consumes the MCP-loaded Foundry Skill, and specialist Skill files are
  live-registered/read from Foundry and wired for runtime injection. The current tool-surface
  contract is tracked in `pathforward/tool_surface.py`: Generator/Search uses the documented direct
  Foundry prompt-agent Azure AI Search tool because the Evidence Gate needs the retrieval trace;
  Fabric Insights uses the documented direct Fabric prompt-agent tool because it is advisory and
  reconciled against code-owned aggregates. Do not re-open those as migration work without explicit
  user authorization. The real open tool surface is Orchestrator-route approval/mint.
- **Approval/mint:** preserve `pathforward/credential/approval.py` as the runtime approval gate for
  mint. Microsoft docs state MCP/Toolbox `require_approval` is runtime-enforced, not endpoint-
  enforced; any future Orchestrator-route MCP/Hosted approval surface must route through this wrapper
  and then through `credential.mint.mint()`.
- Keep the **live `FoundryLLMClient` / `ReasoningFoundryClient` / `FabricInsightsClient`** demo and
  web fixture export path working (`scripts/run_demo.py --live`, `scripts/export_web_fixture.py
  --live`), and keep provenance explicit (`live-foundry`, `fabric-live`, `offline-rehearsal`).
- Use Code Interpreter ONLY as a non-gating analyst (`CodeInterpreterAnalyst`) for second-opinion
  recompute + calibration explainability — never as the gate oracle (it is non-deterministic: the
  model writes the code). `LocalNumericChecker` stays the sole oracle. **(Seam landed 2026-06-08, ADR 008.)**
- Keep the deterministic **Evidence Gate** (`pathforward/agents/evidence_gate.py`) as the trust boundary — it must NOT become an LLM
  judging its own work.

## Stubs are temporary — preserve the seams

- The hard architecture contract is `.agents/plans/000-non-negotiable-agentic-architecture-contract.md`.
  If older plans, ADRs, or summaries imply the architecture is complete merely because five
  code-orchestrated agents exist, the contract wins.

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
  and the `mint` executor (must route through `credential.approval.mint_with_approval(...)`, which
  delegates to `credential.mint.mint`). **Never** let the Workflow track write `status="verified"`
  itself, call raw mint without approval, or become a second trust authority; it must stay a
  projection. It is optional/reference infrastructure only, not the path to keep investing in.

## Invariants you must not break

- The **`corpus ∩ retrieved`** grounding gate in `loop.py` — a citation counts only if it is both
  approved corpus AND actually returned by the retrieval tool trace. This is the anti-bluff core.
- **Fail-closed**: exhausting attempts (N=3) → **ABSTAIN**, never a silent pass.
- **Causal spine**: the minted credential cites the SAME driving CertGap edge.
- **Mint approval**: approval denial, missing approval, request replay, or request mismatch fails
  closed before `mint()`; approval never replaces `mint()`'s readiness/spine checks.
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
