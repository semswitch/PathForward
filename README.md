# PathForward

**A multi-agent reskilling system for displaced / at-risk workers.**
Microsoft Agents League @ AISF 2026 · **Reasoning Agents** track (Microsoft Foundry).

PathForward reasons over a **Fabric IQ** skill-adjacency ontology and a **Foundry IQ**
grounded knowledge base to (1) map a worker's transferable skills to adjacent in-demand
certifications, (2) build capacity- and accessibility-aware study plans, and (3) run a
**grounded, cheat-resistant competency-verification loop** that mints a portable,
citation-backed credential — refusing to certify anything it cannot ground and verify.

> **Synthetic & for demonstration only.** All data is fabricated (e.g. `EMP-001`, `L-1001`,
> `S01`, `AZ-204`). No real people, employee records, or PII. See [RESPONSIBLE-AI.md](RESPONSIBLE-AI.md).

---

## The signature: a grounded Generator → Evidence Gate loop (agents reason, code notarizes)

```
CertGap edge (derived)  ──drives──▶  Generator proposes a grounded item
                                          │
                                          ▼
                                  Evidence Gate  (deterministic 5-criterion notary;
                                                every numeric claim independently checked)
                                          │
                          reject ◀────────┴────────▶ pass
                          (regenerate, capped N=3)        │
                                  │                        ▼
                          fail-closed ABSTAIN     citation-backed credential
                                                  (cites the SAME CertGap edge)
```

The loop is plain SDK-shaped code (a `respond()` call chained by `previous_response_id`),
so the orchestrator owns the payload and **citations propagate deterministically** —
not classic connected agents. See [ARCHITECTURE.md](ARCHITECTURE.md).

## Two load-bearing Microsoft IQ layers

- **Fabric IQ** — the ontology (`Worker / Skill / Role / Certification`) with **derived**
  edges the raw data doesn't contain: `CertGap = Role.requires.Skill \ Worker.has.Skill`
  and `Readiness`. These drive the assessment blueprint. The demo proves live inference by
  editing a skill on screen and watching `CertGap`/`Readiness` re-derive.
- **Foundry IQ** — GA agentic retrieval (extractive grounding + rerank + citations) over the
  synthetic corpus; grounds every adjacency hop and assessment item. At runtime the Generator
  queries a **pre-materialized Search mirror** of the ontology.
- **Fabric live read path** — a published Fabric data agent over OneLake powers the
  `ProgramInsightsAgent` live tier (`source="fabric-live"`). It is read-only and advisory, not on the
  credential mint path, but it is now a real live path rather than a placeholder.

---

## Run it

The deterministic rehearsal path requires no Azure and remains useful for fast local development.
The product-shaped path swaps in live Foundry/Fabric clients behind the same seams. From the repo
root:

```bash
python scripts/generate_data.py     # synthetic ontology + learner responses -> data/generated/
python scripts/build_mirror.py      # materialize the Search-mirror docs (+ build-time guard)
python scripts/run_demo.py          # full reasoning spine, end-to-end, for hero worker EMP-001
python -m unittest discover -s tests -t .   # offline suite (derivation, loop, gate, credential)
```

Or use the task runner: `./tasks.ps1 test` · `./tasks.ps1 demo` (Windows) / `make test` · `make demo`.

Live proof scripts run from the project virtualenv when Azure/Fabric are configured:

```powershell
.venv\Scripts\python.exe scripts\smoke_multiagent_live.py
.venv\Scripts\python.exe scripts\smoke_orchestrator_live.py
.venv\Scripts\python.exe scripts\build_toolbox.py --recreate
.venv\Scripts\python.exe scripts\smoke_toolbox_skill_live.py
.venv\Scripts\python.exe scripts\smoke_mint_approval.py
.venv\Scripts\python.exe scripts\eval_orchestrator_live.py --no-judge
$env:FABRIC_CONNECTION_NAME="<your-foundry-fabric-connection-name>"
.venv\Scripts\python.exe scripts\smoke_fabric_live.py
.venv\Scripts\python.exe scripts\run_demo.py --live
.venv\Scripts\python.exe scripts\export_web_fixture.py --live
.venv\Scripts\python.exe scripts\trace_demo.py       # focused assessment-loop trace
.venv\Scripts\python.exe scripts\trace_full_flow.py  # Orchestrator + full reasoning trace
```

Hosted Agent surface:

```powershell
python -m unittest tests.test_hosted_orchestrator -v
python -m py_compile pathforward\hosted_orchestrator.py hosted\pathforward_orchestrator\main.py
.venv\Scripts\python.exe scripts\smoke_hosted_agent_live.py
.venv\Scripts\python.exe scripts\eval_hosted_agent_live.py --limit 3 --attack-limit 3
```

## Layout

