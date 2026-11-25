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
DANGER = {"t": 75.758, "hp": 0.2393617021276596, "answered": False, "unused": ["Divine Protection", "Lay on Hands"],
          "hits": [{"who": "Aku'mai", "spell": "Melee", "amount": 1160},
                   {"who": "Murkshallow Snapclaw", "spell": "Rend", "amount": 77},
                   {"who": "Aku'mai", "spell": "Melee", "amount": 155}]}
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

    def test_fight_view_minimal_dict(self):
        """an old saved fight: no free, auto, group or potential; nothing to show is empty, never an error"""
        v = build_fight(BARE)
        self.assertEqual((v.rows, v.gap, v.group, v.group_line, v.left_on_table), ([], None, None, None, None))
        self.assertEqual((v.went_well, v.also, v.zone, v.verdict), ([], [], "", ""))
        self.assertEqual((v.pull, v.danger), ([], []))
        self.assertEqual((build_fight(ORACLE).pull, build_fight(ORACLE).danger), ([], []))   # no pull, foes or danger
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

    def test_danger_leaves_also(self):
        """danger, lived or died: the Danger section says it, so Also has no close call and none of summary's "Dropped
        to" lines; without danger Also is d["improve"] less the rows"""
        f = dict(ORACLE, danger=DANGER,
                 improve=ORACLE["improve"] + ["Dropped to 24% health with Divine Protection ready"])
        self.assertEqual(build_fight(f).also, ["Holy Strike: Out of range ×2"])
        died = dict(ORACLE, result="you died", danger=dict(DANGER, hp=0.0, unused=[]),
                    improve=["Dropped to 0% health (Aku'mai: Melee for 160)"])
        self.assertEqual(build_fight(died).also, [])
        calm = dict(ORACLE, improve=ORACLE["improve"] + ["Dropped to 40% health"])
        self.assertEqual(build_fight(calm).also, ["Holy Strike: Out of range ×2", "Dropped to 40% health"])

    def test_the_pull(self):
        """the time since the last fight, every enemy (none named for a lone one), the buffs at pull (eight at most)"""
        f = dict(ORACLE, pull={"since_last": 14.6, "buffs": [f"Buff {k}" for k in range(10)], "own": [], "rest": False},
                 foes=[["Blackfathom Oracle", 1], ["Blackfathom Tide Priestess", 2], ["Murkshallow Snapclaw", 1]])
        self.assertEqual(build_fight(f).pull, [
            ("Since the last fight", "15 s"),
            ("Enemies", "Blackfathom Oracle, Blackfathom Tide Priestess ×2, Murkshallow Snapclaw"),
            ("Buffs", ", ".join(f"Buff {k}" for k in range(8)))])
        first = dict(ORACLE, pull={"since_last": None, "buffs": []}, foes=[["Aku'mai", 1]])
        self.assertEqual(build_fight(first).pull, [("Since the last fight", "first fight since the log started")])
        no_pull = dict(ORACLE, foes=[["Aku'mai", 1], ["Ghamoo-ra", 1]])     # no pull kept: nothing said about it
        self.assertEqual(build_fight(no_pull).pull, [("Enemies", "Aku'mai, Ghamoo-ra")])

    def test_danger(self):
        """your lowest health and when, a row of hits per attacker (the label on the first only), what sat ready"""
        self.assertEqual(build_fight(dict(ORACLE, danger=DANGER)).danger, [
            ("Lowest health", "24% at 1:15"), ("Hits", "Aku'mai: Melee 1,160, Melee 155"),
            ("", "Murkshallow Snapclaw: Rend 77"), ("Ready, not used", "Divine Protection, Lay on Hands")])
        bare = build_fight(dict(ORACLE, danger=dict(DANGER, unused=[], hits=DANGER["hits"][:1]))).danger
        self.assertEqual(bare, [("Lowest health", "24% at 1:15"), ("Hits", "Aku'mai: Melee 1,160")])
        old = {k: v for k, v in DANGER.items() if k != "answered"}      # not known whether one was pressed
        self.assertNotIn("Ready, not used", [label for label, _ in build_fight(dict(ORACLE, danger=old)).danger])

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

    def test_swinging_idle_and_lost_shots(self):
        f = dict(ORACLE, cooldowns=[], auto=None, potential=ORACLE["damage"] + 1400.0,
                 ranged={"shots": 30, "speed": 3.0, "shots_lost": 4, "clipped": 1, "damage_lost": 500.0},
                 idle={"total": 30.0, "with_resource": 12.3, "out_of_resource": 0.0, "moving": 0.0, "lost": 900.0,
                       "filler": True, "swinging": 20.0, "swinging_free": 10.0, "shooting": False},
                 improve=["No ability used for 10.0 s while swinging and 2.3 s idle with a target, standing, with "
                          "resource to spare ≈ 900 damage", "4 shots lost while not shooting ≈ 500 damage"])
        v = build_fight(f)
        self.assertEqual([(label, detail) for label, detail, _ in v.rows],
                         [("No ability", "10.0 s swinging, 2.3 s idle"), ("Shots lost", "×4"),
                          ("Shots clipped by casts", "×1")])        # clipped: not priced, under the priced rows
        self.assertEqual(v.rows[-1][2], 0.0)
        self.assertEqual(v.gap[0], "No ability used for 10.0 s while swinging and 2.3 s idle with resource to spare")
        self.assertEqual(v.also, [])
        f["idle"] = dict(f["idle"], swinging_free=12.3, shooting=True)     # all of it shooting: no "idle" part
        self.assertEqual(build_fight(f).rows[0][:2], ("No ability", "12.3 s shooting"))

    def test_melee_share_line(self):
        """over the losses when melee or shots are 10% or more of your damage; none in an older fight"""
        self.assertIsNone(build_fight(ORACLE).auto_share)            # saved before the hit tables kept damage
        f = dict(ORACLE, auto=dict(ORACLE["auto"], damage=1666))
        text, share = build_fight(f).auto_share
        self.assertEqual(text, "Melee 64% of your damage")
        self.assertAlmostEqual(share, 1666 / 2583)
        f["ranged"] = {"shots": 9, "damage": 520, "clipped": 0}
        self.assertEqual(build_fight(f).auto_share[0], "Melee 64% and shots 20% of your damage")
        f = dict(ORACLE, auto=dict(ORACLE["auto"], damage=200))      # 8%: not said
        self.assertIsNone(build_fight(f).auto_share)
        self.assertIsNone(build_fight(dict(ORACLE, auto=dict(ORACLE["auto"], damage=1666), healing_role=True))
                          .auto_share)

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
        self.assertEqual(page.drawer.label, "ALL THE DETAILS (6)")   # its sections: Abilities, Cooldowns, ... Resource
        self.assertTrue(page.drawer.body.isHidden())
        self.assertEqual([r.ink for r in page.where.rows], ["m-act", "m-cd", "m-cd", "m-cd"])
        self.assertIsNone(page.where.lead)                  # an older fight: no melee line
        page.show_fight(dict(ORACLE, auto=dict(ORACLE["auto"], damage=1666),
                             ranged={"shots": 9, "speed": 2.9, "shots_lost": 0, "damage": 0, "clipped": 3,
                                     "damage_lost": 0.0}), (106.8, 225.3))
        self.assertEqual(page.where.lead[0], "Melee 64% of your damage")
        self.assertEqual((page.where.rows[-1].name, page.where.rows[-1].value_text, page.where.rows[-1].note),
                         ("Shots clipped by casts", "–", "×3"))
        self.assertFalse(page.grab().isNull())
        page.show_fight(ORACLE, (106.8, 225.3))
        self.assertEqual(page.where.total, ("Left on the table · estimate — only time you were free to act",
                                            "≈2,705"))
        self.assertFalse(page.grab().isNull())
        page.drawer.flip()
        self.assertFalse(page.grab().isNull())
        page.show_fight(ORACLE, None)              # outside the loaded run: no button
        self.assertFalse(page.plate.has_button)
        page.show_fight(BARE)                      # nothing to fix, nobody with you
        self.assertEqual(page.drawer.label, "ALL THE DETAILS (2)")   # idle time and resource
        self.assertTrue(page.plate.isHidden())
        self.assertTrue(page.where.isHidden())
        self.assertTrue(page.share.isHidden())
        self.assertTrue(page.pull.isHidden())
        self.assertTrue(page.danger.isHidden())
        self.assertFalse(page.grab().isNull())
        page.show_fight(None)
        self.assertFalse(page.empty.isHidden())
        self.assertTrue(page.hero.isHidden())
        self.assertFalse(page.grab().isNull())

    def test_pull_and_danger_in_the_side(self):
        """the pull and danger: out of the drawer, into the right-hand column when the fight has them"""
        from PyQt6.QtGui import QImage, QPainter
        from dips_score.ui.fightsview import FightDetail, _details
        f = dict(ORACLE, pull={"since_last": 14.6, "buffs": ["Blessing of Might"]}, danger=DANGER,
                 foes=[["Blackfathom Oracle", 1], ["Blackfathom Tide Priestess", 3]])
        self.assertFalse({"Pull", "Enemies", "Danger"} & {title for title, _ in _details(f)})
        page = FightDetail()
        page.resize(1200, 900)
        page.show_fight(f)
        v = build_fight(f)
        self.assertEqual((page.pull.title, page.pull.rows), ("The pull", v.pull))
        self.assertEqual((page.danger.title, page.danger.rows), ("Danger", v.danger))
        self.assertFalse(page.pull.isHidden())
        self.assertFalse(page.danger.isHidden())
        self.assertFalse(page.grab().isNull())
        for w in (420, 260):         # the height it measures is the height it paints, a wrapped row included
            img = QImage(w, 600, QImage.Format.Format_ARGB32)
            p = QPainter(img)
            self.assertEqual(page.danger.draw(None, w), page.danger.draw(p, w))
            p.end()
        page.show_fight(ORACLE)
        self.assertTrue(page.pull.isHidden())
        self.assertTrue(page.danger.isHidden())

    def test_grade_inks_read_on_the_rail(self):
        """the fight list's efficiency inks (gS, gD) are lifted toward rail-tx until they read at 4.5:1 on the rail and
        on the picked row in all four looks; an ink that already reads is left alone"""
        from dips_score.ui import theme
        from test_tokens import contrast
        was = (theme.NAME, theme.MODE)
        try:
            for look in (("timeless", "day"), ("timeless", "night"), ("classical", "day"), ("classical", "night")):
                theme.apply(*look)
                for key in ("gS", "gD"):
                    got = theme.on_rail(theme.tok(key)).name()
                    for bg in ("rail", "rail-on"):
                        self.assertGreaterEqual(contrast(got, theme.tok(bg).name()), 4.5, (look, key, bg))
                self.assertEqual(theme.on_rail(theme.tok("rail-tx")), theme.tok("rail-tx"))
            theme.apply("timeless", "day")
            self.assertNotEqual(theme.on_rail(theme.tok("gD")), theme.tok("gD"))    # 1.4:1 on the dark rail: lifted
        finally:
            theme.apply(*was)

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
        fl.setCurrentRow(2)                                 # reading an older fight: a new one keeps you on it
        reading = fl.fights[2]
        fl.add_fight(dict(ORACLE, id="newer"))
        self.assertIs(fl.fights[fl.currentRow()], reading)
        fl.add_fight(dict(ORACLE, id="later", damage=1))    # another fight updated in place: still the same one
        self.assertIs(fl.fights[fl.currentRow()], reading)
        self.assertFalse(fl.grab().isNull())


