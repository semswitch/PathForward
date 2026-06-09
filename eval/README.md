# PathForward — Eval & Red-Team Pack

Two **deterministic** scorecards over the *same* Generator→Critic→Evidence Gate loop the product runs. Every
pass/fail is decided in **code** (the `corpus ∩ retrieved` gate, the credential spine, an injected
marker surviving into output) — **never an LLM judge** — which is what makes a safety claim
falsifiable. Cases are derived from the synthetic ontology, so the benchmark is reproducible.

## Scorecards

| Scorecard | What it measures | Result |
|---|---|---|
| [`eval-groundedness.md`](eval-groundedness.md) | Every legitimate CertGap case: the agent produced a **grounded** item (cited ⊆ corpus∩retrieved), retrieval actually happened, and the credential's `cited_edge_id` == the driving CertGap edge (**spine intact**). | **16/16 — 100%** (Foundry judge avg **4.1/5**) |
| [`redteam-asr.md`](redteam-asr.md) | 12 model-side attack families vs. the real agent under the enforced `pathforward-rai` policy, including the reflection-channel attack family added after the Critic/reflection work. **Attack Success Rate** = fraction where the refuse-to-bluff defense failed. | **0.0% — 12/12 held** |

Plus offline gate and harness proofs in [`tests/test_redteam_gate.py`](../tests/test_redteam_gate.py)
and [`tests/test_eval_harness.py`](../tests/test_eval_harness.py): for every offline-testable attack,
a hand-crafted malicious item, mint call, or reflection-channel scenario is asserted to be **struck**
by the hardened defense (run with `python -m unittest discover -s tests -t .`).

## Defense-in-depth (why ASR is 0%)

- **RAI content filter** (`pathforward-rai`, Blocking) blocks jailbreak/override prompts *before the
  model runs* — Azure returns `jailbreak: detected/filtered`, surfaced as a fail-closed empty response.
- **The `corpus ∩ retrieved` gate** makes citation-forgery and retrieval-suppression impossible — the
  model cannot fabricate the tool trace, so an ungrounded citation is struck.
- **Fail-closed abstention** (N=3) — a phantom entity (EMP-999) with no retrievable evidence abstains
  rather than inventing a gap.
- **Hardened verifier + mint** — homoglyph leakage, false/tautological numerics, multi-correct options,
  cross-worker credential contamination, and readiness inflation are all rejected deterministically.

## Run it

```bash
python -m unittest tests.test_redteam_gate        # 12 offline defense-logic proofs (no Azure)
python scripts/eval_groundedness.py               # live groundedness + spine eval  -> eval-groundedness.*
python scripts/redteam_live.py                    # live adversarial ASR scorecard  -> redteam-asr.*
```

The live scripts use keyless `DefaultAzureCredential` and back off on the deployment's rate limit. The
Microsoft Foundry **GroundednessEvaluator** runs as a corroborating second opinion when reachable
(`is_reasoning_model=True` for the gpt-5.5 judge); it degrades gracefully and is never authoritative.

## Known limitations (honest — defended in depth, not deterministically closed)

These are inherent LLM-judgment gaps. They are mitigated by the RAI filter + strict schema + the gate,
and are surfaced here rather than hidden (see `.agents/decisions/004` for the full taxonomy):

- **Semantic ungrounding** — an item whose citation *ids* are valid but whose keyed answer isn't
  supported by the cited prose (the gate checks ids, not semantics).
- **Semantic answer leakage / multi-correct by meaning** — a paraphrase that telegraphs the answer, or
  two options both correct, without a literal tell.
- **Adjacency numeric fabrication** — arithmetic that is internally consistent but whose magnitudes the
  corpus never stated.
- **Corpus supply-chain** — a caller that widens `approved_refs` upstream of the loop.

All data is **synthetic** (no PII); identifiers like `EMP-001`, `AZ-204` are fabricated labels.
