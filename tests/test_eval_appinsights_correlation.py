from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from scripts import correlate_eval_appinsights as corr


class EvalAppInsightsCorrelationTests(unittest.TestCase):
    def test_parse_azd_env_values(self):
        parsed = corr._parse_azd_env_values('AZURE_RESOURCE_GROUP="rg-example-eus2"\nBAD LINE\nX=1\n')
        self.assertEqual("rg-example-eus2", parsed["AZURE_RESOURCE_GROUP"])
        self.assertEqual("1", parsed["X"])

    def test_dataset_info_uses_sha_and_row_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dataset.jsonl"
            path.write_text('{"a":1}\n\n{"b":2}\n', encoding="utf-8")
            old_root = corr.ROOT
            try:
                corr.ROOT = Path(tmp)
                info = corr._dataset_info({"dataset_file": "dataset.jsonl"})
            finally:
                corr.ROOT = old_root
        self.assertTrue(info["dataset_version"].startswith("sha256:"))
        self.assertEqual(2, info["row_count"])

    def test_eval_failure_counts(self):
        counts = corr._eval_failure_counts([
            {"results": [
                {"status": "completed", "passed": True},
                {"status": "completed", "passed": False},
                {"status": "failed", "passed": False},
            ]},
            {"results": []},
        ])
        self.assertEqual(2, counts["row_count"])
        self.assertEqual(2, counts["evaluator_failure_count"])
        self.assertEqual(1, counts["evaluator_error_count"])

    def test_first_row_maps_columns(self):
        result = {
            "tables": [{
                "columns": [{"name": "telemetry_event_count"}, {"name": "product_failure_count"}],
                "rows": [[3, 1]],
            }]
        }
        self.assertEqual({"telemetry_event_count": 3, "product_failure_count": 1},
                         corr._first_row(result))

    def test_kql_includes_window_and_agent(self):
        start = datetime(2026, 6, 12, 23, 0, tzinfo=UTC)
        end = datetime(2026, 6, 12, 23, 30, tzinfo=UTC)
        query = corr._events_query(start, end, "pathforward-orchestrator")
        self.assertIn("datetime(2026-06-12T23:00:00Z)", query)
        self.assertIn("agent_name == 'pathforward-orchestrator'", query)
        self.assertIn("pathforward.mcp.gate", query)


if __name__ == "__main__":
    unittest.main()