if __name__ == "__main__":
    unittest.main()


class PressTests(unittest.TestCase):
    """what you pressed in a fight, from the add-on's lines: by spell, by key or click"""
    def test_presses(self):
        from dips_score.fight_view import NONE_PRESSED, presses
        from dips_score.model.run import TLine

        def ln(t, code, *f):
            return TLine(t, code, [str(x) for x in f], 0)
        names = {2495: "Holy Strike", 1310994: "Swift Judgement", 6603: "Attack", 2: "Spell two"}
        lines = [ln(1, "A", 3, "spell", 2495, "K"), ln(2, "A", 3, "spell", 2495, "C"), ln(3, "A", 4, "spell", 2495, "?"),
                 ln(4, "A", 51, "macro", 1310994, "K"),                         # a macro that names its spell
                 ln(5, "A", 60, "macro", 7, "C"), ln(5.2, "CS", 6603),         # one that doesn't: the cast that followed
                 ln(6, "A", 60, "macro", 7, "C"),                               # nothing followed
                 ln(7, "A", 61, "item", 5512, "K"), ln(9, "CS", 2),             # too late to be its cast
                 ln(50, "A", 3, "spell", 2495, "K")]                            # outside the fight
        v = presses(lines, (0, 20), names)
        self.assertEqual(v.rows, [("Holy Strike", "", "2495", 1, 1, 1), ("Attack", "macro", "6603", 0, 1, 0),
                                  ("Item 5512", "item, no spell followed", "–", 1, 0, 0),
                                  ("Macro 7", "macro, no spell followed", "–", 0, 1, 0),
                                  ("Swift Judgement", "macro", "1310994", 1, 0, 0)])
        self.assertEqual(v.line, "7 presses, 3 by key, 3 by click, 1 the game's bars didn't say.")
        self.assertEqual(presses(lines[:1] + lines[3:4], (0, 20), names).line, "2 presses, all by key.")
        self.assertEqual(presses(lines[:1], (0, 20), {}).rows, [("Spell 2495", "", "2495", 1, 0, 0)])
        self.assertEqual((presses(lines, (30, 40), names).rows, presses(lines, (30, 40), names).line),
                         ([], NONE_PRESSED))

    def test_why_no_presses(self):
        from dips_score.fight_view import ARRIVES, NOT_HERE, NOT_RECORDED, OLDER, press_reason
        at, saved, oldest = datetime(2026, 11, 25, 12), datetime(2026, 11, 25, 11).timestamp(), datetime(2026, 11, 20)
        self.assertEqual(press_reason(at, saved, oldest, False), ARRIVES)          # after the game's last save
        self.assertEqual(press_reason(datetime(2026, 11, 19), saved, oldest, False), OLDER)
        self.assertEqual(press_reason(datetime(2026, 11, 22), saved, oldest, False), NOT_HERE)
        self.assertEqual(press_reason(datetime(2026, 11, 22), saved, oldest, True), NOT_RECORDED)   # a dungeon's
        self.assertEqual(press_reason(at, None, None, False), NOT_HERE)

