"""What the Timeline tab says (dips_score/timeline_view.py), on the real Blackfathom run's idle gaps (copied in as a
literal) and on stubs; the tab and its lanes when PyQt6 is there:
PYTHONPATH=<folder with PyQt6> python -m unittest discover -s tests"""
import importlib.util
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dips_score.debrief import FightCell  # noqa: E402
from dips_score.timeline_view import (fight_verdict, fight_window, idle_moments, idle_view, option_text,  # noqa: E402
                                      scope_for, step, with_fight)

HAVE_QT = importlib.util.find_spec("PyQt6") is not None

# Blackfathom Deeps, 18 Nov 22:27 (run 6): the Activity score's idle gaps of 2.5 s or more (metrics.idle_gaps, which
# the timeline shows as Data.idle), the whole run; and three of its fights
IDLE = [(153.461, 156.181), (322.419, 328.871), (410.798, 421.359), (422.859, 428.129), (527.77, 530.515),
        (532.015, 535.38), (576.19, 584.189), (986.632, 991.059), (1137.626, 1140.599), (1157.648, 1160.574),
        (1757.86, 1768.802), (1967.824, 1970.951), (2186.746, 2189.578), (2639.718, 2644.653), (2764.094, 2768.571),
        (2799.314, 2801.819), (2915.455, 2919.926), (2952.398, 2956.356), (3242.45, 3245.066), (3361.16, 3366.553),
        (3404.211, 3409.912), (3511.261, 3513.834), (3820.573, 3823.282), (4168.275, 4175.158), (4176.658, 4185.233)]
DURATION = 4185.257
CELLS = [FightCell(5, "4:47", "Trash", 83, "A", False, False, 287.878, 336.728),
         FightCell(6, "6:25", "Trash", 70, "C", False, False, 385.497, 475.078),
         FightCell(7, "8:46", "Trash", 78, "B", False, False, 526.291, 586.197)]
SPANS = [(c.start, c.end) for c in CELLS]
FIGHT_625 = SPANS[1]
# the same three fights' own gaps, as each fight's card (fr.metrics.idle_gaps) counts them: 4:47's starts later than
# the whole run's (its swing speed is measured over the fight alone)
OWN = [[(323.238, 328.871)], [(410.799, 421.359), (422.859, 428.129)],
       [(527.77, 530.515), (532.015, 535.38), (576.19, 584.189)]]


