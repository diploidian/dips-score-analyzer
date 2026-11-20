"""Habit cards and session numbers, from hand-made fight dicts; the Habits page's view of them (literals from the live
fight store); and the page itself when PyQt6 is there:
PYTHONPATH=<folder with PyQt6> python -m unittest discover -s tests"""
import importlib.util
import os
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dips_score.habits_view import build_habits  # noqa: E402
from dips_score.live.habits import habits  # noqa: E402

HAVE_QT = importlib.util.find_spec("PyQt6") is not None
T0 = datetime(2026, 11, 17, 12, 0, 0)


def fight(i, me="A", eff=0.8, own=("Fort",), ptype=1, mana=0.9, **kw):
    start = T0 + timedelta(minutes=2 * i)
    f = {"me": me, "me_name": me, "start": start.isoformat(), "end": (start + timedelta(seconds=30)).isoformat(),
         "duration": 30, "result": "killed", "efficiency": eff, "healing_role": False, "cooldowns": [], "failed": [],
         "pull": {"since_last": 90, "buffs": list(own), "own": list(own), "rest": 0},
         "resource": {"start": mana, "start_hp": 1.0, "type": ptype}}
    f.update(kw)
    return f


def titles(h):
    return {c["title"]: c["kind"] for c in h["cards"]}


