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

## The signature: a code-driven Generator → Verifier loop

```
CertGap edge (derived)  ──drives──▶  Generator proposes a grounded item
                                          │
                                          ▼
                                     Verifier  (5-criterion + evidence-answerability gate;
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
  synthetic corpus; grounds every adjacency hop and assessment item. At runtime the system
  queries a **pre-materialized Search mirror** of the ontology (the live Fabric data agent is
  never on the critical path).

---

## Run it (no Azure required)

The offline core is **standard-library only**. From the repo root:

```bash
python scripts/generate_data.py     # synthetic ontology + learner responses -> data/generated/
python scripts/build_mirror.py      # materialize the Search-mirror docs (+ build-time guard)
python scripts/run_demo.py          # full reasoning spine, end-to-end, for hero worker EMP-001
python -m unittest discover -s tests -t .   # 21 tests (derivation, loop, mirror, scorer, credential)
```

Or use the task runner: `./tasks.ps1 test` · `./tasks.ps1 demo` (Windows) / `make test` · `make demo`.

## Layout

| Path | What |
|---|---|
| `pathforward/iq/` | ontology models, the version-pinned **derivation** module, seed, traversal (Glass-Box), Search mirror |
| `pathforward/agents/` | LLM client (fake + Foundry stub), Generator, Verifier, the **loop**, numeric checker, calibration |
| `pathforward/credential/` | the W3C VC 2.0-aligned proof + the causal-spine mint |
| `pathforward/scorer.py` | the shared scorer (voice/text parity) |
| `scripts/` | data generation, mirror build, the offline demo |
| `tests/` | the guarantees (derived-edge correctness, loop termination, citations-survive, parity, credential integrity) |
| `web/` | Carbon UI skeleton (Glass-Box graph · Assessment Arena · Trust Console) |
| `data/corpus/` | synthetic grounding documents |

## Status (Day 0)

✅ Offline reasoning core complete and tested (21/21).  ⏳ Azure layer (Foundry agents, agentic
retrieval, Fabric ontology, Voice Live, MCP mint, evals) wires in per the
[planning package](../Microsoft-Agents-League/03-Build-Plan.md). The `FoundryLLMClient`,
`CodeInterpreterChecker`, and config endpoints are stubs marked with their wire-in day.

## Microsoft IQ integration (submission requirement: ≥1; we use 2)

Foundry IQ (grounded retrieval) **and** Fabric IQ (semantic ontology), both visibly load-bearing.

## Responsible AI

Grounded refusal, fail-closed credential gate, synthetic-only data, human-in-the-loop mint.
See [RESPONSIBLE-AI.md](RESPONSIBLE-AI.md).
