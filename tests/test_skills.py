import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathforward.skills import read_skill_file


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestSkillFiles(unittest.TestCase):
    def test_pathforward_skill_uses_agentskills_shape(self):
        skill = read_skill_file(os.path.join(ROOT, "skills", "pathforward", "SKILL.md"))
        self.assertEqual(skill.name, "pathforward")
        self.assertIn("PathForward", skill.description)
        self.assertIn("Orchestrator", skill.instructions)
        self.assertIn("Never set `status=\"verified\"`", skill.instructions)
        self.assertIn("ABSTAIN", skill.instructions)

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
