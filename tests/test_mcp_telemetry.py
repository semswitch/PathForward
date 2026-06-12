import json
import unittest

from pathforward.mcp.telemetry import emit_mcp_result_event


class McpTelemetryTests(unittest.TestCase):
    def test_gate_event_redacts_token_and_records_counts(self):
        calls = []

        def emitter(connection_string, name, *, properties=None, measurements=None, timeout=5.0):
            calls.append({
                "connection_string": connection_string,
                "name": name,
                "properties": properties or {},
                "measurements": measurements or {},
            })
            return True

        body = json.dumps({
            "result": {
                "isError": False,
                "structuredContent": {
                    "status": "verified",
                    "worker_id": "EMP-001",
                    "target_role_id": "R-CLOUD",
                    "skill_id": "S01",
                    "driving_edge_id": "certgap::EMP-001::S01",
                    "approved_ref_ids": ["a", "b"],
                    "retrieved_ref_ids": ["a", "b"],
                    "effective_allowed_ref_ids": ["a"],
                    "mint_request": {
                        "arguments": {"mint_request_token": "secret-token"},
                        "request": {"request_id": "mcpmint_123"},
                    },
                },
            }
        })
        self.assertTrue(emit_mcp_result_event(
            "gate-mcp",
            body,
            200,
            emitter=emitter,
            connection_string="InstrumentationKey=test",
        ))
        call = calls[0]
        self.assertEqual(call["name"], "pathforward.mcp.gate")
        self.assertEqual(call["properties"]["pf.status"], "verified")
        self.assertEqual(call["properties"]["pf.mint_request_created"], "True")
        self.assertEqual(call["properties"]["pf.request_id"], "mcpmint_123")
        self.assertEqual(call["measurements"]["pf.effective_ref_count"], 1.0)
        serialized = json.dumps(call, sort_keys=True)
        self.assertNotIn("secret-token", serialized)

    def test_mint_event_records_credential_without_evidence(self):
        calls = []

        def emitter(connection_string, name, *, properties=None, measurements=None, timeout=5.0):
            calls.append({"name": name, "properties": properties or {}, "measurements": measurements or {}})
            return True

        body = json.dumps({
            "result": {
                "isError": False,
                "structuredContent": {
                    "status": "minted",
                    "request_id": "mcpmint_456",
                    "credential": {
                        "credentialSubject": {
                            "worker_id": "EMP-001",
                            "target_role_id": "R-CLOUD",
                            "skill_id": "S02",
                            "readiness": 0.5,
                            "cited_edge_id": "certgap::EMP-001::S02",
                        },
                        "evidence": ["do-not-log"],
                    },
                },
            }
        })
        self.assertTrue(emit_mcp_result_event("mcp", body, 200, emitter=emitter))
        call = calls[0]
        self.assertEqual(call["name"], "pathforward.mcp.mint")
        self.assertEqual(call["properties"]["pf.credential_issued"], "true")
        self.assertEqual(call["properties"]["pf.skill"], "S02")
        self.assertEqual(call["measurements"]["pf.readiness"], 0.5)
        self.assertNotIn("do-not-log", json.dumps(call, sort_keys=True))

    def test_skips_initialize_and_tools_list_shapes(self):
        calls = []

        def emitter(connection_string, name, *, properties=None, measurements=None, timeout=5.0):
            calls.append(name)
            return True

        body = json.dumps({"result": {"serverInfo": {"name": "pathforward-gate"}}})
        self.assertFalse(emit_mcp_result_event("gate-mcp", body, 200, emitter=emitter))
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
