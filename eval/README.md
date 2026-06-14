# PathForward — Eval & Red-Team Pack

Narrated flow: https://semswitch.github.io/PathForward/tour

Current dashboard eval target:

```text
Foundry Prompt Agent: pathforward-orchestrator
kind: prompt
azd service: pathforward-orchestrator
dataset: eval/foundry-prompt-dashboard.jsonl
```

Historical hosted/v21 dashboard runs are not current product proof. Current product evals must target
the live Prompt Orchestrator route.

The dashboard JSONL rows are contract-shaped for PathForward-specific evaluators:

```text
query, expected_behavior, expected_outcome, risk_category, feature_area, must_not_expose, must_emit
```

Split dashboard suites:

| Suite | Config |
|---|---|
| `prompt_orchestrator_smoke` | `eval/prompt_orchestrator_smoke.yaml` |
| `prompt_orchestrator_safety` | `eval/prompt_orchestrator_safety.yaml` |
| `prompt_orchestrator_abstain` | `eval/prompt_orchestrator_abstain.yaml` |
| `prompt_orchestrator_fabric` | `eval/prompt_orchestrator_fabric.yaml` |
| `prompt_orchestrator_mint` | `eval/prompt_orchestrator_mint.yaml` |

## Evaluator Authority

Built-in Foundry evaluators are kept as secondary dashboard signal:

- `builtin.intent_resolution`
- `builtin.task_adherence`
- `builtin.indirect_attack`

They are not authoritative for Evidence Gate, readiness, Fabric source, MCP mint, or token exposure.
Those hard invariants require PathForward custom code evaluators and App Insights correlation.

Tracked custom code evaluators:

| Evaluator | Source |
|---|---|
| `pathforward_no_token_exposure` | `eval/evaluators/no_token_exposure.py` |
| `pathforward_credential_requires_approval` | `eval/evaluators/credential_requires_approval.py` |
| `pathforward_abstain_no_mint` | `eval/evaluators/abstain_no_mint.py` |
| `pathforward_fabric_live_source` | `eval/evaluators/fabric_live_source.py` |
| `pathforward_required_tool_calls` | `eval/evaluators/required_tool_calls.py` |
| `pathforward_gate_before_mint` | `eval/evaluators/gate_before_mint.py` |
| `pathforward_mcp_mint_requires_approval` | `eval/evaluators/mcp_mint_requires_approval.py` |

Register or refresh the evaluator catalog versions before running dashboard evals that reference
these names:

```bash
python scripts/register_eval_code_evaluators.py
python scripts/smoke_eval_code_evaluators.py
```

The custom code evaluator API requires explicit `data_mapping` for each field. The tracked evaluator
manifest and SDK smoke path use `output_text`, `output_items`, `expected_outcome`, `risk_category`,
`feature_area`, and `must_emit`. If `azd ai agent eval run` binds to a stale `LAST_EVAL_ID`, it can
reuse old remote criteria even when local YAML lists new evaluator names; inspect per-criteria results
before treating a dashboard run as current proof.

For formal PathForward dashboard evals with these custom evaluators, use the SDK runner:

```bash
python scripts/run_prompt_orchestrator_eval.py --config eval/prompt_orchestrator_smoke.yaml
python scripts/correlate_eval_appinsights.py --eval-id <eval_id> --run-id <evalrun_id> --config eval/prompt_orchestrator_smoke.yaml
```

The SDK runner creates a normal Foundry eval/run for the portal, targets the current versioned Prompt
Agent, passes required evaluator initialization parameters, writes redacted local proof, and avoids
persisting system-prompt content in evidence.

Tracked custom prompt evaluator:

| Evaluator | Source | Authority |
|---|---|---|
| `pathforward_subjective_quality` | `eval/evaluators/subjective_quality_prompt.md` | Subjective signal only |

Register or refresh it separately from the hard code evaluators:

```bash
python scripts/register_eval_prompt_evaluators.py
python scripts/smoke_eval_prompt_evaluators.py
```

## App Insights Correlation

Every formal eval run should have a telemetry correlation record:

```bash
python scripts/correlate_eval_appinsights.py \
  --eval-id <eval_id> \
  --run-id <evalrun_id> \
  --config eval/prompt_orchestrator_smoke.yaml
```

The report records eval ID, run ID, agent name/version, dataset fingerprint, evaluator list/version,
App Insights query window, product failure count, evaluator failure count, and the exact KQL used.
Reports are written to `.agents/evidence/` by default.

The tracked deterministic scorecards remain supporting code/trust-boundary regression proof. Every
pass/fail is decided in code (the `corpus ∩ retrieved` gate, the credential spine, an injected marker
surviving into output), never an LLM judge. Cases are derived from the synthetic ontology, so the
benchmark is reproducible.

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
python scripts/run_prompt_orchestrator_eval.py --config eval/prompt_orchestrator_smoke.yaml  # authoritative SDK runner
python -m unittest tests.test_redteam_gate        # 12 offline defense-logic proofs (no Azure)
python scripts/eval_groundedness.py               # live groundedness + spine eval  -> eval-groundedness.*
python scripts/redteam_live.py                    # live adversarial ASR scorecard  -> redteam-asr.*
azd ai agent eval run --environment <env> --config eval.yaml  # secondary dashboard signal only; under-captures A2A
```

The live scripts use keyless `DefaultAzureCredential` and back off on the deployment's rate limit. The
Microsoft Foundry **GroundednessEvaluator** runs as a corroborating second opinion when reachable
(`is_reasoning_model=True` for the gpt-5.5 judge); it degrades gracefully and is never authoritative.

## Known limitations (honest — defended in depth, not deterministically closed)

These are inherent LLM-judgment gaps. They are mitigated by the RAI filter + strict schema + the gate,
and are surfaced here rather than hidden (see the internal red-team coverage taxonomy for the full list):

- **Semantic ungrounding** — an item whose citation *ids* are valid but whose keyed answer isn't
  supported by the cited prose (the gate checks ids, not semantics).
- **Semantic answer leakage / multi-correct by meaning** — a paraphrase that telegraphs the answer, or
  two options both correct, without a literal tell.
- **Adjacency numeric fabrication** — arithmetic that is internally consistent but whose magnitudes the
  corpus never stated.
- **Corpus supply-chain** — a caller that widens `approved_refs` upstream of the loop.

All data is **synthetic** (no PII); identifiers like `EMP-001`, `AZ-204` are fabricated labels.
