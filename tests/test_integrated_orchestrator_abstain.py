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
            "abstain_state": "ABSTAIN_FAIL_CLOSED",
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

    def test_mcp_list_tools_is_not_gate_or_mint_execution(self):
        rows = [
            {"type": "mcp_list_tools", "server_label": "pathforward-gate"},
            {"type": "mcp_list_tools", "server_label": "pathforward-mint"},
            {"type": "message", "abstain_state": "ABSTAIN_FAIL_CLOSED", "message_preview": "{}"},
        ]
        observations = smoke._observations(rows)

        self.assertFalse(observations["gate_mcp"])
        self.assertFalse(observations["mint_mcp"])
        self.assertTrue(observations["abstain"])

    def test_abstain_prompt_forbids_downstream_mint_path(self):
        prompt = smoke._abstain_prompt(123)

        self.assertIn("EMP-ABSTAIN", prompt)
        self.assertIn("admissible certification-gap skill set is empty: []", prompt)
        self.assertIn("do not call Generator, Critic, Evidence Gate", prompt)
        self.assertIn("no mint request was created", prompt)

    def test_stream_redaction_removes_system_prompt_and_tokens(self):
        redacted = smoke._redact_jsonable({
            "role": "system",
            "content": "hidden instructions with mint_request_token=abc.def",
        })

        self.assertEqual("[REDACTED_SYSTEM_PROMPT]", redacted["content"])

    def test_stream_redaction_removes_response_instructions(self):
        redacted = smoke._redact_jsonable({
            "response": {
                "instructions": "hosted agent instructions",
                "id": "resp_123",
            },
        })

        self.assertEqual("[REDACTED_SYSTEM_PROMPT]", redacted["response"]["instructions"])
        self.assertEqual("resp_123", redacted["response"]["id"])


if __name__ == "__main__":
    unittest.main()
