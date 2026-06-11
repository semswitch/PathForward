"""Adaptive difficulty: a PURE-CODE controller maps cold-start calibration to a difficulty BAND that
is a Generator HINT only. It must never change the gate's verdict, never enter mint(), and must be
observable in code-contract tests."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathforward.agents.adaptive import AdaptiveController, BANDS
from tests.fakes import FakeLLMClient
from pathforward.agents.evidence_gate import EvidenceGate
from pathforward.agents.numeric import LocalNumericChecker
from pathforward.agents.types import AssessmentItem


def _code_test_item(band, attempt=1):
    return FakeLLMClient._generate({"skill_name": "X", "driving_edge_id": "certgap::EMP-001::S01",
                                    "allowed_ref_ids": ["certgap::EMP-001::S01"], "attempt": attempt,
                                    "difficulty_band": band})


class TestAdaptiveController(unittest.TestCase):
    def test_band_maps_difficulty_toward_the_frontier(self):
        c = AdaptiveController(calibration={
            "item-EASY": {"difficulty": 0.95},   # too easy -> go harder
            "item-HARD": {"difficulty": 0.40},   # too hard -> go easier
            "item-MID": {"difficulty": 0.65},
        })
        self.assertEqual(c.band_for("EASY"), "stretch")
        self.assertEqual(c.band_for("HARD"), "foundational")
        self.assertEqual(c.band_for("MID"), "core")
        self.assertEqual(c.band_for("UNKNOWN"), "core")   # no calibration -> safe default

    def test_controller_is_pure_code_no_llm_client(self):
        c = AdaptiveController()
        self.assertFalse(hasattr(c, "client"))            # no model handle -> cannot call an LLM
        self.assertIn(c.band_for("anything"), BANDS)

    def test_band_varies_the_generated_item(self):
        f, s = _code_test_item("foundational"), _code_test_item("stretch")
        self.assertNotEqual(f["stem"], s["stem"])
        self.assertNotEqual(f["numeric_claim"], s["numeric_claim"])

    def test_core_band_reproduces_the_canonical_item(self):
        self.assertEqual(_code_test_item("core")["numeric_claim"], "18 + 6 == 24")
        self.assertEqual(_code_test_item(None)["numeric_claim"], "18 + 6 == 24")   # default == core

    def test_every_band_item_passes_the_gate_identically(self):
        # The gate applies the SAME criteria regardless of band — the band changes the item, not the
        # judgment. Each grounded band item passes cleanly.
        gate = EvidenceGate(LocalNumericChecker())
        for band in BANDS:
            d = _code_test_item(band)
            item = AssessmentItem(id="i", targeted_skill_id="S01",
                                  driving_edge_id="certgap::EMP-001::S01",
                                  stem=d["stem"], options=tuple(d["options"]),
                                  answer_index=d["answer_index"], cited_ref_ids=tuple(d["cited_ref_ids"]),
                                  retrieved_ref_ids=("certgap::EMP-001::S01",),
                                  numeric_claim=d["numeric_claim"])
            verdict = gate.verify(item, ("certgap::EMP-001::S01",))
            self.assertTrue(verdict.passed, f"band {band} item should pass; failed {verdict.failed_reasons}")


if __name__ == "__main__":
    unittest.main()