class Habits(unittest.TestCase):
    def test_trend_up_is_keep_and_down_is_fix(self):
        up = habits([fight(i, eff=0.6 if i < 20 else 0.8) for i in range(40)])
        self.assertEqual(titles(up)["Efficiency is improving"], "keep")
        down = habits([fight(i, eff=0.9 if i < 20 else 0.7) for i in range(40)])
        self.assertEqual(titles(down)["Efficiency is dropping"], "fix")

    def test_pull_buff_missed_sometimes(self):
        fs = [fight(i, own=() if i == 3 else ("Fort",)) for i in range(10)]
        h = habits(fs)
        self.assertEqual(titles(h)["Pulling without Fort"], "fix")
        self.assertEqual(h["cards"][0]["kind"], "fix")           # fixes come first

    def test_old_and_new_pull_buffs_mixed(self):
        old = [fight(i, pull={"since_last": 1, "buffs": ["Fort", "Party Buff"]}) for i in range(6)]
        new = [fight(6 + i) for i in range(6)]
        self.assertNotIn("Pulling without Party Buff", titles(habits(old + new)))

    def test_mana_card_only_for_mana(self):
        self.assertNotIn("Start fights with more mana", titles(habits([fight(i, ptype=1, mana=0.2) for i in range(5)])))
        self.assertEqual(titles(habits([fight(i, ptype=0, mana=0.2) for i in range(5)]))
                         ["Start fights with more mana"], "build")

    def test_only_the_newest_character(self):
        fs = [fight(0, me="B", ptype=0, mana=0.1), fight(1, me="A"), fight(2, me="A")]
        h = habits(fs)
        self.assertEqual((h["name"], h["fights"], h["session"]["fights"]), ("A", 2, 2))

    def test_missed_casts_in_the_cooldown_card(self):
        row = {"name": "Judgement", "cd": 10, "lost": 200, "missed": 3, "counted": 2}    # one miss excused
        fs = [fight(i, cooldowns=[row]) for i in range(2)] + [fight(2, cooldowns=[{"name": "Judgement", "cd": 10, "lost": 100}])]
        card = next(c for c in habits(fs)["cards"] if c["title"] == "Judgement left unused")
        self.assertEqual(card["detail"], "About 500 damage lost, 4 casts missed in 3 fights")

    def test_empty(self):
        h = habits([])
        self.assertEqual((h["cards"], h["session"], h["trend"]), ([], None, []))

    def test_skill_against_gear(self):
        old = [fight(i, eff=0.80, dps=100.0, gear=28, level=32) for i in range(20)]
        new = [fight(20 + i, eff=0.84, dps=120.0, gear=31, level=33) for i in range(20)]
        card = next(c for c in habits(old + new)["cards"] if c["title"] == "DPS up 20%")
        self.assertEqual(card["kind"], "keep")
        self.assertEqual(card["detail"], "About 5% from playing better (efficiency 80% to 84%), the rest (+14%) from "
                                         "gear, level and what you fought (gear 28 to 31, level 32 to 33).")
        same_gear = [fight(20 + i, eff=0.70, dps=90.0, gear=28) for i in range(20)]
        card = next(c for c in habits(old + same_gear)["cards"] if c["title"] == "DPS down 10%")
        self.assertEqual(card["kind"], "fix")
        self.assertTrue(card["detail"].endswith("from gear, level and what you fought."), card["detail"])
        small = [fight(20 + i, eff=0.80, dps=104.0) for i in range(20)]
        self.assertFalse([t for t in titles(habits(old + small)) if t.startswith("DPS ")])

    def test_trend_points(self):
        fs = [fight(i, eff=0.5 + i / 100, level=32 + (i >= 3), gear=30 if i else None) for i in range(5)]
        fs.append(fight(5, healing_role=True))
        self.assertEqual(habits(fs)["trend"], [{"efficiency": 0.5 + i / 100, "level": 32 + (i >= 3),
                                                "gear": 30 if i else None} for i in range(5)])

    def test_no_damage_fights_left_out_of_damage_play(self):
        fs = [fight(i, eff=0.9, damage=500) for i in range(10)] + [fight(10 + i, eff=0.0, damage=0) for i in range(5)]
        h = habits(fs)
        self.assertEqual(len(h["trend"]), 10)
        self.assertEqual(titles(h)["Efficiency is steady"], "keep")
        self.assertEqual(h["fights"], 15)                         # still counted for habits around the fight

    def test_defensive_card(self):
        low = lambda *names: {"t": 5, "hp": 0.1, "hits": [], "unused": list(names)}  # noqa: E731
        fs = [fight(0, danger=low("Divine Protection")), fight(1, danger=low("Lay on Hands", "Divine Protection")),
              fight(2, danger=low()), fight(3)]
        card = next(c for c in habits(fs)["cards"] if c["title"] == "Use a defensive when low")
        self.assertEqual((card["kind"], card["detail"]), ("build", "2 close calls with Divine Protection ready"))
        self.assertNotIn("Use a defensive when low", titles(habits([fight(0, danger=low())])))

    def test_cost_only_on_the_cooldown_card(self):
        row = {"name": "Judgement", "cd": 10, "lost": 150.5, "missed": 1, "counted": 1}
        h = habits([fight(i, cooldowns=[row], own=() if i == 3 else ("Fort",)) for i in range(6)])
        costs = {c["title"]: c["cost"] for c in h["cards"]}
        self.assertEqual(costs.pop("Judgement left unused"), 903.0)
        self.assertTrue(costs and all(v is None for v in costs.values()), costs)

    def test_card_figures(self):
        """each card's figures beside its words, so the page never reads the sentences"""
        cards = {c["title"]: c for c in habits([fight(i, eff=0.9 if i < 20 else 0.7) for i in range(40)])["cards"]}
        down = cards["Efficiency is dropping"]
        self.assertAlmostEqual(down["recent"], 70.0)
        self.assertAlmostEqual(down["before"], 90.0)
        self.assertEqual(set(cards["No deaths"]), {"kind", "title", "detail", "cost"})
        steady = next(c for c in habits([fight(i) for i in range(6)])["cards"] if c["title"] == "Efficiency is steady")
        self.assertEqual((round(steady["recent"], 6), steady["before"]), (80.0, None))
        row = {"name": "Judgement", "cd": 10, "lost": 200, "missed": 3, "counted": 2}
        fs = [fight(i, cooldowns=[row]) for i in range(2)] + [fight(2, cooldowns=[{"name": "Judgement", "cd": 10,
                                                                                    "lost": 100}])]
        card = next(c for c in habits(fs)["cards"] if c["title"] == "Judgement left unused")
        self.assertEqual((card["cost"], card["fights"], card["missed"]), (500, 3, 4))
        old = [fight(i, eff=0.80, dps=100.0) for i in range(20)]
        new = [fight(20 + i, eff=0.84, dps=120.0) for i in range(20)]
        card = next(c for c in habits(old + new)["cards"] if c["title"] == "DPS up 20%")
        for key, want in (("dps_change", 0.2), ("play", 0.05), ("rest", 1.2 / 1.05 - 1)):
            self.assertAlmostEqual(card[key], want)


