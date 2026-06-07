"""Voice/text parity (FB5): the same answer scores identically through either modality."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathforward.agents.types import AssessmentItem
from pathforward.scorer import FinalTurnTranscript, score


def _item():
    return AssessmentItem(
        id="item::x", targeted_skill_id="S01", driving_edge_id="certgap::EMP-001::S01",
        stem="total hours?", options=("20 hours", "24 hours", "30 hours"),
        answer_index=1, cited_ref_ids=("requires::R-CLOUD::S01",), numeric_claim="18+6==24",
    )


class TestScorerParity(unittest.TestCase):
    def test_voice_and_text_score_identically(self):
        item = _item()
        voice = FinalTurnTranscript("voice", ("...barge-in...", "24 hours"), "24 hours",
                                    ("requires::R-CLOUD::S01",))
        text = FinalTurnTranscript("text", ("24 hours",), "24 hours",
                                   ("requires::R-CLOUD::S01",))
        sv, st = score(voice, item), score(text, item)
        self.assertEqual(sv.passed, st.passed)
        self.assertEqual(sv.correct, st.correct)
        self.assertEqual(sv.cited_source_ids, st.cited_source_ids)
        self.assertTrue(sv.passed)

    def test_uncited_answer_does_not_pass(self):
        item = _item()
        t = FinalTurnTranscript("text", ("24 hours",), "24 hours", ())  # no citation
        self.assertFalse(score(t, item).passed)

    def test_wrong_answer_is_incorrect(self):
        item = _item()
        t = FinalTurnTranscript("text", ("30 hours",), "30 hours", ("requires::R-CLOUD::S01",))
        s = score(t, item)
        self.assertFalse(s.correct)
        self.assertFalse(s.passed)


if __name__ == "__main__":
    unittest.main()
