"""Adaptive difficulty — a PURE-CODE controller (no LLM in the decision).

It turns the (otherwise display-only) cold-start calibration into a live signal: given a target
skill's estimated difficulty, it selects a difficulty BAND for the next item, targeting an ~80%
success frontier. The band is a **Generator hint only** — it is never a parameter of the Evidence
Gate's `verify()` and never an input to `mint()`. The gate independently re-grounds and re-checks
whatever item it receives, so a harder/easier band can never make an ungrounded item pass, and the
credential's readiness stays derived from the ontology regardless of band.

Honesty (stated in docs/demo): this runs on a SYNTHETIC cold-start learner-response set; the band is
labeled "cold-start estimated, selection-only." It selects WHICH grounded item is authored, nothing
more — it is not a live psychometric mastery loop.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# easy -> hard; the Generator authors a more/less demanding (but still grounded) item per band.
BANDS = ("foundational", "core", "stretch")


@dataclass
class AdaptiveController:
    """Maps a skill's cold-start difficulty (p-value = proportion answering correctly) to a band.

    A HIGH p-value means the current item is too easy for a ready learner -> go harder ('stretch').
    A LOW p-value means it is too hard -> go easier ('foundational'). In between -> 'core'. This
    walks toward the `target_success` (~0.80) frontier used by adaptive testing.
    """
    calibration: dict = field(default_factory=dict)   # item_id -> {difficulty, discrimination, ...}
    target_success: float = 0.80
    easy_threshold: float = 0.85    # p above this => too easy => harder band
    hard_threshold: float = 0.55    # p below this => too hard => easier band

    def band_for(self, skill_id: str) -> str:
        """The selected difficulty band for a skill, from its cold-start difficulty (or 'core')."""
        stats = self.calibration.get(f"item-{skill_id}", {})
        return self._band_for_difficulty(stats.get("difficulty"))

    def _band_for_difficulty(self, difficulty: float | None) -> str:
        if difficulty is None:
            return "core"
        if difficulty >= self.easy_threshold:
            return "stretch"
        if difficulty <= self.hard_threshold:
            return "foundational"
        return "core"