# the live store's last 40 fights (Bao Kahn, 18 Nov), as live.habits.habits() sums them up
EFF = [1.0, 0.964, 0.952, 0.894, 0.845, 0.998, 0.734, 0.874, 0.967, 0.754, 1.0, 0.898, 0.766, 0.908, 0.756, 0.892,
       0.742, 0.681, 0.78, 0.783, 0.839, 0.85, 0.83, 0.667, 0.789, 0.872, 0.763, 0.921, 0.932, 0.703, 0.839, 0.824,
       0.665, 0.87, 0.545, 0.605, 0.736, 0.488]
REAL = {
    "name": "Bao Kahn", "level": 23, "fights": 40,
    "session": {"fights": 43, "kills": 37, "kills_per_hour": 24.725715337962658, "avg_gap": 46.004238095238094,
                "avg_rest": 0.0, "avg_start_hp": 0.9615988986826519, "avg_start_mana": 0.9483409095778407},
    "char": {"class": "PALADIN", "race": "Undead", "level": 31, "spec": None, "gear": 27},
    "trend": [{"efficiency": e, "level": 23, "gear": None} for e in EFF],
    "cards": [
        {"kind": "fix", "title": "Efficiency is dropping",
         "detail": "Last 20 fights 76.5% efficiency vs 86.8% in the 18 before", "cost": None,
         "recent": 76.50344372678967, "before": 86.80858687006481},
        {"kind": "fix", "title": "Consecration left unused",
         "detail": "About 7,298 damage lost, 76 casts missed in 26 fights", "cost": 7297.741291070065,
         "fights": 26, "missed": 76},
        {"kind": "fix", "title": "Swings going missing", "detail": "3.6 swings lost per minute (152 in 37 fights)",
         "cost": None},
        {"kind": "fix", "title": "DPS down 5%",
         "detail": "About 12% from playing worse (efficiency 87% to 77%), the rest (+8%) from gear, level and what you "
                   "fought.", "cost": None,
         "dps_change": -0.05199648609954055, "play": -0.11871110353057468, "rest": 0.07570118913139923},
        {"kind": "fix", "title": "Failed casts: Out of range", "detail": "15 times in 40 fights (0.4 per fight)",
         "cost": None},
        {"kind": "fix", "title": "Dying in fights", "detail": "Died in 1 of 40 fights", "cost": None},
        {"kind": "build", "title": "Use a defensive when low", "detail": "2 close calls with Divine Protection ready",
         "cost": None},
        {"kind": "build", "title": "Spells you never use",
         "detail": "You know Exorcism and have not cast it in your last 40 fights", "cost": None},
        {"kind": "build", "title": "Gear slots to fill", "detail": "Empty gear slots: trinket 1, trinket 2",
         "cost": None},
        {"kind": "build", "title": "Gear nearly broken",
         "detail": "Lowest durability under 20% in 19 of your last 24 fights (worst 7%)", "cost": None},
        {"kind": "keep", "title": "Always pulling with Retribution Aura", "detail": "Present at pull in all 40 fights",
         "cost": None}]}


