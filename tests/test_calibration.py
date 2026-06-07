"""Cold-start calibration: difficulty = p-value, discrimination = point-biserial."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathforward.agents.calibration import cold_start_calibrate


class TestCalibration(unittest.TestCase):
    def test_difficulty_and_discrimination(self):
        # Two items, two high scorers (L1,L2) and two low scorers (L3,L4).
        responses = []
        for learner, correct in [("L1", True), ("L2", True), ("L3", False), ("L4", False)]:
            responses.append({"learner_id": learner, "item_id": "X", "correct": correct})
            responses.append({"learner_id": learner, "item_id": "Y", "correct": correct})
        stats = cold_start_calibrate(responses)
        self.assertEqual(stats["X"]["difficulty"], 0.5)        # 2 of 4 correct
        self.assertEqual(stats["X"]["discrimination"], 1.0)    # perfectly separates high/low
        self.assertEqual(stats["X"]["label"], "estimated (cold-start)")

    def test_difficulty_bounds(self):
        responses = [{"learner_id": f"L{i}", "item_id": "Z", "correct": True} for i in range(5)]
        stats = cold_start_calibrate(responses)
        self.assertEqual(stats["Z"]["difficulty"], 1.0)
        self.assertEqual(stats["Z"]["discrimination"], 0.0)    # no variance -> 0


if __name__ == "__main__":
    unittest.main()
