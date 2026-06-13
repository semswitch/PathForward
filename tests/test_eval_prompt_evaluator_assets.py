from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PromptEvaluatorAssetTests(unittest.TestCase):
    def test_manifest_points_to_prompt(self):
        manifest = json.loads((ROOT / "eval" / "evaluators" / "prompt_manifest.json").read_text())
        self.assertEqual(4, manifest["threshold"])
        self.assertEqual(["pathforward_subjective_quality"], [
            entry["name"] for entry in manifest["evaluators"]
        ])
        for entry in manifest["evaluators"]:
            self.assertTrue((ROOT / entry["local_uri"]).exists())

    def test_prompt_is_subjective_only(self):
        prompt = (ROOT / "eval" / "evaluators" / "subjective_quality_prompt.md").read_text()
        lowered = prompt.lower()
        for phrase in (
            "route reasoning clarity",
            "refusal or abstain quality",
            "user-facing explanation quality",
            "do not score whether deterministic invariants are true",
        ):
            self.assertIn(phrase, lowered)
        self.assertNotIn("output format", lowered)
        self.assertNotIn('"result"', lowered)


if __name__ == "__main__":
    unittest.main()
