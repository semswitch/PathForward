import json
import unittest

from pathforward.agents.client import LLMResponse
from pathforward.mcp.fabric_server import TOOL_NAME, handle_http_body, handle_jsonrpc


class _FakeFabricClient:
    def respond(self, instructions, input, *, previous_response_id=None, schema=None):
        return LLMResponse(
            "run_1",
            "The Cloud Engineer cohort size is 11 and average readiness is 0.5909.",
            {"narrative": "ok"},
            previous_response_id,
        )

    def close(self):
        return None


def _client_factory():
    return _FakeFabricClient()


class FabricMcpServerTest(unittest.TestCase):
    def test_lists_read_only_fabric_tool(self):
        response = handle_jsonrpc({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        tools = response["result"]["tools"]
        self.assertEqual(tools[0]["name"], TOOL_NAME)
        self.assertTrue(tools[0]["annotations"]["readOnlyHint"])
        self.assertEqual(
            tools[0]["_meta"]["tool_configuration"]["server_label"],
            "pathforward-fabric",
        )

    def test_calls_fabric_query_tool(self):
        response = handle_jsonrpc(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": TOOL_NAME,
                    "arguments": {"query": "Cloud Engineer cohort size"},
                },
            },
            client_factory=_client_factory,
        )
        result = response["result"]
        self.assertFalse(result["isError"])
        self.assertEqual(result["structuredContent"]["source"], "fabric-live")
        self.assertIn("11", result["structuredContent"]["narrative"])

    def test_http_parse_error_is_json_rpc_error(self):
        result = handle_http_body(b"{not-json", client_factory=_client_factory)
        self.assertEqual(result.status_code, 400)
        body = json.loads(result.body)
        self.assertEqual(body["error"]["code"], -32700)


if __name__ == "__main__":
    unittest.main()
