"""What attack power and spell power are worth by your own hits, how swings land, and the level a fight was fought at."""
import random
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dips_score.live.worth import hits, level_at, leveled, spells, swing  # noqa: E402
from dips_score.sheet_view import _spell_worth, _swings  # noqa: E402

T0 = datetime(2026, 11, 24, 12)


def fight(cells, day=0, **kw):
    return {"start": (T0 + timedelta(days=day)).isoformat(), "power": cells, **kw}


def cell(name, sid, ap, sp, values):
    return [name, sid, ap, sp, len(values), sum(values), sum(v * v for v in values)]


def swings(per_ap, low=0, width=36, aps=(600, 650, 700, 750), n=150, seed=1):
    r = random.Random(seed)
    return [cell("Melee", 0, ap, 14, [round(low + per_ap * ap + r.uniform(0, width)) for _ in range(n)]) for ap in aps]


class Swing(unittest.TestCase):
    def test_slope(self):
        got = swing([fight(swings(.24))], 139, 175)
        self.assertEqual(got["n"], 600)
        self.assertLess(abs(got["value"] - .24), 3 * got["error"])
        self.assertLess(got["error"], .02)

    def test_another_weapon_is_left_out(self):
        other = swings(.24, low=-30, width=80, seed=2)                      # its roll is another
        self.assertEqual(swing([fight(swings(.24)), fight(other, day=-1)], 139, 175)["n"], 600)
        mixed = swings(.24) + swings(.24, low=40, aps=(600, 650), seed=3)   # swapped within the day
        self.assertIsNone(swing([fight(mixed)], 139, 175))

    def test_nothing_is_guessed(self):
        self.assertIsNone(swing([fight(swings(.24, aps=(700,)))], 139, 175))      # one amount
        self.assertIsNone(swing([fight(swings(.24, n=10))], 139, 175))            # too few
        self.assertIsNone(swing([fight(swings(.01))], 139, 175))                  # not clear of its error
        for low, high in ((None, None), (0, 0), (175, 139)):
            self.assertIsNone(swing([fight(swings(.24))], low, high))
        self.assertIsNone(swing([{"start": T0.isoformat()}], 139, 175))           # saved before 0.22


class Spells(unittest.TestCase):
    LEVELS = [(0, 39)]
    CELLS = [cell("Judgement", 20281, 600, 11, [64, 65, 66] * 30), cell("Judgement", 20281, 600, 14, [66, 67, 68] * 30)]

    def test_slope(self):
        got, = spells([fight(self.CELLS)], self.LEVELS)
        self.assertEqual((got["name"], round(got["value"], 3), got["n"]), ("Judgement", .667, 180))
        row, = _spell_worth({"worth": [got], "stats": {}})
        self.assertEqual((row.name, row.value), ("Judgement", "+6.7"))
        self.assertIn("Measured over 180 hits, give or take 0.", row.note)

    def test_only_within_one_level(self):
        self.assertEqual(spells([fight(self.CELLS)], None), [])
        at = int(T0.timestamp())
        two = [fight(self.CELLS[:1], day=-1), fight(self.CELLS[1:])]
        self.assertEqual(spells(two, [(0, 38), (at - 3600, 39)]), [])
        self.assertEqual(len(spells(two, self.LEVELS)), 1)

    def test_attack_power_is_held_still(self):
        rise = [cell("Holy Strike", 1, ap, sp, [round(.2 * ap) + d for d in (-1, 0, 1)] * 20) for ap, sp in ((600, 11), (700, 14), (650, 14), (750, 11))]
        self.assertEqual([s["value"] for s in spells([fight(rise)], self.LEVELS)], [0.0])       # all of it attack power's
        together = [rise[0], rise[1]]
        self.assertEqual(spells([fight(together)], self.LEVELS), [])                            # can't be told apart

    def test_none_seen(self):
        flat = [cell("Consecration", 2, 600, sp, [10, 10, 10, 11] * 100) for sp in (11, 14)]
        got, = spells([fight(flat)], self.LEVELS)
        self.assertEqual((got["value"], _spell_worth({"worth": [got], "stats": {}})[0].value), (0.0, "0"))

    def test_not_measured_yet(self):
        row, = _spell_worth({"worth": [], "stats": {"spellpower": {"value": 14}}})
        self.assertEqual((row.name, row.value), ("Not measured yet", "–"))
        self.assertEqual(_spell_worth({"worth": [], "stats": {"spellpower": {"value": None}}}), [])


class Hits(unittest.TestCase):
    AUTO = {"landed": 90, "crits": 12, "glancing": 20, "misses": {"miss": 5, "dodge": 3, "parry": 2, "immune": 1},
            "dealt": {"glancing": [20, 1000, 2000], "plain": [58, 4350, 5800]}}

    def test_table(self):
        h = hits([{"auto": dict(self.AUTO)}] * 2 + [{"auto": None}, {}])
        self.assertEqual((h["n"], h["miss"], h["parry"], h["block"], h["glancing"], h["crit"]), (202, 10, 4, 0, 40, 24))
        self.assertAlmostEqual(h["glancing_cost"], 1 - .5 / .75)
        rows = _swings({"swings": h})
        self.assertEqual([(f.name, f.value) for f in rows], [("Missed", "5.0%"), ("Dodged", "3.0%"), ("Parried", "2.0%"),
                                                             ("Glancing", "19.8%"), ("Critical", "11.9%")])
        self.assertEqual((rows[0].note, rows[3].note), ("of 202 swings, against what you fought", "each does 33% less"))

    def test_too_few_or_older(self):
        self.assertIsNone(hits([{"auto": self.AUTO | {"landed": 20}}]))
        self.assertIsNone(hits([{"auto": {"speed": 3.4}}]))
        self.assertIsNone(hits([{"auto": {k: v for k, v in self.AUTO.items() if k != "dealt"}}])["glancing_cost"])
        self.assertEqual(_swings({"swings": None}), [])


class Levels(unittest.TestCase):
    def test_level_at(self):
        t = int(T0.timestamp())
        levels = [(t, 39), (t - 86400, 38)]
        at = lambda days: level_at(levels, (T0 + timedelta(days=days)).isoformat())  # noqa: E731
        self.assertEqual((at(-2), at(-1), at(-.5), at(0), at(3)), (None, 38, 38, 39, 39))
        self.assertIsNone(level_at(None, T0.isoformat()))
        old = [fight([], level=27)]
        self.assertEqual(leveled(old, {"levels": levels})[0]["level"], 39)
        self.assertIs(leveled(old, {"levels": []}), old)


if __name__ == "__main__":
    unittest.main()
