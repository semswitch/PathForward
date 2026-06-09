import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathforward.toolbox_mcp import ToolboxMcpClient


class FakeResponse:
    def __init__(self, text: str, content_type: str):
        self.text = text
        self.headers = {"content-type": content_type}


class TestToolboxMcpClient(unittest.TestCase):
    def test_parse_json_response(self):
        parsed = ToolboxMcpClient._parse_response(FakeResponse(
            json.dumps({"jsonrpc": "2.0", "result": {"ok": True}}),
            "application/json",
        ))
        self.assertEqual(parsed["result"]["ok"], True)

    def test_parse_event_stream_response(self):
        parsed = ToolboxMcpClient._parse_response(FakeResponse(
            "event: message\n"
            "data: {\"jsonrpc\":\"2.0\",\"result\":{\"resources\":[{\"uri\":\"skill://pathforward/SKILL.md\"}]}}\n\n",
            "text/event-stream",
        ))
        self.assertEqual(parsed["result"]["resources"][0]["uri"], "skill://pathforward/SKILL.md")


if __name__ == "__main__":
    unittest.main()