class HabitsViewTests(unittest.TestCase):
    def test_habits_view_real(self):
        v = build_habits(REAL)
        self.assertEqual((v.title, v.meta), ("Bao Kahn", "level 31 Undead Paladin · gear 27 · last 40 fights"))
        self.assertEqual((round(v.recent, 1), round(v.before, 1), v.split_at), (76.5, 86.8, 18))
        self.assertEqual((v.caption, v.chip), ("efficiency, last 20 fights", "−10 pts vs the 18 before"))
        self.assertEqual(v.fix, ("Consecration left unused", "about 7,298 damage", "76 casts missed in 26 fights"))
        self.assertEqual(v.verdict, "Efficiency is dropping, and most of it is play, not gear: Consecration left "
                                    "unused cost about 7,298 damage across 26 fights.")
        self.assertEqual(v.figures, [("43", "fights · 37 kills"), ("25", "kills / hour"), ("46s", "avg gap"),
                                     ("0s", "avg rest"), ("96% / 95%", "start health / mana")])
        self.assertEqual(v.trend, [e * 100 for e in EFF])
        self.assertEqual((v.levels, v.gear_changes), ([], []))
        self.assertEqual([(name, len(rows)) for name, rows in v.groups], [("Fix", 6), ("Build", 4), ("Keep", 1)])
        self.assertEqual([t for _, rows in v.groups for t, _, plate in rows if plate], ["Consecration left unused"])
        self.assertEqual(v.groups[2][1], [("Always pulling with Retribution Aura", "Present at pull in all 40 fights",
                                           False)])

    def test_verdict_and_plate_without_a_cost(self):
        cards = [c for c in REAL["cards"] if c["title"] not in ("Consecration left unused", "DPS down 5%")]
        v = build_habits(dict(REAL, cards=cards, char=None))
        self.assertEqual(v.meta, "level 23 · last 40 fights")
        self.assertEqual(v.fix, ("Swings going missing", None, "3.6 swings lost per minute (152 in 37 fights)"))
        self.assertEqual(v.verdict, "Efficiency is dropping. Swings going missing: 3.6 swings lost per minute (152 in "
                                    "37 fights).")
        only_eff = [c for c in cards if c["kind"] != "fix" or c["title"].startswith("Efficiency")]
        v = build_habits(dict(REAL, cards=only_eff))      # the efficiency card is the hero's, not a habit to fix
        self.assertEqual((v.fix, v.verdict), (None, "Efficiency is dropping."))
        gear_too = [c for c in REAL["cards"] if c["title"] != "DPS down 5%"] + [
            {"kind": "fix", "title": "DPS down 9%", "detail": "About 4% from playing worse (efficiency 87% to 84%), "
             "the rest (-5%) from gear, level and what you fought.", "cost": None,
             "dps_change": -0.09, "play": -0.04, "rest": -0.05}]      # gear outweighs play
        self.assertNotIn("most of it is play", build_habits(dict(REAL, cards=gear_too)).verdict)
        steady = [dict(c, title="Efficiency is steady", recent=85.0) if c["title"] == "Efficiency is dropping" else c
                  for c in REAL["cards"]]                               # within MOVE: no drop to explain
        self.assertTrue(build_habits(dict(REAL, cards=steady)).verdict.startswith("Efficiency is steady: Consecration"))
        once = [dict(c, fights=1, missed=0) if c["title"] == "Consecration left unused" else c for c in REAL["cards"]]
        v = build_habits(dict(REAL, cards=once))
        self.assertEqual(v.fix[2], "in 1 fight")
        self.assertTrue(v.verdict.endswith("cost about 7,298 damage across 1 fight."), v.verdict)

    def test_cards_without_figures(self):
        """older dicts, only words: what needs a card's figures is left out, never read from its sentence"""
        bare = [{k: c[k] for k in ("kind", "title", "detail", "cost")} for c in REAL["cards"]]
        v = build_habits(dict(REAL, cards=bare))
        self.assertEqual(v.fix, ("Consecration left unused", "about 7,298 damage", None))
        self.assertEqual(v.verdict, "Consecration left unused cost about 7,298 damage.")

    def test_trend_marks_and_a_short_before(self):
        trend = [{"efficiency": 0.8, "level": 30 + (i >= 10), "gear": 25 if i < 20 else 27} for i in range(24)]
        trend[3]["efficiency"] = None                   # an old save: left out
        v = build_habits(dict(REAL, trend=trend))
        self.assertEqual(len(v.trend), 23)
        self.assertEqual((v.levels, v.gear_changes), ([(9, 31)], [19]))
        self.assertEqual((v.before, v.split_at, v.chip), (None, None, None))       # 3 before: under TREND_MIN
        self.assertEqual(v.caption, "efficiency, last 20 fights")

    def test_habits_view_empty(self):
        v = build_habits(habits([]))
        self.assertEqual((v.title, v.meta, v.recent, v.fix, v.trend, v.figures, v.groups),
                         ("Habits", "", None, None, [], [], []))
        self.assertEqual(v.verdict, "Fights appear here once you have some.")
        row = {"name": "Judgement", "cd": 10, "lost": 200, "missed": 3, "counted": 2}
        v = build_habits(habits([fight(i, cooldowns=[row], result="you died" if i == 2 else "killed")
                                 for i in range(3)]))
        self.assertEqual((v.recent, v.before, v.chip, v.fix, v.trend, v.split_at), (None, None, None, None, [], None))
        self.assertEqual(v.verdict, "Efficiency shows here after 5 fights where you did damage (3 so far).")
        self.assertEqual(v.meta, "last 3 fights")
        self.assertEqual(v.figures[0], ("3", "fights · 2 kills"))
        self.assertEqual([(name, [t for t, _, plate in rows if not plate]) for name, rows in v.groups],
                         [("Fix", ["Judgement left unused", "Dying in fights"])])


