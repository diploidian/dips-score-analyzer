"""python -m unittest discover -s tests  (from the project folder, with src on the path)"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dips_score.scoring.score import Category, _card  # noqa: E402


def blackfathom_card(survival_weight: int = 10):
    """the real Blackfathom numbers: Cooldowns, Survival and Upkeep carry tips"""
    return _card([
        Category("Damage", 97, 20, "damage summary"),
        Category("Activity", 90, 15, "activity summary"),
        Category("Cooldowns", 23, 10, "cooldowns summary",
                 "Consecration sat ready 75s while you were free to use it "
                 "(about 8.4 casts, ~1,177 damage). Cast it as soon as it comes up."),
        Category("Interrupts", 0, 10, "interrupts summary", unavailable="no interrupt data"),
        Category("Casting", 80, 10, "casting summary"),
        Category("Movement", 100, 0, "movement summary"),
        Category("Survival", 53, survival_weight, "survival summary", "survival tip"),
        Category("Upkeep", 59, 5, "upkeep summary", "upkeep tip"),
        Category("Input", 100, 5, "input summary"),
        Category("Positioning", 39, 0, "positioning summary"),
    ], "dps")


class PointsLostTests(unittest.TestCase):
    def test_points_lost_blackfathom(self):
        card = blackfathom_card()
        lost = card.points_lost()
        self.assertEqual([c.name for c, _ in lost],
                         ["Cooldowns", "Survival", "Upkeep", "Casting", "Activity", "Damage"])
        self.assertEqual([round(p, 1) for _, p in lost], [10.3, 6.3, 2.7, 2.7, 2.0, 0.8])
        self.assertAlmostEqual(sum(p for _, p in lost), 100 - card.total, delta=0.05)

    def test_points_lost_excludes_info(self):
        names = {c.name for c, _ in blackfathom_card().points_lost()}
        self.assertFalse(names & {"Interrupts", "Movement", "Positioning", "Input"})

    def test_points_lost_follows_weights(self):
        self.assertEqual(blackfathom_card(survival_weight=20).points_lost()[0][0].name, "Survival")

    def test_tips_by_points_lost(self):
        tips = blackfathom_card().tips
        self.assertEqual(len(tips), 3)
        self.assertTrue(tips[0].startswith("Consecration"))
        self.assertEqual(tips[1:], ["survival tip", "upkeep tip"])


if __name__ == "__main__":
    unittest.main()
