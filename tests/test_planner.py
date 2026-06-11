"""Planner behaviour: the LLM proposes a pace/adaptations, but deterministic code owns the hours
(from the cert blueprint), the weekly load (phased to the worker's capacity), the arithmetic
(NumericChecker), and the accessibility adaptations (fixed vocabulary keyed to declared needs)."""
import os
import sys
import unittest
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathforward.agents.client import FakeLLMClient, LLMResponse
from pathforward.agents.numeric import LocalNumericChecker
from pathforward.agents.planner import A11Y_ADAPTATIONS, Planner, canonical_hours
from pathforward.iq import derivation as dv
from pathforward.iq import traversal
from pathforward.iq.seed import build_seed


class _CleanPlannerClient:
    """Proposes a pace at or under capacity -> the gate flags no correction."""
    def respond(self, instructions, input, *, previous_response_id=None, schema=None):
        return LLMResponse("r", "", {"sequence": [], "weekly_hours": 0.0,
                                     "accessibility_adaptations": [], "rationale": "ok"})


class TestPlanner(unittest.TestCase):
    def setUp(self):
        self.onto = build_seed()

    def _ranked(self, worker):
        role = self.onto.roles[worker.target_role_id]
        return tuple(s for s in dv.cert_gap_skill_ids(worker, role)
                     if traversal.is_assessable(s, self.onto))

    def _plan(self, wid, client=None):
        worker = self.onto.workers[wid]
        planner = Planner(client or FakeLLMClient(), LocalNumericChecker())
        return worker, planner.plan(worker, self._ranked(worker), self.onto)

    def _weekly_loads(self, plan):
        by_week: dict[int, float] = defaultdict(float)
        for ph in plan.phases:
            by_week[ph.week] += ph.hours
        return by_week

    def test_canonical_hours_is_deterministic_min_with_tiebreak(self):
        # S08 is certified by AZ-400 (25h) and AZ-305 (30h) -> cheapest path is AZ-400.
        self.assertEqual(canonical_hours("S08", self.onto), (25, "AZ-400"))
        self.assertEqual(canonical_hours("S08", self.onto), canonical_hours("S08", self.onto))
        # S01 is certified only by AZ-204 (20h).
        self.assertEqual(canonical_hours("S01", self.onto), (20, "AZ-204"))

    def test_hours_tie_to_real_cert_hours(self):
        worker, plan = self._plan("EMP-001")
        per_skill: dict[str, float] = defaultdict(float)
        for ph in plan.phases:
            per_skill[ph.skill_id] += ph.hours
            hrs, cert = canonical_hours(ph.skill_id, self.onto)
            self.assertEqual(ph.cert_id, cert)
            # every sourced hour figure equals some real certification's recommended_hours
            self.assertIn(hrs, [c.recommended_hours for c in self.onto.certifications.values()])
        for skill, hrs in per_skill.items():
            self.assertAlmostEqual(hrs, canonical_hours(skill, self.onto)[0])

    def test_total_load_respects_capacity(self):
        worker, plan = self._plan("EMP-001")
        self.assertTrue(plan.capacity_respected)
        for wk, load in self._weekly_loads(plan).items():
            self.assertLessEqual(load, plan.weekly_capacity_hours + 1e-6, f"week {wk} over capacity")
        self.assertAlmostEqual(plan.total_hours, 65.0)            # 20 + 20 + 25
        self.assertEqual(plan.weeks, 17)                          # ceil(65 / 4)

    def test_capacity_violating_llm_plan_is_corrected(self):
        # The code-test client proposes 3x capacity; the gate clamps to real capacity and flags it.
        worker, plan = self._plan("EMP-001")
        self.assertTrue(plan.corrected)
        self.assertTrue(plan.capacity_respected)
        for load in self._weekly_loads(plan).values():
            self.assertLessEqual(load, plan.weekly_capacity_hours + 1e-6)

    def test_clean_pace_is_not_flagged_corrected(self):
        worker, plan = self._plan("EMP-001", client=_CleanPlannerClient())
        self.assertFalse(plan.corrected)

    def test_numeric_check_passes(self):
        worker, plan = self._plan("EMP-001")
        self.assertTrue(plan.numeric_check["ok"])
        self.assertEqual(plan.numeric_check["claim"], "20 + 20 + 25 == 65")

    def test_a11y_only_from_vocabulary(self):
        worker, plan = self._plan("EMP-001")           # low-vision, prefers-audio, screen-reader
        allowed = {a for need in worker.accessibility_needs
                   for a in A11Y_ADAPTATIONS.get(need, ())}
        self.assertTrue(plan.accessibility_adaptations)
        self.assertTrue(set(plan.accessibility_adaptations) <= allowed)
        self.assertNotIn("unlimited tutor hours", plan.accessibility_adaptations)   # out-of-vocab dropped

    def test_zero_a11y_needs_yields_no_adaptations(self):
        worker, plan = self._plan("EMP-003")           # no accessibility needs
        self.assertEqual(worker.accessibility_needs, ())
        self.assertEqual(plan.accessibility_adaptations, ())

    def test_small_capacity_phases_into_many_finite_weeks(self):
        worker, plan = self._plan("EMP-005")           # capacity 3.0h/week, 40h total
        self.assertEqual(plan.weekly_capacity_hours, 3.0)
        self.assertAlmostEqual(plan.total_hours, 40.0)
        self.assertEqual(plan.weeks, 14)               # ceil(40 / 3)
        self.assertTrue(plan.capacity_respected)
        for load in self._weekly_loads(plan).values():
            self.assertLessEqual(load, 3.0 + 1e-6)

    def test_empty_ranked_yields_empty_plan(self):
        worker = self.onto.workers["EMP-001"]
        plan = Planner(FakeLLMClient(), LocalNumericChecker()).plan(worker, (), self.onto)
        self.assertEqual(plan.phases, ())
        self.assertEqual(plan.weeks, 0)
        self.assertAlmostEqual(plan.total_hours, 0.0)
        self.assertTrue(plan.capacity_respected)
        self.assertTrue(plan.numeric_check["ok"])


if __name__ == "__main__":
    unittest.main()
