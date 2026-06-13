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
        self.assertEqual(
            "{{sample.output}}",
            by_name["pathforward_no_token_exposure"]["data_mapping"]["output_items"],
        )

    def test_testing_criteria_pin_custom_evaluator_versions(self):
        criteria = runner._testing_criteria({
            "evaluators": ["pathforward_no_token_exposure"],
        }, "reasoning", {"pathforward_no_token_exposure": "11"})

        self.assertEqual("11", criteria[0]["evaluator_version"])

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

    def test_latest_agent_version_uses_highest_numeric_version(self):
        class Agents:
            @staticmethod
            def list_versions(agent_name):
                self.assertEqual("pathforward-orchestrator", agent_name)
                return [
                    type("Agent", (), {"version": "9"})(),
                    type("Agent", (), {"version": "11"})(),
                    type("Agent", (), {"version": "10"})(),
                ]

        project = type("Project", (), {"agents": Agents()})()

        self.assertEqual("11", runner._latest_agent_version(project, "pathforward-orchestrator"))

    def test_latest_evaluator_version_uses_highest_numeric_version(self):
        class Evaluators:
            @staticmethod
            def list_versions(name):
                self.assertEqual("pathforward_no_token_exposure", name)
                return [
                    type("Evaluator", (), {"version": "8"})(),
                    type("Evaluator", (), {"version": "11"})(),
                    type("Evaluator", (), {"version": "10"})(),
                ]

        project = type("Project", (), {"beta": type("Beta", (), {"evaluators": Evaluators()})()})()

        self.assertEqual("11", runner._latest_evaluator_version(project, "pathforward_no_token_exposure"))


if __name__ == "__main__":
    unittest.main()
