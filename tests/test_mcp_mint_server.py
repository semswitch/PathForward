import json
import os
import unittest

from pathforward.agents.evidence_gate import EvidenceGate
from pathforward.agents.generator import Generator
from pathforward.agents.loop import run_assessment_loop
from pathforward.agents.numeric import LocalNumericChecker
from pathforward.credential.mcp_mint import (
    MemoryMintReplayStore,
    create_mcp_mint_request,
)
from pathforward.iq import derivation as dv
from pathforward.iq import traversal
from pathforward.iq.seed import HERO_WORKER_ID, build_seed
from pathforward.mcp.mint_server import TOOL_NAME, handle_http_body, handle_jsonrpc
from tests.fakes import FakeLLMClient


class TestMcpMintServer(unittest.TestCase):
    def setUp(self):
        self.old_key = os.environ.get("PATHFORWARD_MINT_SIGNING_KEY")
        self.old_dev = os.environ.get("PATHFORWARD_ALLOW_DEV_MINT_KEY")
        os.environ["PATHFORWARD_MINT_SIGNING_KEY"] = "mcp-server-test-key"
        os.environ.pop("PATHFORWARD_ALLOW_DEV_MINT_KEY", None)
        onto = build_seed()
        self.worker = onto.workers[HERO_WORKER_ID]
        self.role = onto.roles[self.worker.target_role_id]
        edges = dv.build_all_edges(onto)
        self.driving = traversal.cert_gap_edges(self.worker, onto, edges)[0]
        self.skill = onto.skills[self.driving.target_id]
        allowed = traversal.approved_refs(self.worker, self.skill, onto)
        self.loop = run_assessment_loop(
            self.driving,
            self.skill,
            allowed,
            Generator(FakeLLMClient()),
            EvidenceGate(LocalNumericChecker()),
        )

    def tearDown(self):
        if self.old_key is None:
            os.environ.pop("PATHFORWARD_MINT_SIGNING_KEY", None)
        else:
            os.environ["PATHFORWARD_MINT_SIGNING_KEY"] = self.old_key
        if self.old_dev is None:
            os.environ.pop("PATHFORWARD_ALLOW_DEV_MINT_KEY", None)
        else:
            os.environ["PATHFORWARD_ALLOW_DEV_MINT_KEY"] = self.old_dev

    def _token(self):
        sealed = create_mcp_mint_request(
            self.worker,
            self.role,
            self.driving.id,
            self.skill.id,
            self.loop,
            signing_key="mcp-server-test-key",
        )
        return sealed.token

    def test_initialize_and_tools_list_expose_single_approval_mint_tool(self):
        init = handle_jsonrpc({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        self.assertEqual(init["result"]["serverInfo"]["name"], "pathforward-mint")

        listed = handle_jsonrpc({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        tools = listed["result"]["tools"]
        self.assertEqual([tool["name"] for tool in tools], [TOOL_NAME])
        tool = tools[0]
        self.assertEqual(tool["_meta"]["tool_configuration"]["require_approval"], "always")
        self.assertEqual(tool["inputSchema"]["required"], ["mint_request_token"])
        self.assertNotIn("verified", tool["inputSchema"]["properties"])

    def test_notification_initialized_returns_no_body(self):
        self.assertIsNone(handle_jsonrpc({
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        }))

    def test_tools_call_mints_from_signed_token(self):
        response = handle_jsonrpc(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": TOOL_NAME,
                    "arguments": {"mint_request_token": self._token()},
                },
            },
            replay_store=MemoryMintReplayStore(),
        )
        result = response["result"]
        self.assertFalse(result["isError"])
        structured = result["structuredContent"]
        self.assertEqual(structured["status"], "minted")
        subject = structured["credential"]["credentialSubject"]
        self.assertEqual(subject["worker_id"], self.worker.id)
        self.assertEqual(subject["cited_edge_id"], self.driving.id)

    def test_tools_call_rejects_tampered_token_as_tool_error(self):
        token = self._token()
        payload, sig = token.split(".", 1)
        tampered = f"{payload[:-1]}X.{sig}"
        response = handle_jsonrpc({
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": TOOL_NAME,
                "arguments": {"mint_request_token": tampered},
            },
        })
        result = response["result"]
        self.assertTrue(result["isError"])
        self.assertIn("rejected", result["content"][0]["text"])

    def test_http_body_handles_parse_and_success(self):
        bad = handle_http_body(b"{not-json")
        self.assertEqual(bad.status_code, 400)

        good = handle_http_body(json.dumps({
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/list",
        }).encode("utf-8"))
        self.assertEqual(good.status_code, 200)
        self.assertIn(TOOL_NAME, good.body)


if __name__ == "__main__":
    unittest.main()
