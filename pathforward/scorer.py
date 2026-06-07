"""Shared scorer over a normalized FinalTurnTranscript.

The accessibility story (D2) rests on voice and text sharing ONE scoring path. Both
the Voice Live Oral Viva and the typed viva emit a `FinalTurnTranscript`; the scorer
consumes only that object — never raw audio or modality-specific state. The parity
test asserts the same answer scores identically through either modality.
"""
from __future__ import annotations

from dataclasses import dataclass

from .agents.types import AssessmentItem


@dataclass(frozen=True)
class FinalTurnTranscript:
    modality: str                       # 'voice' | 'text'
    turns: tuple[str, ...]
    final_answer: str
    cited_source_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class Score:
    passed: bool
    selected: str
    correct: bool
    cited_source_ids: tuple[str, ...]


def score(transcript: FinalTurnTranscript, item: AssessmentItem) -> Score:
    """Score depends ONLY on the normalized transcript + the item — not the modality."""
    correct = transcript.final_answer.strip().lower() == item.correct_option.strip().lower()
    # a learner answer counts only if grounded (cited at least one approved source)
    passed = correct and len(transcript.cited_source_ids) > 0
    return Score(
        passed=passed,
        selected=transcript.final_answer.strip(),
        correct=correct,
        cited_source_ids=transcript.cited_source_ids,
    )
