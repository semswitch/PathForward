"""Generate the synthetic dataset: ontology + learner-response set.

Writes:
  data/generated/ontology.json      — the seeded ontology (entities only)
  data/generated/learners.jsonl     — synthetic learner responses for cold-start calibration

All synthetic. No PII. Run:  python scripts/generate_data.py
"""
from __future__ import annotations

import json
import os
import random
import sys
from dataclasses import asdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathforward.iq.seed import build_seed  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "generated")


def _ontology_doc(onto) -> dict:
    return {
        "skills": [asdict(s) for s in onto.skills.values()],
        "roles": [asdict(r) for r in onto.roles.values()],
        "certifications": [asdict(c) for c in onto.certifications.values()],
        "workers": [asdict(w) for w in onto.workers.values()],
        "summary": onto.summary(),
    }


def _learner_responses(onto, n_learners: int = 30) -> list[dict]:
    """Synthetic responses with a latent ability so calibration is meaningful."""
    rng = random.Random(7)
    # 12 demo items, one per skill drawn from the first certs
    item_skills = ["S01", "S02", "S08", "S06", "S07", "S15",
                   "S16", "S21", "S22", "S23", "S13", "S26"]
    difficulty = {sid: rng.uniform(-1.0, 1.0) for sid in item_skills}
    rows: list[dict] = []
    for i in range(1, n_learners + 1):
        learner = f"L-{1000 + i}"
        ability = rng.gauss(0.0, 1.0)
        for sid in item_skills:
            logit = ability - difficulty[sid] + rng.gauss(0.0, 0.4)
            correct = logit > 0
            rows.append({"learner_id": learner, "item_id": f"item-{sid}",
                         "skill_id": sid, "correct": bool(correct)})
    return rows


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    onto = build_seed()

    with open(os.path.join(OUT, "ontology.json"), "w", encoding="utf-8") as f:
        json.dump(_ontology_doc(onto), f, indent=2)

    rows = _learner_responses(onto)
    with open(os.path.join(OUT, "learners.jsonl"), "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    print(f"ontology: {onto.summary()}")
    print(f"learner responses: {len(rows)} rows -> {OUT}\\learners.jsonl")


if __name__ == "__main__":
    main()
