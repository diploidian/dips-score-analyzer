"""What the Fight page shows (dips_score/fight_view.py), on the real "Blackfathom Oracle +3" fight (copied in as
literals from the live fight store) and on bare dicts; the page and the fight list themselves when PyQt6 is there:
PYTHONPATH=<folder with PyQt6> python -m unittest discover -s tests"""
import importlib.util
import os
import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dips_score.fight_view import build_fight, list_row, run_window  # noqa: E402

HAVE_QT = importlib.util.find_spec("PyQt6") is not None

# Wed 18 Nov 23:38:49, Blackfathom Deeps, as live/summary.py saved it (buffs and pull left out)
ORACLE = {
    "id": "20261118233849824000", "start": "2026-11-18T23:38:49.824000", "end": "2026-11-18T23:40:42.282000",
    "duration": 112.458, "me": "Player-6932-00C0878F", "me_name": "Bao Kahn", "kind": "PvP",
    "zone": "Blackfathom Deeps", "target": "Blackfathom Oracle", "more": 3, "result": "they got away",
    "damage": 2583, "dps": 22.968574934642266, "healing": 53, "overheal": 84, "taken": 433,
    "lowest_hp": 0.8632218844984803, "potential": 5288.2917175917255, "efficiency": 0.48843750268305763,
    "healing_role": False, "verdict": "12 swings lost while not attacking, about 1,538 damage.", "best_before": None,
    "good": ["1 dispel", "Never below 86% health"],
    "improve": ["12 swings lost while not attacking ≈ 1,538 damage",
                "Judgement sat ready 64.6 s while you were free ≈ 614 damage",
                "Consecration sat ready 72.8 s while you were free ≈ 343 damage",
                "Holy Strike sat ready 38.6 s while you were free ≈ 211 damage",
                "Holy Strike: Out of range ×2"],
    "danger": None,
    "abilities": [
        {"name": "Melee", "casts": 0, "hits": 13, "crits": 1, "miss": 0, "damage": 1666, "avg": 128.15384615384616,
         "share": 0.6449864498644986},
        {"name": "Seal of Command", "casts": 4, "hits": 4, "crits": 0, "miss": 0, "damage": 416, "avg": 104.0,
         "share": 0.1610530391018196},
        {"name": "Holy Strike", "casts": 4, "hits": 4, "crits": 0, "miss": 0, "damage": 218, "avg": 54.5,
         "share": 0.08439798683701123},
        {"name": "Judgement of Command", "casts": 0, "hits": 2, "crits": 0, "miss": 0, "damage": 152, "avg": 76.0,
         "share": 0.05884630274874177},
        {"name": "Touch of the Grave", "casts": 0, "hits": 2, "crits": 0, "miss": 0, "damage": 131, "avg": 65.5,
         "share": 0.05071622144792876},
        {"name": "Seal of the Crusader", "casts": 1, "hits": 0, "crits": 0, "miss": 0, "damage": 0, "avg": 0,
         "share": 0.0},
        {"name": "Judgement", "casts": 2, "hits": 0, "crits": 0, "miss": 0, "damage": 0, "avg": 0, "share": 0.0},
        {"name": "Purify", "casts": 1, "hits": 0, "crits": 0, "miss": 0, "damage": 0, "avg": 0, "share": 0.0}],
    "cooldowns": [
        {"name": "Judgement", "cd": 8.0, "used": 2, "ready": 96.458, "free": 64.6000000000006,
         "excused": {"nothing to hit": 13.9, "healing": 13.0, "just came up": 3.2, "fight ending": 2.0},
         "lost": 613.7000000000057, "possible": 14, "missed": 12, "counted": 8},
        {"name": "Consecration", "cd": 8.91, "used": 0, "ready": 112.458, "free": 72.80000000000014,
         "excused": {"nothing to hit": 23.6, "healing": 13.0, "fight ending": 2.0, "just came up": 1.1},
         "lost": 343.1649831649838, "possible": 13, "missed": 13, "counted": 8},
        {"name": "Holy Strike", "cd": 9.99, "used": 4, "ready": 72.498, "free": 38.60000000000028,
         "excused": {"nothing to hit": 13.9, "healing": 12.9, "just came up": 5.3, "fight ending": 2.0},
         "lost": 210.5805805805821, "possible": 12, "missed": 8, "counted": 4}],
    "auto": {"swings": 13, "speed": 3.4390000000000036, "lost": 12, "lost_casting": 0, "lost_other": 12,
             "damage_lost": 1537.8461538461538},
    "idle": {"total": 93.844, "with_resource": 69.259, "out_of_resource": 0.0, "moving": 24.585, "lost": 0.0,
             "filler": False},
    "group": {"size": 5, "names": ["Piraña Segundo", "Shizuka Tsuruta", "Anaruz Lightborne", "Evilguy Verybad"],
              "damage_share": 0.25470860861847944, "damage_rank": 3, "heal_share": 0.10685483870967742,
              "heal_rank": 4,
              "members": [{"name": "Piraña Segundo", "damage": 4518, "healing": 177},
                          {"name": "Shizuka Tsuruta", "damage": 0, "healing": 198},
                          {"name": "Anaruz Lightborne", "damage": 0, "healing": 68},
                          {"name": "Evilguy Verybad", "damage": 3040, "healing": 0}],
              "deaths": []},
    "failed": [{"spell": "Holy Strike", "reason": "Out of range", "count": 2},
               {"spell": "Holy Strike", "reason": "Not yet recovered", "count": 1}],
    "resource": {"start": 0.9260476581758422, "end": 1.0, "start_hp": 1.0, "type": 0}, "level": 23,
    "interrupts": 0, "dispels": 1,
}
BARE = {"start": "2026-11-18T22:22:52.938000", "duration": 20.4, "damage": 0, "dps": 0.0, "taken": 120,
        "healing": 0, "result": "they got away", "kind": "Dungeon", "target": "Aku'mai"}