class TimelineViewTests(unittest.TestCase):
    def test_idle_moments_clip_and_sort(self):
        self.assertEqual(idle_moments(IDLE, FIGHT_625), [(410.798, 421.359), (422.859, 428.129)])
        whole = idle_moments(IDLE, (0.0, DURATION))
        self.assertEqual((len(whole), whole[0]), (25, (1757.86, 1768.802)))
        # cut to the window, and only what still lasts 2.5 s counts: (40, 50) keeps 2 s of it
        self.assertEqual(idle_moments([(10, 20), (30, 33), (40, 50), (70, 80)], (15, 42)), [(15, 20), (30, 33)])
        self.assertEqual(idle_moments([(20, 23), (5, 8)], (0, 60)), [(5, 8), (20, 23)])   # a tie: the earlier first
        self.assertEqual(idle_moments([(0, 3)], (0, 60), min_s=4), [])

    def test_fight_verdict_text(self):
        self.assertEqual(fight_verdict(idle_moments(IDLE, FIGHT_625)),
                         "Idle twice for 2.5 s or more — longest 10.6 s at 6:50.")
        self.assertEqual(fight_verdict(idle_moments(IDLE, (0.0, DURATION))),    # as the Debrief's Activity line
                         "Idle 25 times for 2.5 s or more — longest 10.9 s at 29:17.")
        self.assertEqual(fight_verdict([(153.461, 156.181)]), "Idle once for 2.5 s or more: 2.7 s at 2:33.")
        self.assertEqual(fight_verdict([]), "No idle moments of 2.5 s or more in combat.")

    def test_idle_view(self):
        v = idle_view(IDLE, FIGHT_625)
        self.assertEqual((v.big, v.gaps), ("16", "gaps of 2.5 s or more"))
        self.assertEqual(v.plate, ("Longest idle: 10.6 s at 6:50", "16 s idle", "2 gaps of 2.5 s or more"))
        self.assertEqual([(at, length) for at, length, _ in v.rows], [("6:50", "10.6 s"), ("7:02", "5.3 s")])
        self.assertEqual(v.rows[0][2], 1.0)
        self.assertAlmostEqual(v.rows[1][2], 5.27 / 10.561)
        none = idle_view(IDLE, (600.0, 900.0))       # a stretch with no gap
        self.assertEqual((none.big, none.gaps, none.rows), ("0", "gaps of 2.5 s or more", []))
        self.assertEqual(none.plate, ("No idle moments of 2.5 s or more", None, None))
        self.assertEqual(idle_view(IDLE, (150.0, 160.0)).plate[2], "1 gap of 2.5 s or more")

    def test_scope_for(self):
        self.assertIsNone(scope_for(SPANS, DURATION, (-41.85, 4227.11)))       # the whole run (show_all)
        self.assertEqual(scope_for(SPANS, DURATION, fight_window(*FIGHT_625)), 1)   # the Debrief's, and the picker's
        self.assertEqual(scope_for(SPANS, DURATION, (385.32 - 3, 475.078 + 3)), 1)  # a pull, 3 s either side
        self.assertEqual(scope_for(SPANS, DURATION, (278.572 - 3, 336.728 + 3)), 0)  # a pull engaged 9 s early
        self.assertEqual(scope_for(SPANS, DURATION, (400.0, 425.0)), (400.0, 425.0))  # inside a fight: custom
        self.assertEqual(scope_for(SPANS, DURATION, (280.0, 600.0)), (280.0, 600.0))  # three fights: custom
        self.assertEqual(scope_for(SPANS, DURATION, (380.0, 520.0)), (380.0, 520.0))  # well past the fight: custom
        self.assertEqual(scope_for([], 0.0, (385.0, 480.0)), (385.0, 480.0))         # no run

    def test_with_fight(self):
        merged = with_fight(IDLE, SPANS[0], OWN[0])         # 4:47's own gap in place of the run's
        self.assertIn((323.238, 328.871), merged)
        self.assertNotIn((322.419, 328.871), merged)
        self.assertEqual(len(merged), len(IDLE))
        self.assertEqual(with_fight([], SPANS[0], []), [])

    def test_fight_window_and_step(self):
        self.assertEqual(fight_window(100.0, 110.0), (97.0, 113.0))                 # at least 3 s
        a, b = fight_window(*FIGHT_625)
        self.assertAlmostEqual(385.497 - a, 89.581 * 0.08)
        starts = [c.start for c in CELLS]
        self.assertEqual((step(starts, 1, 1), step(starts, 1, -1)), (2, 0))
        self.assertEqual((step(starts, 2, 1), step(starts, 0, -1)), (None, None))
        self.assertEqual((step(starts, None, 1), step(starts, None, -1)), (0, 2))     # from the whole run
        self.assertEqual((step(starts, (400.0, 425.0), 1), step(starts, (400.0, 425.0), -1)), (2, 1))
        self.assertIsNone(step([], None, 1))

    def test_option_text(self):
        self.assertEqual(option_text(CELLS[1]), "6:25 Trash · 90 s · 70 C")
        unscored = FightCell(0, "0:36", "Trash", None, "-", False, False, 36.2, 75.0)
        self.assertEqual(option_text(unscored), "0:36 Trash · 39 s")


