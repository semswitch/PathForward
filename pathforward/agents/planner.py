"""Planner agent — reasons a capacity- and accessibility-aware learning plan around the gap.

The LLM proposes a study pace, a skill sequence, and accessibility phrasing. Deterministic code
OWNS every trust-bearing fact:
  - per-skill HOURS are taken from the certification blueprint (`canonical_hours`), never the model;
  - the weekly LOAD is phased in code to respect `worker.weekly_capacity_hours` (an over-ambitious
    model pace is clamped and flagged `corrected`);
  - the arithmetic is proven by the same `NumericChecker` the Evidence Gate trusts;
  - accessibility ADAPTATIONS are derived from a fixed vocabulary keyed to the worker's declared
    needs (a model suggestion outside that vocabulary never enters the plan).

The plan is ADVISORY — it is not part of the credential trust chain (the mint does not consume it).
"""
from __future__ import annotations

import json
import math

from ..iq.models import Ontology, Worker
from .client import PLANNER_TAG, LLMClient
from .numeric import NumericChecker
from .types import LearningPlan, PlannedPhase

# Fixed accessibility vocabulary, keyed by the exact need strings used in iq/seed.py. The model
# may phrase accommodations, but only entries mapped from the worker's REAL needs enter the plan.
A11Y_ADAPTATIONS: dict[str, tuple[str, ...]] = {
    "low-vision": ("high-contrast materials", "screen-magnifier-friendly labs"),
    "prefers-audio": ("audio-narrated modules",),
    "screen-reader": ("screen-reader-tested content", "alt-text on diagrams"),
    "dyslexia": ("dyslexia-friendly typography", "extended reading time"),
    "ADHD-focus-windows": ("short 25-minute focus blocks", "spaced repetition"),
    "hard-of-hearing": ("captioned video",),
    "captions-required": ("captioned video", "transcripts"),
    "color-blind": ("color-blind-safe palettes",),
}

PLAN_INSTRUCTIONS = (
    f"{PLANNER_TAG} You are the Planner. Given the worker's gap skills, weekly capacity, and "
    "accessibility needs, propose a study `sequence` (skill_ids), a realistic `weekly_hours` pace, "
    "`accessibility_adaptations`, and a short `rationale`. Respect the worker's weekly capacity."
)

PLANNER_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "sequence": {"type": "array", "items": {"type": "string"}},
        "weekly_hours": {"type": "number"},
        "accessibility_adaptations": {"type": "array", "items": {"type": "string"}},
        "rationale": {"type": "string"},
    },
    "required": ["sequence", "weekly_hours", "accessibility_adaptations", "rationale"],
}


def canonical_hours(skill_id: str, onto: Ontology) -> tuple[int, str]:
    """The deterministic study-hours figure for a skill: the MINIMUM `recommended_hours` over the
    certifications that certify it (the cheapest credentialed path), tie-broken by cert id sort.
    Returns (hours, cert_id); (0, "") if no certification covers the skill."""
    certs = onto.certs_for_skill(skill_id)
    if not certs:
        return (0, "")
    best = min(certs, key=lambda c: (c.recommended_hours, c.id))
    return (best.recommended_hours, best.id)


class Planner:
    def __init__(self, client: LLMClient, numeric_checker: NumericChecker,
                 skill_instructions: str = ""):
        self.client = client
        self.numeric_checker = numeric_checker
        self.skill_instructions = skill_instructions.strip()

    def _instructions(self) -> str:
        if not self.skill_instructions:
            return PLAN_INSTRUCTIONS
        return (
            f"{PLAN_INSTRUCTIONS}\n\n"
            "Loaded Foundry Skill `/pathforward-plan`:\n"
            f"{self.skill_instructions}\n\n"
            "Follow the loaded skill, but code-owned hours, capacity phasing, arithmetic, and "
            "accessibility vocabulary remain authoritative."
        )

    def plan(self, worker: Worker, ranked_skill_ids: tuple[str, ...],
             onto: Ontology) -> LearningPlan:
        capacity = float(worker.weekly_capacity_hours)

        # Derive per-skill hours from the certification blueprint (code-owned, not model-supplied).
        derived = [(s, *canonical_hours(s, onto)) for s in ranked_skill_ids]
        derived = [(s, h, c) for (s, h, c) in derived if h > 0]   # drop uncorpused defensively
        total = float(sum(h for _, h, _ in derived))

        # Prove the sum with the NumericChecker (same trust as the Evidence Gate's numeric gate).
        if derived:
            claim = f"{' + '.join(str(h) for _, h, _ in derived)} == {int(total)}"
            res = self.numeric_checker.check(claim)
            numeric_check = {"claim": claim, "ok": res.ok, "detail": res.detail}
        else:
            numeric_check = {"claim": "", "ok": True, "detail": "no skills to plan"}

        # The model PROPOSES a pace + adaptations; nothing it returns is trusted for the facts.
        payload = {
            "worker_id": worker.id,
            "weekly_capacity_hours": capacity,
            "accessibility_needs": list(worker.accessibility_needs),
            "gap_skills": [{"id": s, "hours": h, "cert_id": c} for s, h, c in derived],
        }
        resp = self.client.respond(self._instructions(), json.dumps(payload), schema=PLANNER_SCHEMA)
        parsed = resp.parsed or {}
        proposed_weekly = float(parsed.get("weekly_hours", capacity) or 0.0)
        rationale = str(parsed.get("rationale", ""))

        # GATE 1 — capacity: phase the derived hours in CODE at <= capacity/week. A model pace that
        # exceeds the worker's real capacity is clamped (we always use `capacity`) and flagged.
        corrected = proposed_weekly > capacity + 1e-9
        phases, weeks, capacity_respected = self._phase(derived, capacity, total)

        # GATE 2 — accessibility: derive adaptations from the fixed vocabulary keyed to the worker's
        # DECLARED needs. A model suggestion outside this set never enters the plan; no needs -> none.
        adaptations = tuple(sorted({a for need in worker.accessibility_needs
                                    for a in A11Y_ADAPTATIONS.get(need, ())}))

        return LearningPlan(
            worker_id=worker.id, phases=tuple(phases), total_hours=total,
            weekly_capacity_hours=capacity, weeks=weeks,
            capacity_respected=capacity_respected, corrected=corrected,
            accessibility_adaptations=adaptations, numeric_check=numeric_check, rationale=rationale,
        )

    @staticmethod
    def _phase(derived: list[tuple[str, int, str]], capacity: float,
               total: float) -> tuple[list[PlannedPhase], int, bool]:
        """Greedily pack derived hours into weeks at <= capacity/week, in ranked order. A skill may
        span weeks; a partial week may carry the tail of one skill and the head of the next. Each
        emitted phase is one (skill, week) chunk of <= capacity hours."""
        if not derived:
            return ([], 0, True)
        if capacity <= 0:
            # Cannot schedule any positive load within a non-positive weekly capacity.
            return ([], 0, total <= 0)
        phases: list[PlannedPhase] = []
        week = 1
        remaining_in_week = capacity
        for skill, hours, cert in derived:
            h_rem = float(hours)
            while h_rem > 1e-9:
                if remaining_in_week <= 1e-9:
                    week += 1
                    remaining_in_week = capacity
                chunk = min(h_rem, remaining_in_week)
                phases.append(PlannedPhase(week=week, skill_id=skill,
                                           hours=round(chunk, 2), cert_id=cert))
                h_rem -= chunk
                remaining_in_week -= chunk
        return (phases, week, True)
