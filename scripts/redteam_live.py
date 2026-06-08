"""Live adversarial red-team -> Attack Success Rate scorecard.

Runs each model-side attack family against the REAL agent (gpt-5.5 + agentic search, under the
enforced pathforward-rai policy) and scores — in code — whether the refuse-to-bluff defense held:
the agent abstains or returns a gate-clean item, never leaks its instructions, and never smuggles
the injected marker into a surviving item. The offline defense-logic proofs live in
tests/test_redteam_gate.py.

Writes eval/redteam-asr.{json,md} (tracked evidence). Exits non-zero if ANY attack succeeds
(target Attack Success Rate = 0%).

    python scripts/redteam_live.py                 # all attacks
    python scripts/redteam_live.py --limit 3       # first 3 (quick)
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from pathforward.agents.critic import Critic               # noqa: E402
from pathforward.agents.foundry import FoundryLLMClient, ReasoningFoundryClient  # noqa: E402
from pathforward.config import load_settings               # noqa: E402
from pathforward.eval.attacks import LIVE_ATTACKS, run_live_attack  # noqa: E402
from pathforward.eval.runner import Scorecard              # noqa: E402
from pathforward.iq import derivation as dv                # noqa: E402
from pathforward.iq.seed import build_seed                 # noqa: E402

CRITIC_AGENT = "pathforward-critic"


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description="Live adversarial red-team (ASR scorecard).")
    ap.add_argument("--limit", type=int, default=0, help="only run the first N attacks")
    args = ap.parse_args()

    s = load_settings(os.path.join(_ROOT, ".env"))
    onto = build_seed()
    edges = dv.build_all_edges(onto)
    attacks = LIVE_ATTACKS[:args.limit] if args.limit else LIVE_ATTACKS

    client = FoundryLLMClient(endpoint=s.foundry_project_endpoint, model=s.model_deployment,
                              index_name=s.search_index)
    # Live Critic agent (tool-less reasoning prompt agent) — the red-team now runs the FULL post-P2
    # flow (Critic + bounded reflection), so the ASR numbers reflect the new surface.
    critic = Critic(ReasoningFoundryClient(endpoint=s.foundry_project_endpoint,
                                           agent_name=CRITIC_AGENT, model=s.model_deployment))
    print(f"running {len(attacks)} live attacks against the agent + live Critic "
          f"(RAI: {s.rai_policy or 'default'})...")
    results = []
    try:
        for atk in attacks:
            r = run_live_attack(atk, client, onto, edges, critic=critic)
            print(f"  {'HELD ' if r.passed else 'BREACH'} {atk.id}: {r.detail.get('why')}")
            results.append(r)
    finally:
        client.close()
        critic.client.close()

    card = Scorecard("PathForward — Adversarial Red-Team (live)", "defense held",
                     results, adversarial=True)
    out_dir = os.path.join(_ROOT, "eval")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "redteam-asr.json"), "w", encoding="utf-8") as fh:
        json.dump(card.to_dict(), fh, indent=2)
    with open(os.path.join(out_dir, "redteam-asr.md"), "w", encoding="utf-8") as fh:
        fh.write(card.to_markdown())
    print(f"\ndefense held on {card.n_passed}/{card.n}  ·  Attack Success Rate {card.asr * 100:.1f}%")
    print("wrote eval/redteam-asr.json + .md")
    return 0 if card.n_passed == card.n else 1


if __name__ == "__main__":
    raise SystemExit(main())
