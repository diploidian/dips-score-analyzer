"""python -m unittest discover -s tests  (from the project folder, with src on the path)"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dips_score.debrief import FightCell, build_view  # noqa: E402
from dips_score.scoring.score import Category, Scorecard, _card  # noqa: E402


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


BLACKFATHOM_FIGHTS = [
    ("0:42", 98), ("1:44", 90), ("2:33", 93), ("3:13", 81), ("3:47", 85), ("4:47", 83),
    ("6:25", 70), ("8:46", 78), ("9:58", 74), ("10:24", 100), ("10:35", 97), ("10:57", 86),
    ("11:23", 100), ("12:27", 93), ("13:08", 97), ("14:09", 97), ("14:35", 99), ("15:25", 99),
    ("15:54", 81), ("16:10", 91), ("17:15", 82), ("17:49", 91), ("18:19", 85), ("28:16", 90),
    ("29:10", 76), ("30:24", 99), ("32:25", 85), ("33:41", 73), ("34:22", 93), ("34:57", 89),
    ("35:30", 85), ("36:26", 92), ("37:07", 85), ("37:35", 94), ("38:47", 84), ("40:11", 92),
    ("41:05", 95), ("42:09", 89), ("42:48", 86), ("43:12", 89), ("43:57", 50), ("44:23", 82),
    ("45:09", 73), ("45:48", 85), ("47:52", 96), ("48:35", 83), ("48:53", 95), ("51:18", 94),
    ("52:05", 89), ("54:00", 74), ("54:28", 89), ("55:02", 73), ("55:26", 90), ("56:44", 97),
    ("58:31", 98), ("59:53", 80), ("60:21", 96), ("61:08", 87), ("61:35", 99), ("63:40", 84),
    ("64:26", 62), ("64:45", 98), ("67:44", 87), ("69:28", 53),
]


def cell(i, score, at="0:00"):
    return FightCell(i, at, "Trash", score, "-", False, False, 0.0, 1.0)


def review(scores):
    return build_view(blackfathom_card(), [cell(i, s) for i, s in enumerate(scores)], None, 0).review


class ViewTests(unittest.TestCase):
    def test_view_blackfathom(self):
        v = build_view(blackfathom_card(), [], 1.28, 1)
        self.assertEqual(v.fix.title, "Consecration sat ready 75s while you were free to use it")
        self.assertEqual(v.fix.points, 10.3)
        self.assertEqual(v.fix.damage, "~1,177 damage")
        self.assertEqual(v.verdict, "Strong damage — 128% of an even share — but Consecration sat ready 75s "
                                    "while you were free to use it and you died once.")
        self.assertEqual([m.name for m in v.measures], ["Damage", "Activity", "Abilities on time", "Casting"])
        self.assertEqual(v.earned, 75)

    def test_review_blackfathom(self):
        cells = [FightCell(i, t, "Trash", s, "-", False, False, 0.0, 1.0)
                 for i, (t, s) in enumerate(BLACKFATHOM_FIGHTS)]
        v = build_view(blackfathom_card(), cells, None, 0)
        self.assertEqual([cells[i].at for i in v.review], ["6:25", "43:57", "64:26", "69:28"])

    def test_review_long_run(self):
        scores = [95] * 70
        for i, s in ((2, 40), (65, 50), (30, 60), (68, 70)):
            scores[i] = s
        self.assertEqual(review(scores), [2, 30, 65, 68])

    def test_review_none(self):
        self.assertEqual(review([90, 95, 100]), [])

    def test_review_few(self):
        self.assertEqual(review([95, 80, 95, 60]), [1, 3])

    def test_view_empty_card(self):
        v = build_view(Scorecard(0, "-", note="no combat"), [], None, 0)
        self.assertEqual((v.total, v.grade, v.note, v.fix, v.measures, v.lost, v.review),
                         ("–", "-", "no combat", None, [], [], []))

    def test_verdict_variants(self):
        card = blackfathom_card()
        self.assertEqual(build_view(card, [], None, 3).verdict,
                         "Consecration sat ready 75s while you were free to use it and you died 3 times.")
        self.assertEqual(build_view(_card([Category("Damage", 100, 10, "x")], "dps"), [], None, 0).verdict,
                         "Nothing stands out — nice run.")

    def test_measures_healer(self):
        card = _card([Category("Group health", 90, 35, "a; b"), Category("Response", 80, 35, "c"),
                      Category("Efficiency", 70, 20, "d"), Category("Casting", 60, 10, "e")], "healer")
        ms = build_view(card, [], None, 0).measures
        self.assertEqual([m.name for m in ms], ["Group health", "Response", "Efficiency", "Casting"])
        self.assertEqual([m.ink for m in ms], ["m-surv", "m-cd", "m-dmg", "m-cast"])
        self.assertEqual((ms[0].reason, ms[0].on_target, ms[1].on_target), ("a", True, False))

    def test_measures_tank(self):
        card = _card([Category("Holding mobs", 90, 30, "a"), Category("Survival", 80, 25, "b"),
                      Category("Pickups", 70, 15, "c"), Category("Cooldowns", 60, 15, "d"),
                      Category("Casting", 50, 15, "e")], "tank")
        self.assertEqual([m.name for m in build_view(card, [], None, 0).measures],
                         ["Holding mobs", "Survival", "Pickups", "Abilities on time"])


if __name__ == "__main__":
    unittest.main()
