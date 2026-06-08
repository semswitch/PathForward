"""Cold-start calibration (classical test theory).

HONEST LABELING (red-team correction): we do NOT claim population IRT on synthetic
data. We compute classical item statistics — difficulty (p-value) and discrimination
(point-biserial) — from the synthetic learner-response set, label every item
'estimated (cold-start)', and let the Evidence Gate's filtering be the real quality ratchet.

  difficulty      = proportion answering correctly (p-value)
  discrimination  = point-biserial correlation between item correctness and total score
"""
from __future__ import annotations

import statistics
from collections import defaultdict


def cold_start_calibrate(responses: list[dict]) -> dict[str, dict]:
    """responses: [{learner_id, item_id, correct: bool}, ...]"""
    # total score per learner
    totals: dict[str, int] = defaultdict(int)
    per_item: dict[str, list[tuple[str, int]]] = defaultdict(list)  # item -> [(learner, 0/1)]
    for r in responses:
        c = 1 if r.get("correct") else 0
        totals[r["learner_id"]] += c
        per_item[r["item_id"]].append((r["learner_id"], c))

    all_totals = list(totals.values())
    sd = statistics.pstdev(all_totals) if len(all_totals) > 1 else 0.0

    out: dict[str, dict] = {}
    for item_id, rows in per_item.items():
        n = len(rows)
        scores = [c for _, c in rows]
        p = sum(scores) / n if n else 0.0
        disc = _point_biserial(rows, totals, sd, p)
        out[item_id] = {
            "n": n,
            "difficulty": round(p, 4),
            "discrimination": round(disc, 4),
            "label": "estimated (cold-start)",
        }
    return out


def _point_biserial(rows: list[tuple[str, int]], totals: dict[str, int],
                    sd: float, p: float) -> float:
    if sd == 0 or p in (0.0, 1.0):
        return 0.0
    correct_totals = [totals[l] for l, c in rows if c == 1]
    wrong_totals = [totals[l] for l, c in rows if c == 0]
    if not correct_totals or not wrong_totals:
        return 0.0
    m1 = statistics.mean(correct_totals)
    m0 = statistics.mean(wrong_totals)
    return ((m1 - m0) / sd) * ((p * (1 - p)) ** 0.5)
