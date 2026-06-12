import json
import os
import unittest

from pathforward.credential.mcp_mint import MemoryMintReplayStore, mint_from_mcp_request
from pathforward.iq import derivation as dv
from pathforward.iq import traversal
from pathforward.iq.seed import HERO_WORKER_ID, build_seed
from pathforward.mcp.gate_server import TOOL_NAME, handle_http_body, handle_jsonrpc


class _StaticRetriever:
    def __init__(self, refs):
        self.refs = tuple(refs)
        self.calls = []

    def retrieve_refs(self, *, query, allowed_ref_ids, worker_id, role_id, skill_id):
        self.calls.append({
            "query": query,
            "allowed_ref_ids": allowed_ref_ids,
            "worker_id": worker_id,
            "role_id": role_id,
            "skill_id": skill_id,
        })
        return self.refs


class GateMcpServerTest(unittest.TestCase):
    def setUp(self):
        self.old_key = os.environ.get("PATHFORWARD_MINT_SIGNING_KEY")
        os.environ["PATHFORWARD_MINT_SIGNING_KEY"] = "gate-mcp-test-key"
        self.onto = build_seed()
        self.worker = self.onto.workers[HERO_WORKER_ID]
        self.role = self.onto.roles[self.worker.target_role_id]
        self.skill_id = "S01"
        self.skill = self.onto.skills[self.skill_id]
        self.driving_edge_id = dv.certgap_edge_id(self.worker.id, self.skill_id)
        self.allowed = traversal.approved_refs(self.worker, self.skill, self.onto)

    def tearDown(self):
        if self.old_key is None:
            os.environ.pop("PATHFORWARD_MINT_SIGNING_KEY", None)
        else:
            os.environ["PATHFORWARD_MINT_SIGNING_KEY"] = self.old_key

    def _args(self, **overrides):
        item = {
            "stem": "Which evidence-supported action addresses the selected Cloud Engineer skill gap?",
            "options": [
                "Ignore the target role",
                "Use the cited certification path",
                "Change the worker identity",
                "Skip verification",
            ],
            "answer_index": 1,
            "cited_ref_ids": [
                self.driving_edge_id,
                "requires::R-CLOUD::S01",
                "corpus::AZ-204",
            ],
            "numeric_claim": None,
        }
        base = {
            "worker_id": self.worker.id,
            "target_role_id": self.role.id,
            "skill_id": self.skill_id,
            "driving_edge_id": self.driving_edge_id,
            "attempt": 0,
            "item": item,
        }
        base.update(overrides)
        return base

    def _call(self, args, retriever):
        return handle_jsonrpc(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": TOOL_NAME, "arguments": args},
            },
            retriever_factory=lambda: retriever,
        )

    def test_lists_gate_issuer_tool(self):
        response = handle_jsonrpc({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        tool = response["result"]["tools"][0]
        self.assertEqual(tool["name"], TOOL_NAME)
        self.assertEqual(tool["_meta"]["tool_configuration"]["server_label"], "pathforward-gate")
        self.assertEqual(tool["_meta"]["tool_configuration"]["require_approval"], "never")
        self.assertIn("item", tool["inputSchema"]["required"])

    def test_verified_item_issues_token_consumable_by_mint_tool(self):
        retriever = _StaticRetriever(self.allowed)
        response = self._call(self._args(), retriever)
        result = response["result"]
        self.assertFalse(result["isError"])
        structured = result["structuredContent"]
        self.assertEqual(structured["status"], "verified")
        token = structured["mint_request"]["arguments"]["mint_request_token"]
        credential = mint_from_mcp_request(
            self.worker,
            self.role,
            token,
            replay_store=MemoryMintReplayStore(),
            signing_key="gate-mcp-test-key",
        )
        self.assertEqual(credential.credential_subject["cited_edge_id"], self.driving_edge_id)

    def test_unretrieved_citation_rejects_without_token(self):
        retriever = _StaticRetriever(("requires::R-CLOUD::S01",))
        response = self._call(self._args(), retriever)
        structured = response["result"]["structuredContent"]
        self.assertEqual(structured["status"], "rejected")
        self.assertIsNone(structured["mint_request"])
        self.assertIn("grounded", structured["feedback"]["failed_criteria"])

    def test_forged_driving_edge_is_structured_rejection(self):
        response = self._call(
            self._args(driving_edge_id="certgap::EMP-999::S01"),
            _StaticRetriever(self.allowed),
        )
        result = response["result"]
        self.assertFalse(result["isError"])
        structured = result["structuredContent"]
        self.assertEqual(structured["status"], "rejected")
        self.assertIsNone(structured["mint_request"])
        self.assertIn("driving_edge_id", structured["error"])
        self.assertIn("input_contract", structured["feedback"]["failed_criteria"])

    def test_http_parse_error_is_json_rpc_error(self):
        result = handle_http_body(b"{not-json")
        self.assertEqual(result.status_code, 400)
        body = json.loads(result.body)
        self.assertEqual(body["error"]["code"], -32700)


if __name__ == "__main__":
    unittest.main()