class FightViewTests(unittest.TestCase):
    def test_fight_view_oracle(self):
        v = build_fight(ORACLE)
        self.assertEqual((v.name, v.when, v.zone, v.kind, v.duration, v.result),
                         ("Blackfathom Oracle +3 more", "Wed 18 Nov 23:38:49", "Blackfathom Deeps", "PvP", "1:52",
                          "they got away"))
        self.assertEqual((v.big, v.unit, v.caption), ("49", "%", "of the damage that was possible"))
        self.assertAlmostEqual(v.efficiency, 0.4884, places=4)
        self.assertEqual(v.verdict, "12 swings lost while not attacking, about 1,538 damage.")
        self.assertEqual(v.figures, [("2,583", "damage"), ("23", "DPS"), ("433", "taken"), ("53", "healing")])
        self.assertEqual([(label, detail) for label, detail, _ in v.rows],
                         [("Swings lost", "×12"), ("Judgement sat ready", "64.6 s"),
                          ("Consecration sat ready", "72.8 s"), ("Holy Strike sat ready", "38.6 s")])
        self.assertEqual([round(dmg) for *_, dmg in v.rows], [1538, 614, 343, 211])
        self.assertEqual(v.gap, ("12 swings lost while you weren't attacking", "≈ 1,538"))
        self.assertAlmostEqual(v.left_on_table, 2705, delta=1)
        self.assertEqual(v.went_well, ["1 dispel", "Never below 86% health"])
        self.assertEqual(v.also, ["Holy Strike: Out of range ×2"])      # the rest are rows already
        self.assertEqual(v.group, [("Piraña Segundo", 4518, 177, False), ("Evilguy Verybad", 3040, 0, False),
                                   ("You", 2583, 53, True), ("Shizuka Tsuruta", 0, 198, False),
                                   ("Anaruz Lightborne", 0, 68, False)])
        self.assertIn("25% of the damage (3rd of 5)", v.group_line)
        self.assertEqual(v.group_line, "You did 25% of the damage (3rd of 5) and 11% of the healing.")
        self.assertEqual(len(v.abilities), 8)

    def test_fight_view_minimal_dict(self):
        """an old saved fight: no free, auto, group or potential; nothing to show is empty, never an error"""
        v = build_fight(BARE)
        self.assertEqual((v.rows, v.gap, v.group, v.group_line, v.left_on_table), ([], None, None, None, None))
        self.assertEqual((v.went_well, v.also, v.abilities, v.zone, v.verdict), ([], [], [], "", ""))
        self.assertEqual((v.name, v.duration, v.efficiency, v.big), ("Aku'mai", "0:20", None, "–"))
        self.assertEqual(v.caption, "no damage done this fight")
        old = dict(ORACLE, cooldowns=[{"name": "Judgement", "cd": 8.0, "used": 2, "lost": 600.0}])
        for key in ("auto", "group", "potential", "efficiency"):
            del old[key]
        v = build_fight(old)       # a cooldown saved before ready time was measured: no seconds to name
        self.assertEqual(v.rows, [("Judgement sat ready", "", 600.0)])
        self.assertEqual(v.gap, ("Judgement sat ready", "≈ 600"))
        self.assertEqual((v.left_on_table, v.group, v.big, v.efficiency), (None, None, "–", None))

    def test_healing_role_has_no_gap(self):
        heal = dict(ORACLE, healing_role=True, healing=4200, efficiency=1.0, potential=2583, good=["Healed 4,200"],
                    improve=["Piraña Segundo died"])
        v = build_fight(heal)
        self.assertEqual((v.rows, v.gap, v.left_on_table), ([], None, None))     # nothing left: no total
        self.assertEqual((v.big, v.unit), ("100", "%"))           # efficiency stays the figure while there is one
        self.assertEqual(v.also, ["Piraña Segundo died"])
        del heal["efficiency"]
        v = build_fight(heal)
        self.assertEqual((v.big, v.unit, v.caption), ("4,200", None, "healed · mostly healing this fight"))

    def test_close_call_tops_also(self):
        """danger: one line at the top of Also, in place of summary's own "Dropped to" line; the detail stays in the
        drawer"""
        danger = {"t": 75.758, "hp": 0.2393617021276596, "unused": ["Divine Protection"],
                  "hits": [{"who": "Aku'mai", "spell": "Melee", "amount": 160}]}
        f = dict(ORACLE, danger=danger,
                 improve=ORACLE["improve"] + ["Dropped to 24% health with Divine Protection ready"])
        v = build_fight(f)
        self.assertEqual(v.also, ["Close call: down to 24% health at 1:15 — Divine Protection was ready",
                                  "Holy Strike: Out of range ×2"])
        two = build_fight(dict(f, danger=dict(danger, unused=["Divine Protection", "Lay on Hands"])))
        self.assertEqual(two.also[0], "Close call: down to 24% health at 1:15 — Divine Protection and Lay on Hands "
                                      "were ready")
        bare = build_fight(dict(f, danger=dict(danger, unused=[])))
        self.assertEqual(bare.also[0], "Close call: down to 24% health at 1:15")
        died = dict(ORACLE, result="you died", danger=dict(danger, hp=0.0, unused=[]),
                    improve=["Dropped to 0% health (Aku'mai: Melee for 160)"])
        self.assertEqual(build_fight(died).also, ["Dropped to 0% health (Aku'mai: Melee for 160)"])  # not a close call

    def test_nothing_left_on_the_table(self):
        """under 1 left (or a potential under the damage): no total, as the old page's >= 1"""
        self.assertIsNone(build_fight(dict(ORACLE, potential=2583.4)).left_on_table)
        self.assertIsNone(build_fight(dict(ORACLE, potential=2500.0)).left_on_table)
        self.assertAlmostEqual(build_fight(dict(ORACLE, potential=2584.0)).left_on_table, 1.0)

    def test_held_and_idle_rows(self):
        f = dict(ORACLE, cooldowns=[dict(ORACLE["cooldowns"][0], held=True, lost=0.0),
                                    dict(ORACLE["cooldowns"][1], lost=0.0)],
                 idle={"total": 30.0, "with_resource": 12.3, "out_of_resource": 0.0, "moving": 0.0, "lost": 900.0,
                       "filler": True},
                 improve=["12 swings lost while not attacking ≈ 1,538 damage",
                          "12.3 s idle with a target, standing, with resource to spare ≈ 900 damage"])
        v = build_fight(f)
        self.assertEqual([(label, detail) for label, detail, _ in v.rows],
                         [("Swings lost", "×12"), ("Idle with resource", "12.3 s")])
        self.assertEqual(v.also, [])

    def test_group_deaths_and_ties(self):
        f = dict(ORACLE, damage=3040, group=dict(ORACLE["group"], deaths=["Shizuka Tsuruta"]))
        v = build_fight(f)
        self.assertEqual([name for name, *_ in v.group][:3], ["Piraña Segundo", "You", "Evilguy Verybad"])
        self.assertTrue(v.group_line.endswith("(2nd of 5) and 11% of the healing. Died: Shizuka Tsuruta."))
        self.assertIsNone(build_fight(dict(ORACLE, group=dict(ORACLE["group"], size=1))).group)

    def test_list_row(self):
        self.assertEqual(list_row(ORACLE), ("Blackfathom Oracle +3",
                                            [("23 DPS · ", "mu"), ("49%", "gD"), (" · 1:52", "mu")], "PvP"))
        self.assertEqual(list_row(BARE), ("Aku'mai", [("no damage · 0:20", "mu")], "Dungeon"))
        clean = dict(ORACLE, efficiency=0.93, more=0, result="you died")
        self.assertEqual(list_row(clean)[:2], ("Blackfathom Oracle", [("23 DPS · ", "mu"), ("93%", "gS"),
                                                                      (" · 1:52", "mu"), (" · died", "mu")]))
        self.assertEqual(list_row(dict(ORACLE, efficiency=0.74))[1][1], ("74%", "tx2"))
        self.assertEqual(list_row(dict(ORACLE, efficiency=0.6))[1][1], ("60%", "tx2"))
        old = dict(ORACLE)
        del old["efficiency"]
        self.assertEqual(list_row(old)[1], [("23 DPS", "mu"), (" · 1:52", "mu")])
        healer = dict(BARE, healing_role=True, healing=900, efficiency=1.0, dps=0.0)
        self.assertEqual(list_row(healer)[1][:2], [("0 DPS · ", "mu"), ("100%", "gS")])

    def test_run_window(self):
        """the fight's window in the loaded run's seconds, 3 s either side; None when it isn't inside the run"""
        run_start = datetime(2026, 11, 18, 23, 37)
        a, b = run_window(ORACLE, run_start, 600.0)
        self.assertAlmostEqual(a, 109.824 - 3, places=3)
        self.assertAlmostEqual(b, 109.824 + 112.458 + 3, places=3)
        self.assertIsNone(run_window(ORACLE, run_start, 200.0))                      # the run ended mid-fight
        self.assertIsNone(run_window(ORACLE, datetime(2026, 11, 18, 23, 40), 600.0))  # it started after the fight


