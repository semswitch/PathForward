import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathforward.agents.critic import Critic
from pathforward.agents.curator import Curator
from pathforward.agents.generator import Generator
from pathforward.agents.insights import ProgramInsightsAgent
from pathforward.agents.planner import Planner
from pathforward.agents.client import LLMResponse
from pathforward.agents.numeric import LocalNumericChecker
from pathforward.agents.types import AssessmentItem
from pathforward.iq import derivation as dv
from pathforward.iq import traversal
from pathforward.iq.seed import HERO_WORKER_ID, build_seed
from pathforward.skills import read_skill_file


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPECIALIST_SKILLS = {
    "pathforward": ("Orchestrator", "Never set `status=\"verified\"`", "ABSTAIN"),
    "pathforward-curate": ("Curator", "Never choose a skill outside the candidate set", "candidate_skill_ids"),
    "pathforward-assess": ("Generator Contract", "Never override the Evidence Gate"),
    "pathforward-critic": ("Critic Contract", "recommendation", "Never treat a Critic pass as a credential pass"),
    "pathforward-plan": ("Planner", "weekly capacity", "Never decide readiness"),
    "pathforward-insights": ("Program Insights", "Fabric-Live Contract", "Never fabricate a statistic"),
}


class _RecordingClient:
    def __init__(self, parsed):
        self.parsed = parsed
        self.last_instructions = ""
        self.last_input = ""

    def respond(self, instructions: str, input: str, *, previous_response_id=None, schema=None):
        self.last_instructions = instructions
        self.last_input = input
        return LLMResponse("recorded", "", self.parsed, previous_response_id,
                           retrieved_ref_ids=("corpus::AZ-204",))


class TestSkillFiles(unittest.TestCase):
    def test_pathforward_skill_uses_agentskills_shape(self):
        skill = read_skill_file(os.path.join(ROOT, "skills", "pathforward", "SKILL.md"))
        self.assertEqual(skill.name, "pathforward")
        self.assertIn("PathForward", skill.description)
        self.assertIn("Orchestrator", skill.instructions)
        self.assertIn("Never set `status=\"verified\"`", skill.instructions)
        self.assertIn("ABSTAIN", skill.instructions)

    def test_specialist_skill_files_use_agentskills_shape(self):
        for name, required in SPECIALIST_SKILLS.items():
            with self.subTest(skill=name):
                skill = read_skill_file(os.path.join(ROOT, "skills", name, "SKILL.md"))
                self.assertEqual(skill.name, name)
                self.assertIn("Azure AI Foundry Skills", skill.compatibility)
                for needle in required:
                    self.assertIn(needle, skill.instructions)

    def test_specialist_skill_instructions_are_loaded_by_agents(self):
        onto = build_seed()
        edges = dv.build_all_edges(onto)
        worker = onto.workers[HERO_WORKER_ID]
        role = onto.roles[worker.target_role_id]
        driving = traversal.cert_gap_edges(worker, onto, edges)[0]
        skill = onto.skills[driving.target_id]
        marker = "SPECIALIST_RUNTIME_MARKER"

        curator_client = _RecordingClient({"ranking": [skill.id], "rationale": {skill.id: "because"}})
        Curator(curator_client, skill_instructions=marker).curate(worker, role, onto)
        self.assertNotIn("Loaded Foundry Skill", curator_client.last_instructions)
        self.assertIn(marker, curator_client.last_instructions)

        generator_client = _RecordingClient({
            "stem": "What is checked?",
            "options": ["A", "B"],
            "answer_index": 0,
            "cited_ref_ids": ["corpus::AZ-204"],
            "numeric_claim": None,
        })
        Generator(generator_client, skill_instructions=marker).generate(
            driving, skill, ("corpus::AZ-204",), attempt=1)
        self.assertNotIn("Loaded Foundry Skill", generator_client.last_instructions)
        self.assertIn(marker, generator_client.last_instructions)

        item = AssessmentItem(
            id="item-1", targeted_skill_id=skill.id, driving_edge_id=driving.id,
            stem="What is checked?", options=("A", "B"), answer_index=0,
            cited_ref_ids=("corpus::AZ-204",), retrieved_ref_ids=("corpus::AZ-204",),
            numeric_claim=None, attempt=1,
        )
        critic_client = _RecordingClient({
            "recommendation": "pass",
            "concerns": [],
            "advisory_notes": "ok",
        })
        Critic(critic_client, skill_instructions=marker).review(
            item, ("corpus::AZ-204",), skill, driving)
        self.assertNotIn("Loaded Foundry Skill", critic_client.last_instructions)
        self.assertIn(marker, critic_client.last_instructions)

        planner_client = _RecordingClient({
            "sequence": [skill.id],
            "weekly_hours": 1,
            "accessibility_adaptations": [],
            "rationale": "ok",
        })
        Planner(planner_client, LocalNumericChecker(), skill_instructions=marker).plan(
            worker, (skill.id,), onto)
        self.assertNotIn("Loaded Foundry Skill", planner_client.last_instructions)
        self.assertIn(marker, planner_client.last_instructions)

        insights_client = _RecordingClient({"narrative": "ok"})
        ProgramInsightsAgent(insights_client, skill_instructions=marker).analyze(worker, role, onto)
        self.assertNotIn("Loaded Foundry Skill", insights_client.last_instructions)
        self.assertIn(marker, insights_client.last_instructions)

    def test_skill_file_requires_front_matter(self):
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as f:
            f.write("# Missing front matter\n")
            path = f.name
        try:
            with self.assertRaises(ValueError):
                read_skill_file(path)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