@unittest.skipUnless(HAVE_QT, "needs PyQt6")
class HabitsPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_page_paints_and_opens_fights(self):
        from dips_score.ui.habitsview import HabitsPage
        page = HabitsPage()
        page.resize(1200, 900)
        opened = []
        page.open_fights.connect(lambda: opened.append(True))
        page.show_habits(REAL)
        self.assertEqual((page.page.title, page.hero.big, page.hero.chip),
                         ("Bao Kahn", "77", "−10 pts vs the 18 before"))
        self.assertEqual((page.plate.title, page.plate.price, page.plate.button.text()),
                         ("Consecration left unused", "about 7,298 damage", "Open Fights"))
        self.assertEqual(page.chart.view.split_at, 18)
        real_h = page.chart.heightForWidth(700)                         # no marks: no caption
        self.assertFalse(page.grab().isNull())
        page.plate.button.click()
        self.assertEqual(opened, [True])
        page.show_habits(dict(REAL, trend=[{"efficiency": 0.8, "level": 30 + (i >= 10), "gear": 25 + (i >= 16)}
                                           for i in range(22)]))    # level and gear marks, no before
        self.assertEqual((page.chart.view.levels, page.chart.view.gear_changes, page.hero.chip),
                         ([(10, 31)], [16], None))
        self.assertGreater(page.chart.heightForWidth(700), real_h)      # the marks' caption under the chart
        self.assertFalse(page.grab().isNull())
        page.show_habits(habits([fight(i) for i in range(3)]))      # too few: no plate, no chart
        self.assertTrue(page.plate.isHidden() and page.chart.isHidden())
        self.assertEqual(page.hero.big, "–")
        self.assertFalse(page.grab().isNull())
        page.show_habits(habits([]))
        self.assertFalse(page.empty.isHidden())
        self.assertTrue(page.hero.isHidden() and page.side.isHidden())
        self.assertFalse(page.grab().isNull())


if __name__ == "__main__":
    unittest.main()
