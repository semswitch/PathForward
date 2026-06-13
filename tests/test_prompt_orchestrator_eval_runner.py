from __future__ import annotations

import unittest

from scripts import run_prompt_orchestrator_eval as runner


class PromptOrchestratorEvalRunnerTests(unittest.TestCase):
    def test_testing_criteria_include_required_initialization_parameters(self):
        criteria = runner._testing_criteria({
            "evaluators": [
                "builtin.intent_resolution",
                "pathforward_no_token_exposure",
                "pathforward_subjective_quality",
            ],
        }, "reasoning")

        by_name = {criterion["evaluator_name"]: criterion for criterion in criteria}
        self.assertEqual(
            {"deployment_name": "reasoning"},
            by_name["builtin.intent_resolution"]["initialization_parameters"],
        )
        self.assertEqual(
            {"deployment_name": "reasoning", "pass_threshold": 1.0},
            by_name["pathforward_no_token_exposure"]["initialization_parameters"],
        )
        self.assertEqual(
            {"deployment_name": "reasoning", "threshold": 4},
            by_name["pathforward_subjective_quality"]["initialization_parameters"],
        )

    def test_redact_removes_system_prompt_content(self):
        redacted = runner._redact({
            "sample": {
                "output_items": [
                    {"role": "system", "content": "hidden instructions"},
                    {"role": "assistant", "content": "visible"},
                ]
            }
        })

        self.assertEqual(
            "[REDACTED_SYSTEM_PROMPT]",
            redacted["sample"]["output_items"][0]["content"],
        )
        self.assertEqual("visible", redacted["sample"]["output_items"][1]["content"])


if __name__ == "__main__":
    unittest.main()
