"""What attack power and spell power are worth by your own hits, how swings land, and the level a fight was fought at."""
import json
import random
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dips_score.live.worth import hits, level_at, leveled, spells, swing  # noqa: E402
from dips_score.config import Paths  # noqa: E402
from dips_score.live.history import History  # noqa: E402
from dips_score.live.profile import profile  # noqa: E402
from dips_score.live.summary import summarize  # noqa: E402
from dips_score.profile_view import _had, build_profile  # noqa: E402
from dips_score.sheet_view import _spell_worth, _swings  # noqa: E402
from dips_score.sources.combatlog import UnitInfo  # noqa: E402
from test_live import ME, MOB, bites, dmg, line, one_fight  # noqa: E402

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
        near = swings(.24, low=-30, width=40, n=400, seed=4)                # a little wider: with enough swings it shows
        self.assertEqual(swing([fight(swings(.24)), fight(near, day=-1)], 139, 175)["n"], 600)
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

    def test_only_within_one_day(self):
        self.assertEqual(spells([fight(self.CELLS[:1], day=-1), fight(self.CELLS[1:])], self.LEVELS), [])

    def test_only_within_one_level(self):
        self.assertEqual(spells([fight(self.CELLS)], None), [])
        at = int(T0.timestamp())
        two = [fight(self.CELLS[:1]), fight(self.CELLS[1:], day=.2)]
        self.assertEqual(spells(two, [(0, 38), (at + 3600, 39)]), [])
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
        self.assertEqual(len(_spell_worth({"worth": [], "stats": {"spellpower": {"value": None}}})), 1)        # hidden
        self.assertEqual(_spell_worth({"worth": [], "stats": {"spellpower": {"value": 0}}}), [])
        self.assertEqual(_spell_worth({"worth": [], "stats": {}}), [])


class Hits(unittest.TestCase):
    AUTO = {"landed": 90, "crits": 12, "glancing": 20, "misses": {"miss": 5, "dodge": 3, "parry": 2, "immune": 1},
            "glance": [20, 300.0, 400.0]}

    def test_table(self):
        h = hits([{"auto": dict(self.AUTO)}] * 2 + [{"auto": None}, {}])
        self.assertEqual((h["n"], h["miss"], h["parry"], h["block"], h["glancing"], h["crit"]), (202, 10, 4, 0, 40, 24))
        self.assertAlmostEqual(h["glancing_cost"], .25)
        rows = _swings({"swings": h})
        self.assertEqual([(f.name, f.value) for f in rows], [("Missed", "5.0%"), ("Dodged", "3.0%"), ("Parried", "2.0%"),
                                                             ("Glancing", "19.8%"), ("Critical", "11.9%")])
        self.assertEqual((rows[0].note, rows[3].note), ("of 202 swings, against what you fought", "each does 25% less"))

    def test_too_few_or_older(self):
        self.assertIsNone(hits([{"auto": self.AUTO | {"landed": 20}}]))
        self.assertIsNone(hits([{"auto": {"speed": 3.4}}]))
        self.assertIsNone(hits([{"auto": {k: v for k, v in self.AUTO.items() if k != "glance"}}])["glancing_cost"])
        self.assertEqual(_swings({"swings": None}), [])


class Saved(unittest.TestCase):
    def test_a_fight(self):
        """the base damage, at your own last block's attack and spell power; not under Seal of the Crusader"""
        swing = lambda t, amount, base, glancing="nil": line(t, f"SWING_DAMAGE,{ME},{MOB},{amount},{base},-1,1,0,0,0,nil,{glancing},nil")  # noqa: E731
        seal = lambda t, ev: line(t, f'SPELL_AURA_{ev},{ME},{ME},1,"Seal of the Crusader",0x2,BUFF')  # noqa: E731
        tr, f = one_fight([dmg(0, ME, MOB, 7, "Smite", 50), swing(1, 70, 100), swing(2, 40, 110, "1"), dmg(3, ME, MOB, 7, "Smite", 60),
                           seal(4, "APPLIED"), swing(5, 50, 70), seal(6, "REMOVED"), swing(7, 70, 100), *bites()])
        for e in f.events:
            if e.event == "SWING_DAMAGE" and e.src == tr.me:
                e.info = UnitInfo(tr.me, 900, 1000, 0, 80, 100, 0.0, 0.0, 0, 0.0, 27, 0, 0, 600, 14, 940)
        s = summarize(f, tr.me, tr.me_name, {}, [])
        self.assertEqual(sorted(s["power"], key=str), [["Melee", 0, 600, 14, 3, 310, 32100], ["Smite", 7, 600, 14, 1, 60, 3600]])
        self.assertEqual((s["stats"], s["ilvl"]), ({"sp": 14, "armor": 940, "hp": 1000, "mana": 100}, 27))
        n, did, plain = s["auto"]["glance"]
        self.assertEqual((n, round(1 - did / plain, 4)), (1, round(1 - (40 / 110) / (190 / 270), 4)))

    def test_the_log_s_level_was_not_one(self):
        saved = [{"id": "1", "start": "2026-11-20", "level": 27}, 3, {"id": "2", "start": "2026-11-21", "ilvl": 28}]
        with tempfile.TemporaryDirectory() as d, patch.dict("os.environ", {"APPDATA": d}):
            h = History(Paths(Path(d)))
            h.file.parent.mkdir(parents=True, exist_ok=True)
            h.file.write_text("\n".join(map(json.dumps, saved)), encoding="utf-8")
            h.load()
            self.assertEqual([(f.get("level"), f["ilvl"]) for f in h.fights], [(None, 27), (None, 28)])

    def test_a_block(self):
        self.assertEqual(_had({}), "stats not recorded")
        self.assertEqual(_had({"time": {"type": "Errant"}}), "Errant · stats not recorded")
        self.assertEqual(_had({"time": {"type": None}, "stats": {"gear": 31.0, "sp": 14, "hp": 1697.0}}),
                         "gear 31 · 14 spell power · 1,697 health")

    def test_the_time_bar_needs_no_fights(self):
        f = {"me": "A", "me_name": "A", "start": T0.isoformat(), "duration": 5, "kind": "World", "result": "killed", "damage": 5,
             "healing_role": False, "abilities": [], "stats": {"armor": 940}}
        day = lambda n: (T0 - timedelta(days=n)).date().isoformat()  # noqa: E731
        char = {"guid": "A", "time": {day(40): {}, day(1): {"trade": 36000}, day(20): {"hunt": 36000}}}
        p = profile([f], char, {}, [], T0)
        self.assertEqual((p["before"], p["now"]["stats"]), (None, {"armor": 940}))
        v = build_profile(p, [])
        self.assertTrue(v.need)
        self.assertEqual((v.time.type, v.time.parts[0].chip), ("Merchant Prince", "+100 pts vs the 15 days before"))


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
