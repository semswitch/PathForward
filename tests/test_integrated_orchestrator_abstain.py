from __future__ import annotations

import json
import unittest
from types import SimpleNamespace

from scripts import smoke_integrated_orchestrator_live as smoke


def _message(text: str) -> SimpleNamespace:
    return SimpleNamespace(type="message", content=[SimpleNamespace(text=text)])


class IntegratedOrchestratorAbstainTests(unittest.TestCase):
    def test_final_json_not_abstained_is_false(self):
        final = {
            "gate_status": "verified",
            "abstain_state": "not_abstained",
            "mint_state": {"status": "minted"},
        }
        rows, _ = smoke._summarize_response(SimpleNamespace(output=[_message(json.dumps(final))]))

        self.assertEqual("not_abstained", rows[0]["abstain_state"])
        self.assertFalse(smoke._observations(rows)["abstain"])

    def test_final_json_abstain_is_true(self):
        final = {
            "gate_status": "rejected",
            "abstain_state": "ABSTAIN",
            "mint_state": {"status": "not_requested"},
        }
        rows, _ = smoke._summarize_response(SimpleNamespace(output=[_message(json.dumps(final))]))

        self.assertTrue(smoke._observations(rows)["abstain"])

    def test_code_fenced_final_json_is_parsed(self):
        rows, _ = smoke._summarize_response(SimpleNamespace(output=[_message(
            '```json\n{"abstain_state":"not-abstained"}\n```'
        )]))

        self.assertFalse(smoke._observations(rows)["abstain"])

    def test_fallback_ignores_negated_abstain_text(self):
        rows = [{"type": "message", "message_preview": "Final state: NOT_ABSTAIN. No ABSTAIN happened."}]

        self.assertFalse(smoke._observations(rows)["abstain"])

    def test_fallback_detects_explicit_abstain_text(self):
        rows = [{"type": "message", "message_preview": "Gate failed closed: ABSTAIN. No mint request."}]

        self.assertTrue(smoke._observations(rows)["abstain"])


if __name__ == "__main__":
    unittest.main()