@unittest.skipUnless(HAVE_QT, "needs PyQt6")
class TimelineTabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def tab(self):
        from dips_score.ui.timeline import Data
        from dips_score.ui.timelinetab import TimelineTab
        tab = TimelineTab()
        tab.resize(1300, 900)
        tab.timeline.set_data(Data(role="dps", duration=DURATION, idle=IDLE, fight_idle=OWN))
        tab.show_run("Blackfathom Deeps", "Wed 18 Nov 22:27 · 69:45 long", CELLS, DURATION, "32:57", "75 B")
        return tab

    def test_tab_follows_the_view_and_steps(self):
        tab = self.tab()
        t = tab.timeline
        self.assertEqual([tab.pick.itemText(i) for i in range(tab.pick.count())],
                         ["Whole run", "4:47 Trash · 49 s · 83 A", "6:25 Trash · 90 s · 70 C",
                          "8:46 Trash · 60 s · 78 B"])
        self.assertEqual((tab.pick.currentIndex(), tab.plate.label), (0, "In this run"))
        self.assertEqual(tab.hero.verdict, "Idle 25 times for 2.5 s or more — longest 10.9 s at 29:17.")
        self.assertEqual(tab.figures.items[:2], [("32:57", "in combat", ""), ("75 B", "run score", "")])
        self.assertEqual(tab.list.title, "Idle moments, longest first (10 of 25)")
        tab.follow(*fight_window(*FIGHT_625))            # Show me from the Debrief: the fight it shows is picked
        self.assertEqual(tab.pick.currentText(), "6:25 Trash · 90 s · 70 C")
        self.assertEqual((tab.plate.label, tab.plate.title, tab.plate.price),
                         ("In this fight", "Longest idle: 10.6 s at 6:50", "16 s idle"))
        self.assertEqual((tab.hero.big, tab.hero.suffix), ("16", "s idle"))
        self.assertEqual(tab.figures.items, [("90 s", "fight length", ""), ("70 C", "fight score", ""),
                                             ("2", "gaps of 2.5 s or more", "")])
        self.assertEqual(([r.name for r in tab.list.rows], tab.list.title),
                         (["6:50", "7:02"], "Idle moments, longest first"))
        tab.plate.button.click()                         # Next idle moment: zooms in the tab, the fight stays picked
        self.assertEqual((round(t.v0, 3), round(t.v1, 3)), (407.799, 424.359))     # the longest, 3 s either side
        tab.plate.button.click()
        self.assertEqual((round(t.v0, 3), round(t.v1, 3)), (419.859, 431.129))
        self.assertEqual(tab.pick.currentIndex(), 2)
        tab.next.click()                                 # the fight after
        self.assertEqual((tab.pick.currentIndex(), (t.v0, t.v1)), (3, fight_window(*SPANS[2])))
        self.assertFalse(tab.next.isEnabled())
        tab.follow(400.0, 425.0)                         # a death's window: a custom view
        self.assertEqual((tab.pick.currentIndex(), tab.pick.placeholderText(), tab.plate.label),
                         (-1, "custom view", "In this view"))
        self.assertEqual(tab.figures.items[0], ("25 s", "in view", ""))
        tab.prev.click()                                 # from a custom view: the fight it starts in
        self.assertEqual(tab.pick.currentIndex(), 2)
        tab.pick.setCurrentIndex(1)                      # a fight picked
        self.assertEqual(((t.v0, t.v1), tab.scope), (fight_window(*SPANS[0]), 0))
        tab.whole.click()
        self.assertEqual((tab.pick.currentIndex(), tab.scope), (0, None))
        self.assertLess(t.v0, 0)
        self.assertFalse(tab.grab().isNull())

    def test_a_healer_sees_answers_not_idle(self):
        from types import SimpleNamespace as NS
        from dips_score.ui.timeline import Data
        from dips_score.ui.timelinetab import TimelineTab
        tab = TimelineTab()
        tab.resize(1300, 900)
        tab.healer = ([NS(start=400.0, guid="t", response=2.5, covered=False), NS(start=410.0, guid="me", response=None,
                                                                                 covered=False)],
                      {"me": "You", "t": "Tank"}.get)
        tab.timeline.set_data(Data(role="healer", duration=DURATION, idle=IDLE, fight_idle=OWN))
        tab.show_run("Blackfathom Deeps", "", CELLS, DURATION, "32:57", "75 B")
        tab.follow(*fight_window(*FIGHT_625))
        self.assertEqual((tab.hero.big, tab.hero.suffix), ("4.2", "s to answer"))
        self.assertEqual(tab.figures.items[2], ("2", "dips under 60%", ""))
        self.assertTrue(tab.plate.isHidden() and tab.list.isHidden())
        self.assertEqual([(r.name, r.note, r.value_text) for r in tab.dips.rows],
                         [("6:50", "You", "no heal"), ("6:40", "Tank", "2.5 s")])
        self.assertEqual(tab.quiet.items, [("6:50", "10.6 s"), ("7:02", "5.3 s")])      # the fight's own gaps, in order
        self.assertFalse(tab.grab().isNull())

    def test_a_fight_speaks_with_its_own_card(self):
        """a fight picked: its own card's gaps (as its Debrief scores them) for the figures, list and washes; the
        whole run and custom views keep the run's"""
        tab = self.tab()
        t = tab.timeline
        self.assertEqual(t.idle, IDLE)
        tab.pick.setCurrentIndex(1)                      # 4:47: its card says "longest 5.6s"
        self.assertEqual((tab.plate.title, tab.hero.big), ("Longest idle: 5.6 s at 5:23", "6"))
        self.assertEqual([r.value_text for r in tab.list.rows], ["5.6 s"])
        self.assertIn((323.238, 328.871), t.idle)
        self.assertNotIn((322.419, 328.871), t.idle)
        tab.follow(300.0, 340.0)                         # a custom view over the same gap: the run's
        self.assertEqual(tab.plate.title, "Longest idle: 6.5 s at 5:22")
        self.assertEqual(t.idle, IDLE)
        tab.pick.setCurrentIndex(2)                      # 6:25: the same either way
        self.assertEqual((tab.plate.title, tab.hero.big), ("Longest idle: 10.6 s at 6:50", "16"))
        tab.whole.click()
        self.assertEqual((t.idle, tab.hero.verdict),
                         (IDLE, "Idle 25 times for 2.5 s or more — longest 10.9 s at 29:17."))

    def test_a_redraw_keeps_the_fight(self):
        tab = self.tab()
        tab.pick.setCurrentIndex(2)
        tab.show_run("Blackfathom Deeps", "", CELLS, DURATION, "32:57", "75 B", keep=True)    # the same run again
        self.assertEqual((tab.scope, (tab.timeline.v0, tab.timeline.v1)), (1, fight_window(*FIGHT_625)))
        tab.show_run("Blackfathom Deeps", "", CELLS, DURATION, "32:57", "75 B")               # another run
        self.assertEqual((tab.scope, tab.pick.currentIndex()), (None, 0))
        self.assertLess(tab.timeline.v0, 0)                                                     # the whole of it

    def test_no_run(self):
        from dips_score.ui.timelinetab import TimelineTab
        tab = TimelineTab()
        tab.resize(1300, 900)
        tab.set_analysis(None)
        tab.follow(385.0, 480.0)
        self.assertEqual((tab.hero.big, tab.plate.isHidden(), tab.list.isHidden()), ("–", True, True))
        self.assertFalse(tab.grab().isNull())

    def test_group_lanes_fold_and_open_for_a_highlight(self):
        from dips_score.model.roster import Player
        from dips_score.ui.timeline import Data, Timeline
        me = Player("me", "Bao Kahn", "PALADIN", "DPS", is_me=True)
        tank = Player("tank", "Anaruz Lightborne", "PALADIN", "TANK")
        heal = Player("heal", "Shizuka Tsuruta", "PRIEST", "HEALER")
        t = Timeline()
        t.resize(1000, 400)
        t.set_data(Data(role="dps", duration=600.0, idle=[(100.0, 110.0)], busy=[(90.0, 100.0)],
                        players=[tank, heal, me], roster={p.guid: p for p in (tank, heal, me)},
                        hp={"me": [(0.0, 1.0), (50.0, 0.6)], "tank": [(0.0, 1.0), (60.0, 0.7)]}))
        lanes = [(ln.key, ln.label, ln.guid) for ln in t.lanes]
        self.assertIn(("health", "Your health", "me"), lanes)
        self.assertIn(("health", "Tank health", "tank"), lanes)
        self.assertEqual(lanes[-1][0], "group")              # the others folded away, under one row
        self.assertNotIn("heal", [g for _, _, g in lanes])
        self.assertEqual((t.group.label, t.group.isHidden()), ("GROUP (2)", False))
        folded = t.minimumHeight()
        t.highlight("heal", "Flash Heal")                    # lit from the Spells tab: the group opens to show it
        self.assertTrue(t.group.open)
        self.assertIn(("spells", "Shizuka Tsuruta", "heal"), [(ln.key, ln.label, ln.guid) for ln in t.lanes])
        self.assertGreater(t.minimumHeight(), folded)
        t.hover_x = 500.0                                    # the crosshair and its readout paint
        self.assertFalse(t.grab().isNull())
        t.group.flip()
        self.assertEqual(t.minimumHeight(), folded)
        t.highlight("me", "Judgement")                       # yours: nothing to open
        self.assertFalse(t.group.open)


