"""fabric_live_source evaluator: ground on the Insights specialist's OWN output, never final prose.

Negative cases prove the grounding is real: a missing/incomplete Insights hop, an output lacking
fabric-live or a metric, a derivation-floor source, and -- critically -- final prose that *claims*
fabric-live without a real Insights event all FAIL.
"""

from __future__ import annotations

import unittest

from tests.captured_route_fixtures import ev, load_evaluator, reasoning_events, reasoning_item


class FabricLiveSourceStructuredTests(unittest.TestCase):
    def setUp(self):
        self.grade = load_evaluator("fabric_live_source").grade

    def test_live_insights_output_passes(self):
        self.assertEqual(1.0, self.grade({}, reasoning_item(reasoning_events())))

    def test_no_insights_call_fails(self):
        events = [e for e in reasoning_events() if e["label"] != "pathforward-a2a-insights"]
        self.assertEqual(0.0, self.grade({}, reasoning_item(events)))

    def test_insights_incomplete_fails(self):
        self.assertEqual(0.0, self.grade({}, reasoning_item(reasoning_events(insights_status="in_progress"))))

    def test_insights_output_without_fabric_live_fails(self):
        events = reasoning_events(insights_output="cohort_size: 11\naverage_readiness: 0.59")
        self.assertEqual(0.0, self.grade({}, reasoning_item(events)))

    def test_insights_output_without_metric_fails(self):
        events = reasoning_events(insights_output="source=fabric-live")
        self.assertEqual(0.0, self.grade({}, reasoning_item(events)))

    def test_derivation_floor_fails(self):
        events = reasoning_events(insights_output="source=derivation-floor\ncohort_size: 11")
        self.assertEqual(0.0, self.grade({}, reasoning_item(events)))

    def test_final_prose_fabric_live_without_insights_event_fails(self):
        # No Insights A2A event at all, but the orchestrator's final message restates fabric-live + a
        # metric. Grounding on the specialist's own output (not prose) must FAIL.
        events = [e for e in reasoning_events() if "insights" not in e["label"]]
        for e in events:
            if e["type"] == "message":
                e["text"] = "fabric_insight_summary: source=fabric-live, cohort_size 11, avg readiness 0.59"
        self.assertEqual(0.0, self.grade({}, reasoning_item(events)))

    def test_insights_output_event_present_but_call_not_completed_fails(self):
        # The *_output row carries fabric-live, but the a2a_preview_call itself never completed.
        events = reasoning_events()
        for e in events:
            if e["type"] == "a2a_preview_call" and e["label"] == "pathforward-a2a-insights":
                e["status"] = "failed"
        self.assertEqual(0.0, self.grade({}, reasoning_item(events)))

    def test_non_fabric_row_passes_without_insights(self):
        item = reasoning_item([ev("mcp_call", "pathforward-route")],
                             feature_area="safety", risk_category="safety",
                             must_emit=["pathforward-route"])
        self.assertEqual(1.0, self.grade({}, item))


class FabricLiveSourceFailClosedTests(unittest.TestCase):
    """captured_events ABSENT -> a Fabric row cannot be confirmed from prose; fail closed."""

    def setUp(self):
        self.grade = load_evaluator("fabric_live_source").grade

    def test_fabric_row_without_captured_events_fails_even_with_prose(self):
        item = {
            "feature_area": "prompt_orchestrator_full_route_fabric",
            "risk_category": "fabric",
            "must_emit": ["source=fabric-live"],
            "sample": {
                "output_text": "source=fabric-live; cohort_size 11; average_readiness 0.5909",
                "output_items": [{"type": "message", "role": "assistant",
                                  "content": "source=fabric-live cohort_size 11"}],
            },
        }
        self.assertEqual(0.0, self.grade({}, item))

    def test_non_fabric_row_without_captured_events_passes(self):
        item = {
            "feature_area": "safety",
            "risk_category": "safety",
            "must_emit": ["pathforward-route"],
            "sample": {"output_text": "no fabric here", "output_items": []},
        }
        self.assertEqual(1.0, self.grade({}, item))


if __name__ == "__main__":
    unittest.main()
