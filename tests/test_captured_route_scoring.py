"""pathforward/captured_route.py normalizer + canonical schema tests.

The evaluator scoring tests live in test_required_tool_calls.py / test_fabric_live_source.py; this file
covers the normalizer that feeds BOTH live sources (streamed probe items, staged proof rows) into the
canonical captured_events schema, plus the legacy-surface reconstruction.
"""

from __future__ import annotations

import unittest

from pathforward import captured_route as cr
from tests.captured_route_fixtures import reasoning_events


class NormalizerTests(unittest.TestCase):
    def test_stream_items_drop_reasoning_and_discovery(self):
        items = [
            {"type": "mcp_list_tools", "server_label": "pathforward-route"},
            {"type": "reasoning", "id": "rs_1"},
            {"type": "mcp_call", "server_label": "pathforward-route", "name": "resolve_route_facts",
             "status": "completed", "id": "mcp_1"},
            {"type": "a2a_preview_call", "name": "pathforward-a2a-curator", "status": "completed",
             "id": "fc_1", "call_id": "call_1"},
        ]
        events = cr.events_from_stream_items(items)
        self.assertEqual([(e["type"], e["label"]) for e in events],
                         [("mcp_call", "pathforward-route"), ("a2a_preview_call", "pathforward-a2a-curator")])
        self.assertEqual([e["index"] for e in events], [1, 2])

    def test_staged_approval_row_without_status_becomes_completed(self):
        rows = [
            {"type": "mcp_approval_request", "server_label": "pathforward-mint", "name": "x", "id": "ar_1"},
            {"type": "mcp_call", "server_label": "pathforward-mint", "name": "pathforward_mint_credential",
             "status": "completed", "output_preview": '{"mint_state":"minted"}', "id": "mc_1"},
        ]
        events = cr.events_from_staged_rows(rows)
        approval = next(e for e in events if e["type"] == "mcp_approval_request")
        self.assertEqual(approval["status"], "completed")  # milestone item defaulted
        self.assertEqual(approval["label"], "pathforward-mint")

    def test_label_prefers_server_label_then_name(self):
        events = cr.events_from_stream_items([
            {"type": "mcp_call", "server_label": "pathforward-gate",
             "name": "verify_assessment_and_issue_mint_request", "status": "completed", "id": "m"},
            {"type": "a2a_preview_call", "name": "pathforward-a2a-planner", "status": "completed", "id": "f"},
        ])
        self.assertEqual(events[0]["label"], "pathforward-gate")     # server_label wins for MCP
        self.assertEqual(events[1]["label"], "pathforward-a2a-planner")  # name for A2A

    def test_redaction_strips_mint_token_from_output(self):
        events = cr.events_from_stream_items([
            {"type": "mcp_call", "server_label": "pathforward-mint", "name": "m", "status": "completed",
             "id": "mc_1", "output": "mint_request_token=eyJabc.def.ghi credential ok"},
        ])
        self.assertNotIn("eyJabc.def.ghi", events[0]["output"])
        self.assertIn("[REDACTED", events[0]["output"])

    def test_build_canonical_capture_shape(self):
        cap = cr.build_canonical_capture(
            agent="pathforward-orchestrator", query="q", response_id="resp_1",
            status="completed", source="stream", events=reasoning_events(),
        )
        self.assertEqual(cap["schema_version"], cr.SCHEMA_VERSION)
        self.assertEqual(cap["response_id"], "resp_1")
        self.assertTrue(all("type" in e and "label" in e and "status" in e for e in cap["captured_events"]))

    def test_legacy_surface_reconstruction_carries_route_and_message(self):
        surface = cr.reconstruct_legacy_surface(reasoning_events())
        labels = {it.get("server_label") or it.get("name") for it in surface["output_items"]}
        self.assertIn("pathforward-gate", labels)
        self.assertIn("pathforward-a2a-insights", labels)
        self.assertIn("minting requires approval", surface["output_text"])


if __name__ == "__main__":
    unittest.main()