@unittest.skipUnless(HAVE_QT, "needs PyQt6")
class FightPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_page_paints_and_shows_on_the_timeline(self):
        from dips_score.ui.fightsview import FightDetail
        page = FightDetail()
        page.resize(1200, 900)
        shown = []
        page.show_me.connect(lambda a, b: shown.append((a, b)))
        page.show_fight(ORACLE, (106.8, 225.3))
        self.assertEqual((page.page.title, page.page.sub), ("Blackfathom Oracle +3 more",
                                                             "Wed 18 Nov 23:38:49 · Blackfathom Deeps"))
        self.assertEqual((page.plate.title, page.plate.price), ("12 swings lost while you weren't attacking",
                                                                "≈ 1,538"))
        self.assertEqual(page.plate.button.text(), "Show on the timeline")
        page.plate.button.click()
        self.assertEqual(shown, [(106.8, 225.3)])
        self.assertEqual(page.drawer.label, "ABILITIES (8)")
        self.assertTrue(page.drawer.body.isHidden())
        self.assertEqual([r.ink for r in page.where.rows], ["m-act", "m-cd", "m-cd", "m-cd"])
        self.assertEqual(page.where.total, ("Left on the table · estimate — only time you were free to act",
                                            "≈2,705"))
        self.assertFalse(page.grab().isNull())
        page.drawer.flip()
        self.assertFalse(page.grab().isNull())
        page.show_fight(ORACLE, None)              # outside the loaded run: no button
        self.assertFalse(page.plate.has_button)
        page.show_fight(BARE)                      # nothing to fix, nobody with you
        self.assertTrue(page.plate.isHidden())
        self.assertTrue(page.where.isHidden())
        self.assertTrue(page.share.isHidden())
        self.assertFalse(page.grab().isNull())
        page.show_fight(None)
        self.assertFalse(page.empty.isHidden())
        self.assertTrue(page.hero.isHidden())
        self.assertFalse(page.grab().isNull())

    def test_fight_list_rows(self):
        from dips_score.ui.fightsview import FightList
        fl = FightList()
        fl.resize(260, 400)
        got = []
        fl.picked.connect(got.append)
        fl.set_fights([BARE, ORACLE])                       # oldest first, as the history keeps them
        self.assertEqual(fl.count(), 2)
        self.assertIs(got[-1], ORACLE)                      # the newest, on top
        fl.add_fight(dict(ORACLE, id="later"))
        self.assertEqual((fl.count(), fl.currentRow()), (3, 0))
        self.assertFalse(fl.grab().isNull())


if __name__ == "__main__":
    unittest.main()
