"""required_tool_calls evaluator: structured ordered-route grading + its real failure modes.

Authoritative path grades an ordered subsequence of completed captured_events. The negative cases are
the point -- a check that only ever returns 1.0 proves nothing.
"""

from __future__ import annotations

import unittest

from tests.captured_route_fixtures import (
    REASONING_EXPECTED_ROUTE,
    ev,
    load_evaluator,
    reasoning_events,
    reasoning_item,
)


class RequiredToolCallsStructuredTests(unittest.TestCase):
    def setUp(self):
        self.grade = load_evaluator("required_tool_calls").grade

    def test_full_reasoning_route_passes(self):
        self.assertEqual(1.0, self.grade({}, reasoning_item(reasoning_events())))

    def test_missing_generator_fails(self):
        events = [e for e in reasoning_events() if e["label"] != "pathforward-a2a-generator"]
        self.assertEqual(0.0, self.grade({}, reasoning_item(events)))

    def test_missing_insights_fails(self):
        events = [e for e in reasoning_events() if e["label"] != "pathforward-a2a-insights"]
        self.assertEqual(0.0, self.grade({}, reasoning_item(events)))

    def test_critic_before_generator_fails(self):
        events = reasoning_events()
        # Swap the critic call ahead of the generator call -> order violated.
        gi = next(i for i, e in enumerate(events)
                  if e["type"] == "a2a_preview_call" and e["label"] == "pathforward-a2a-generator")
        ci = next(i for i, e in enumerate(events)
                  if e["type"] == "a2a_preview_call" and e["label"] == "pathforward-a2a-critic")
        events[gi], events[ci] = events[ci], events[gi]
        self.assertEqual(0.0, self.grade({}, reasoning_item(events)))

    def test_insights_incomplete_fails(self):
        events = reasoning_events(insights_status="in_progress")
        self.assertEqual(0.0, self.grade({}, reasoning_item(events)))

    def test_a2a_output_rows_do_not_satisfy_the_call_requirement(self):
        # Only the *_output rows present (no a2a_preview_call rows) must NOT pass.
        events = [ev("mcp_call", "pathforward-route", server_label="pathforward-route")]
        events += [ev("a2a_preview_call_output", lbl) for lbl in REASONING_EXPECTED_ROUTE if "a2a" in lbl]
        self.assertEqual(0.0, self.grade({}, reasoning_item(events)))

    def test_required_sequence_falls_back_to_must_emit(self):
        item = reasoning_item(reasoning_events(), expected_route=None,
                              must_emit=["pathforward-route", "pathforward-gate"])
        self.assertEqual(1.0, self.grade({}, item))

    def test_no_requirement_passes(self):
        item = reasoning_item(reasoning_events(), expected_route=None, must_emit=["approval required"])
        self.assertEqual(1.0, self.grade({}, item))


class RequiredToolCallsFailClosedTests(unittest.TestCase):
    """captured_events ABSENT (the demoted cloud path) must NOT vacuously pass an A2A route."""

    def setUp(self):
        self.grade = load_evaluator("required_tool_calls").grade

    def _cloud_item(self, output_items, **over):
        # No captured_events anywhere -- mimics azure_ai_target_completions sample.output.
        row = {
            "expected_route": list(REASONING_EXPECTED_ROUTE),
            "must_emit": list(REASONING_EXPECTED_ROUTE),
        }
        row.update(over)
        return {**row, "sample": {"output_items": output_items, "output_text": ""}}

    def test_a2a_route_without_captured_events_fails_even_if_output_items_undercaptured(self):
        # The cloud surface captures only the MCP calls (route, gate); A2A hops are missing.
        item = self._cloud_item([
            {"type": "mcp_call", "server_label": "pathforward-route"},
            {"type": "mcp_call", "server_label": "pathforward-gate"},
        ])
        self.assertEqual(0.0, self.grade({}, item))

    def test_a2a_route_without_captured_events_fails_even_if_names_leak_into_text(self):
        # Even if the A2A names appear as text in output_items, an A2A route is NOT confirmable without
        # the structured capture -> fail closed (not a vacuous text-match pass).
        item = self._cloud_item([
            {"type": "message", "role": "assistant",
             "content": "called pathforward-a2a-curator, pathforward-a2a-generator, "
                        "pathforward-a2a-critic, pathforward-gate, pathforward-a2a-planner, "
                        "pathforward-a2a-insights, pathforward-route"},
        ])
        self.assertEqual(0.0, self.grade({}, item))

    def test_non_a2a_requirement_without_captured_events_uses_legacy(self):
        # A pure MCP requirement (route + gate, no A2A) can still be graded from the cloud surface.
        item = self._cloud_item([
            {"type": "mcp_call", "server_label": "pathforward-route"},
            {"type": "mcp_call", "server_label": "pathforward-gate"},
        ], expected_route=["pathforward-route", "pathforward-gate"],
            must_emit=["pathforward-route", "pathforward-gate"])
        self.assertEqual(1.0, self.grade({}, item))


if __name__ == "__main__":
    unittest.main()
