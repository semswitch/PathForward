import json
import unittest

from pathforward.iq import derivation as dv
from pathforward.iq import traversal
from pathforward.iq.seed import HERO_WORKER_ID, build_seed
from pathforward.mcp.route_server import TOOL_NAME, handle_http_body, handle_jsonrpc


class RouteMcpServerTest(unittest.TestCase):
    def setUp(self):
        self.onto = build_seed()
        self.worker = self.onto.workers[HERO_WORKER_ID]
        self.role = self.onto.roles[self.worker.target_role_id]
        # Independent, principled recomputation of what the tool should return.
        self.cert_gap = dv.cert_gap_skill_ids(self.worker, self.role)
        self.expected_admissible = [s for s in self.cert_gap if traversal.is_assessable(s, self.onto)]

    def _call(self, arguments):
        return handle_jsonrpc({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": TOOL_NAME, "arguments": arguments},
        })

    def test_lists_route_facts_tool(self):
        response = handle_jsonrpc({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        tool = response["result"]["tools"][0]
        self.assertEqual(tool["name"], TOOL_NAME)
        self.assertEqual(tool["_meta"]["tool_configuration"]["server_label"], "pathforward-route")
        self.assertEqual(tool["_meta"]["tool_configuration"]["require_approval"], "never")
        self.assertTrue(tool["annotations"]["readOnlyHint"])
        self.assertIn("worker_id", tool["inputSchema"]["required"])

    def test_resolves_admissible_facts_for_hero(self):
        response = self._call({"worker_id": self.worker.id})
        result = response["result"]
        self.assertFalse(result["isError"])
        doc = result["structuredContent"]
        self.assertEqual(doc["status"], "resolved")
        # Target role is resolved from the worker when omitted.
        self.assertEqual(doc["target_role_id"], self.worker.target_role_id)
        self.assertEqual(doc["target_role"], self.role.name)
        self.assertEqual(doc["existing_skills"], list(self.worker.has_skill_ids))
        # Admissible == cert gap INTERSECT assessable, in role order. Non-empty for the hero.
        self.assertEqual(doc["admissible_skill_ids"], self.expected_admissible)
        self.assertTrue(doc["admissible_skill_ids"])
        # Every admissible skill carries a deterministic driving edge + a non-empty approved ref set
        # whose first ref is exactly that driving edge.
        self.assertEqual(set(doc["driving_edge_ids"]), set(doc["admissible_skill_ids"]))
        self.assertEqual(set(doc["approved_ref_map"]), set(doc["admissible_skill_ids"]))
        for sid in doc["admissible_skill_ids"]:
            edge = dv.certgap_edge_id(self.worker.id, sid)
            self.assertEqual(doc["driving_edge_ids"][sid], edge)
            refs = doc["approved_ref_map"][sid]
            self.assertTrue(refs)
            self.assertEqual(refs[0], edge)

    def test_admissible_excludes_unassessable_gap_skills(self):
        # Any cert-gap skill without certification content must be dropped from admissible.
        response = self._call({"worker_id": self.worker.id})
        doc = response["result"]["structuredContent"]
        for sid in doc["admissible_skill_ids"]:
            self.assertTrue(traversal.is_assessable(sid, self.onto))
        unassessable = [s for s in self.cert_gap if not traversal.is_assessable(s, self.onto)]
        for sid in unassessable:
            self.assertNotIn(sid, doc["admissible_skill_ids"])

    def test_unknown_worker_is_structured_rejection(self):
        response = self._call({"worker_id": "EMP-999"})
        result = response["result"]
        self.assertFalse(result["isError"])
        doc = result["structuredContent"]
        self.assertEqual(doc["status"], "rejected")
        self.assertIn("unknown worker_id", doc["error"])
        self.assertEqual(doc["admissible_skill_ids"], [])

    def test_target_role_mismatch_is_structured_rejection(self):
        other_role = next(rid for rid in self.onto.roles if rid != self.worker.target_role_id)
        response = self._call({"worker_id": self.worker.id, "target_role_id": other_role})
        doc = response["result"]["structuredContent"]
        self.assertEqual(doc["status"], "rejected")
        self.assertIn("does not match", doc["error"])

    def test_explicit_matching_target_role_ok(self):
        response = self._call({
            "worker_id": self.worker.id,
            "target_role_id": self.worker.target_role_id,
        })
        doc = response["result"]["structuredContent"]
        self.assertEqual(doc["status"], "resolved")
        self.assertEqual(doc["admissible_skill_ids"], self.expected_admissible)

    def test_http_parse_error_is_json_rpc_error(self):
        result = handle_http_body(b"{not-json")
        self.assertEqual(result.status_code, 400)
        body = json.loads(result.body)
        self.assertEqual(body["error"]["code"], -32700)


if __name__ == "__main__":
    unittest.main()