| Path | What |
|---|---|
| `pathforward/iq/` | ontology models, the version-pinned **derivation** module, seed, traversal (Glass-Box), Search mirror |
| `pathforward/agents/` | LLM client (fake + Foundry), Orchestrator/Conductor contract, Curator/Generator/Critic/Planner/Insights, the **Evidence Gate** (deterministic notary), the **loop**, numeric checker, and calibration |
| `pathforward/credential/` | the W3C VC 2.0-aligned proof, governed approval wrapper, and causal-spine mint |
| `pathforward/hosted_orchestrator.py` | the testable core for the Foundry Hosted Agent top-level Orchestrator route |
| `hosted/pathforward_orchestrator/` | the `responses` protocol adapter and hosted-agent runtime requirements |
| `agent.yaml` / `Dockerfile` | Foundry Hosted Agent manifest and container packaging for `pathforward-orchestrator` |
| `pathforward/scorer.py` | the shared scorer (voice/text parity) |
| `pathforward/tool_surface.py` | the checked mainline tool-surface contract for the Hosted `/pathforward` Orchestrator route, Toolbox-loaded Skills, direct Foundry Search/Fabric specialist seams, and Workflow lockout |
| `scripts/` | data generation, mirror build, the offline demo |
| `skills/pathforward*/SKILL.md` | the `agentskills.io` sources for the Foundry `/pathforward` Orchestrator skill and specialist Curator/Assessment/Planner/Insights skills |
| `tests/` | the guarantees (derived-edge correctness, loop termination, citations-survive, parity, credential integrity) |
| `web/` | Carbon UI skeleton (Glass-Box graph · Assessment Arena · Trust Console) |
| `data/corpus/` | synthetic grounding documents |

## Status

✅ Hosted Agent top-level Orchestrator is deployed and live-proven on Foundry Hosted Agent version 11:
`agent.yaml`, `Dockerfile`, `hosted/pathforward_orchestrator/main.py`, and
`pathforward/hosted_orchestrator.py` package the existing `/pathforward` route as a Foundry
`responses`-protocol Hosted Agent. Local proof (`tests/test_hosted_orchestrator.py`) verifies the
route requests mint approval and only mints with explicit runtime approval. Live hosted proof
(`scripts/smoke_hosted_agent_live.py`) verifies Toolbox MCP Skill loading, Azure AI Search retrieval,
Fabric-live Program Insights, default no-approval/no-mint, and explicit approval mint. ✅ Multi-agent Foundry path live-proven: Curator, Generator, Critic, Planner, and Program Insights
run through `scripts/smoke_multiagent_live.py`; the deterministic Evidence Gate and mint remain the
trust boundary. ✅ Fabric live read path proven through `scripts/smoke_fabric_live.py` using the
Microsoft Fabric data-agent tool. ✅ Demo and web fixture export now support a live mode
(`scripts/run_demo.py --live`, `scripts/export_web_fixture.py --live`) with explicit provenance.
✅ A bounded Orchestrator/Conductor contract is implemented, offline-proven (`tests/test_conductor.py`),
and live-smoke-proven through `scripts/smoke_orchestrator_live.py`. ✅ The `/pathforward` Foundry
Skill is sourced from `skills/pathforward/SKILL.md`, registered into `pathforward-toolbox`, read back
through toolbox MCP resources, and consumed by the live Orchestrator path through
`scripts/smoke_toolbox_skill_live.py`. ✅ Skill-loaded Orchestrator safety has its own live scorecards:
`scripts/eval_orchestrator_live.py --no-judge` produced 16/16 grounded + spine-intact and 0.0% ASR
(16/16 defenses held, including Orchestrator route attacks). ✅ Specialist Skill files for Curator,
Assessment, Planner, and Insights are registered in the Foundry toolbox and read through MCP by
`scripts/smoke_toolbox_skill_live.py`. ✅ The local governed mint approval wrapper is implemented:
`scripts/smoke_mint_approval.py` proves review request, denied fail-closed path, approved mint, and
spine preservation. ✅ `scripts/trace_full_flow.py` now
shows the proof trace for Skill load, Orchestrator routing, Curator, Generator, Critic,
adaptive/reflection, Evidence Gate, Planner, Program Insights/Fabric, mint, and fail-closed ABSTAIN;
it exports to Azure Monitor when `AZURE_MONITOR_CONNECTION_STRING` is set. ✅ Offline suite is green
(`python -m unittest discover -s tests -t .`).
The non-gating `CodeInterpreterAnalyst` (Code Interpreter — advisory, never the numeric oracle; see
ADR 008) is wired but still needs its live smoke before it should be called live-proven. The Workflow
decision is locked: PathForward is not using Agent Framework Workflow as an architecture surface.
Hosted-target scorecards are now started (`scripts/eval_hosted_agent_live.py --limit 3 --attack-limit
3`): 2/3 hosted groundedness cases passed, 3/3 hosted prompt-surface attacks held. Remaining hosted
hardening is broader eval coverage, semantic ABSTAIN proof, and Fabric data-agent reliability after
one hosted EMP-004 run failed inside Fabric before returning proof JSON.

## Microsoft IQ integration (submission requirement: ≥1; we use 2)

Foundry IQ (grounded retrieval) **and** Fabric IQ (semantic ontology), both visibly load-bearing.

## Responsible AI

Grounded refusal, fail-closed credential gate, synthetic-only data, human-in-the-loop mint.
See [RESPONSIBLE-AI.md](RESPONSIBLE-AI.md).
