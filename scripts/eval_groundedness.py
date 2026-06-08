"""Live groundedness + spine-integrity eval over legit CertGap cases.

Runs the REAL assessment loop (gpt-5.5 + agentic search) on each hero worker's CertGap edges and
scores, deterministically in code: produced a grounded item (cited ⊆ corpus∩retrieved), retrieval
actually happened, and the credential's cited_edge_id == the driving CertGap edge (spine intact).
Optionally adds the Microsoft Foundry GroundednessEvaluator as a corroborating second opinion.

Writes eval/eval-groundedness.{json,md} (tracked evidence). Exits non-zero if any legit case fails
(fail-loud: a grounded assessor must ground every legit case).

    python scripts/eval_groundedness.py                 # all hero cases
    python scripts/eval_groundedness.py --limit 3       # first 3 (quick)
    python scripts/eval_groundedness.py --no-judge      # skip the Foundry second opinion
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from pathforward.agents.foundry import FoundryLLMClient        # noqa: E402
from pathforward.agents.generator import Generator             # noqa: E402
from pathforward.agents.numeric import LocalNumericChecker     # noqa: E402
from pathforward.agents.evidence_gate import EvidenceGate               # noqa: E402
from pathforward.config import load_settings                   # noqa: E402
from pathforward.eval.cases import build_eval_cases            # noqa: E402
from pathforward.eval.foundry_eval import FoundryGroundedness  # noqa: E402
from pathforward.eval.runner import Scorecard, run_eval_case   # noqa: E402
from pathforward.iq import derivation as dv                    # noqa: E402
from pathforward.iq import mirror                              # noqa: E402
from pathforward.iq.seed import build_seed                     # noqa: E402


def _content_by_ref(onto, edges) -> dict[str, str]:
    """ref_id -> doc content, for the Foundry groundedness context."""
    return {d["ref_id"]: d["content"] for d in mirror.build_search_docs(onto, edges)}


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description="Live groundedness + spine eval.")
    ap.add_argument("--limit", type=int, default=0, help="only run the first N cases")
    ap.add_argument("--no-judge", action="store_true", help="skip the Foundry GroundednessEvaluator")
    args = ap.parse_args()

    s = load_settings(os.path.join(_ROOT, ".env"))
    onto = build_seed()
    edges = dv.build_all_edges(onto)
    cases = build_eval_cases(onto, edges)
    if args.limit:
        cases = cases[:args.limit]
    content = _content_by_ref(onto, edges)

    judge = None if args.no_judge else FoundryGroundedness(
        s.foundry_project_endpoint, s.model_deployment, s.eval_judge_api_version)
    if judge and not judge.available:
        print(f"(Foundry groundedness judge unavailable: {judge.reason})")

    client = FoundryLLMClient(endpoint=s.foundry_project_endpoint, model=s.model_deployment,
                              index_name=s.search_index)
    gen, ver = Generator(client), EvidenceGate(LocalNumericChecker())
    print(f"running {len(cases)} groundedness cases...")
    results = []
    try:
        for c in cases:
            r = run_eval_case(c, gen, ver, onto)
            # corroborating second opinion on verified items
            if judge and judge.available and r.detail.get("status") == "verified":
                ctx = "\n\n".join(content.get(ref, "") for ref in r.detail.get("cited", []))
                resp = f"{r.detail.get('item_stem','')}\nCorrect: {r.detail.get('item_answer','')}"
                score = judge.score(ctx, resp, query=f"Competency item for skill {c.skill.name}.")
                r.detail["foundry_groundedness"] = score
                if score is not None:
                    r.headline += f" | foundry={score}/5"
            mark = "PASS" if r.passed else "FAIL"
            fg = r.detail.get("foundry_groundedness")
            print(f"  [{mark}] {c.id}: {r.headline}" + (f" | foundry={fg}/5" if fg else ""))
            results.append(r)
    finally:
        client.close()

    card = Scorecard("PathForward — Groundedness & Spine Integrity (live)",
                     "grounded + spine-intact", results)
    out_dir = os.path.join(_ROOT, "eval")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "eval-groundedness.json"), "w", encoding="utf-8") as fh:
        json.dump(card.to_dict(), fh, indent=2)
    with open(os.path.join(out_dir, "eval-groundedness.md"), "w", encoding="utf-8") as fh:
        fh.write(card.to_markdown())
    print(f"\n{card.n_passed}/{card.n} grounded + spine-intact ({card.rate * 100:.0f}%)")
    print(f"wrote eval/eval-groundedness.json + .md")
    return 0 if card.n_passed == card.n else 1


if __name__ == "__main__":
    raise SystemExit(main())