if __name__ == "__main__":
    unittest.main()


class Answers(unittest.TestCase):
    """a healer's Timeline: the dips in view, slowest answer first; quiet moments unjudged"""
    def test_answers(self):
        from types import SimpleNamespace as NS
        from dips_score.timeline_view import answer_view
        dips = [NS(start=1926.0, guid="d", response=2.4, covered=False), NS(start=1928.0, guid="d", response=0.4, covered=False),
                NS(start=1946.0, guid="t", response=2.0, covered=False), NS(start=1948.0, guid="t", response=0.0, covered=False),
                NS(start=1965.0, guid="me", response=None, covered=False), NS(start=1970.0, guid="t", response=None, covered=True),
                NS(start=10.0, guid="t", response=5.0, covered=False)]
        who = {"me": "You", "t": "Tank", "d": "DPS"}.get
        v = answer_view(dips, [(1910.0, 1914.1), (1960.0, 1961.0)], (1905.0, 2002.0), who)
        self.assertEqual((v.big, v.unit, v.count), ("2.0", "s to answer", 5))
        self.assertEqual(v.verdict, "5 dips under 60% in this fight, the middle answer 2.0 s. One had no heal from you "
                                    "within 6 s and counts as 6.")
        self.assertEqual([(at, w, a) for at, w, _, a in v.rows], [("32:45", "You", "no heal"), ("32:06", "DPS", "2.4 s"),
                                                                 ("32:26", "Tank", "2.0 s"), ("32:08", "DPS", "0.4 s"),
                                                                 ("32:28", "Tank", "0.0 s")])
        self.assertEqual(v.rows[0][2], 1.0)
        self.assertEqual(v.quiet, [("31:50", "4.1 s")])                 # 1 s isn't a quiet moment
        none = answer_view([], [], (0.0, 60.0), who, "in this run")
        self.assertEqual((none.big, none.unit, none.verdict, none.rows), ("0", "dips under 60%",
                                                                          "Nobody dropped under 60% in this run.", []))

