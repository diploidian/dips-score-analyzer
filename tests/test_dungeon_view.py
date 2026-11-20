"""The dungeon page's History tab: dungeon_view.py (no Qt), and its widgets in ui/historytab.py (skipped without
PyQt6: PYTHONPATH=<folder with PyQt6> python -m unittest discover -s tests).

R2: the cards below are the real Blackfathom Deeps visits' (18 Nov 22:16, 22:17 and 22:27), as literals."""
import importlib.util
import os
import sys
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dips_score.dungeon_view import (TOO_SHORT, UNJUDGED, Visit, build_history, history_meta, plate_text,  # noqa: E402
                                     trend_note, visits)
from dips_score.scoring.score import Category, Scorecard  # noqa: E402

HAVE_QT = importlib.util.find_spec("PyQt6") is not None
ME = "Player-5826-0217F1D2"


def card_2227() -> Scorecard:
    """22:27, the full clear: 75 B as DPS"""
    return Scorecard(75.334, "B", "dps", [
        Category("Damage", 97.32, 20, ""), Category("Activity", 90.18, 15, ""), Category("Cooldowns", 23.07, 10, ""),
        Category("Interrupts", 0.0, 10, "", unavailable="no interrupt used this run"),
        Category("Casting", 79.6, 10, ""), Category("Movement", 100.0, 0, ""), Category("Survival", 53.11, 10, ""),
        Category("Input", 100.0, 5, ""), Category("Upkeep", 58.62, 5, ""), Category("Positioning", 39.21, 0, "")])


def card_2216() -> Scorecard:
    """22:16: one 2.2 s fight, which the card scores 58 D"""
    return Scorecard(57.939, "D", "dps", [
        Category("Damage", 0.0, 20, ""), Category("Activity", 0.0, 15, ""), Category("Cooldowns", 100.0, 10, ""),
        Category("Interrupts", 0.0, 10, "", unavailable="no interrupt used this run"),
        Category("Casting", 100.0, 10, ""), Category("Movement", 100.0, 10, ""), Category("Survival", 100.0, 10, ""),
        Category("Input", 100.0, 5, ""), Category("Upkeep", 84.96, 5, ""),
        Category("Positioning", 0.0, 0, "", unavailable="too few position readings to judge")])


def run(rid: str, when: datetime, pieces: int = 1):
    return SimpleNamespace(id=rid, start_time=when, parts=[rid] * pieces)


def analysed(card, duration, combat, bosses=(0, 0), mine=0, others=0, wipes=0):
    return SimpleNamespace(card=card, data=SimpleNamespace(duration=duration, player_guid=ME),
                           metrics=SimpleNamespace(combat_time=combat),
                           summary=SimpleNamespace(bosses_killed=bosses[0], bosses=bosses[1]),
                           deaths=[SimpleNamespace(guid=ME)] * mine + [SimpleNamespace(guid="Player-2")] * others,
                           wipes=[None] * wipes)


def blackfathom():
    """the three real visits, oldest first (as the rail lists them, newest first, reversed), and one whose analysis
    failed"""
    return [(run("1795069010-Bao", datetime(2026, 11, 18, 22, 16, 50)), analysed(card_2216(), 16.092, 2.209)),
            (run("1795069037-Bao", datetime(2026, 11, 18, 22, 17, 17)),
             analysed(Scorecard(0.0, "-", "dps", note="no combat in this run, nothing to score"), 20.805, 0)),
            (run("1795069645-Bao", datetime(2026, 11, 18, 22, 27, 25), pieces=2),
             analysed(card_2227(), 4185.257, 1977.628, (6, 6), mine=1, others=3)),
            (run("broken", datetime(2026, 11, 17, 20, 0)), None)]


def visit(day: int, score: float | None, lost: dict, cats: dict | None = None, short: float | None = None) -> Visit:
    """short: too short to compare, with that card score"""
    s = score if short is None else short
    grade = "-" if s is None else "S" if s >= 90 else "A" if s >= 80 else "B" if s >= 70 else "C"
    note = "" if score is not None else UNJUDGED if short is None else TOO_SHORT
    return Visit(datetime(2026, 11, day, 21, 0), f"r{day}", 3600.0, 1800.0, score, grade, "6 of 6", 0, 0,
                 cats or {}, lost, note, role="dps", card_score=short)


def history():
    """the mock-up's history, newest first: six scored visits and one too short to compare (64 C on its card)"""
    return [visit(18, 75.0, {"Cooldowns": 10.3, "Survival": 6.3, "Upkeep": 2.8}, {"Cooldowns": 23.0, "Damage": 97.0}),
            visit(17, None, {}, short=64.0),
            visit(14, 69.0, {"Cooldowns": 8.1, "Damage": 12.0, "Survival": 2.0}, {"Cooldowns": 30.0, "Damage": 80.0}),
            visit(11, 82.0, {"Cooldowns": 6.2, "Damage": 9.0, "Survival": 0.5}, {"Cooldowns": 41.0, "Damage": 88.0}),
            visit(8, 71.0, {"Cooldowns": 7.0, "Damage": 11.0, "Survival": 1.0}, {"Cooldowns": 33.0}),
            visit(5, 68.0, {"Cooldowns": 9.4, "Damage": 13.0, "Survival": 1.5}, {"Cooldowns": 25.0, "Damage": 78.0}),
            visit(2, 76.0, {"Cooldowns": 6.4, "Survival": 0.7}, {"Cooldowns": 38.0, "Damage": 99.0})]


class HistoryTests(unittest.TestCase):
    def test_history_recurring(self):
        vs = history()
        h = build_history(vs)
        # Damage lost more a visit (11.25) but in 4 visits; Cooldowns and Survival lost in all 6, Cooldowns more
        self.assertEqual(h.recurring, ("Cooldowns", 6, 6, 7.9))
        self.assertEqual(plate_text(h), ("Abilities on time cost you points in 6 of 6 visits",
                                         "Average −7.9 points a visit."))
        self.assertIs(h.last, vs[0])
        self.assertIs(h.best, vs[3])
        self.assertAlmostEqual(h.trend, 75.0 - (69 + 82 + 71 + 68 + 76) / 5)
        self.assertEqual(trend_note(h), "+2 vs the 5 before")
        self.assertEqual(history_meta(h), "7 visits · 6 scored · best 82 A · last 75 B · as DPS")
        # scored visits only, oldest first; None where the category wasn't counted
        self.assertEqual(h.series, {"Cooldowns": [38.0, 25.0, 33.0, 41.0, 30.0, 23.0],
                                    "Damage": [99.0, 78.0, None, 88.0, 80.0, 97.0]})
        # a tie on the visits goes to the larger average; a tie on the best score to the earlier visit
        vs = [visit(9, 82.0, {"Survival": 3.0, "Upkeep": 1.0}), visit(5, 60.0, {"Survival": 2.0, "Upkeep": 5.0}),
              visit(2, 82.0, {"Damage": 1.0})]
        h = build_history(vs)
        self.assertEqual(h.recurring, ("Upkeep", 2, 3, 3.0))
        self.assertIs(h.best, vs[2])
        self.assertEqual(trend_note(h), "+11 vs the 2 before")
        self.assertEqual(trend_note(build_history(vs[:2])), "+22 vs the visit before")
        self.assertEqual(trend_note(build_history([visit(9, 60.0, {}), visit(5, 82.0, {})])),
                         "−22 vs the visit before")
        # nothing lost anywhere: no recurring fix, and the plate says so
        h = build_history([visit(9, 100.0, {}), visit(5, 100.0, {})])
        self.assertIsNone(h.recurring)
        self.assertEqual(plate_text(h), ("No measure cost you points on any visit", None))

    def test_history_unscored_visits(self):
        vs = visits(blackfathom())
        self.assertEqual([v.run_id for v in vs], ["1795069645-Bao", "1795069037-Bao", "1795069010-Bao", "broken"])
        full, empty, short, broken = vs
        self.assertEqual((full.score, full.grade, full.length, full.combat, full.bosses, full.deaths, full.wipes,
                          full.pieces, full.role, full.note),
                         (75.334, "B", 4185.257, 1977.628, "6 of 6", 1, 0, 2, "dps", ""))
        self.assertEqual(set(full.categories), {"Damage", "Activity", "Cooldowns", "Casting", "Survival", "Input",
                                                "Upkeep"})      # counted only: no Interrupts, Movement, Positioning
        self.assertEqual(list(full.lost)[:2], ["Cooldowns", "Survival"])
        self.assertAlmostEqual(full.lost["Cooldowns"], 10.257, places=3)
        # R10: a 2.2 s fight the card scores 58 D shows that score, but isn't compared; no combat: no score at all
        self.assertEqual((short.score, short.card_score, short.grade, short.note, short.bosses, short.categories,
                          short.lost, short.combat, short.deaths),
                         (None, 57.939, "D", "too short to compare", "—", {}, {}, 2.209, 0))
        self.assertEqual((empty.score, empty.card_score, empty.grade, empty.note, empty.bosses, empty.categories),
                         (None, None, "-", "too short to judge", "—", {}))
        self.assertEqual((broken.score, broken.card_score, broken.length, broken.deaths, broken.note),
                         (None, None, None, None, "couldn't be analysed"))
        h = build_history(vs)
        self.assertIs(h.best, full)
        self.assertIs(h.last, full)
        self.assertIsNone(h.trend)
        self.assertIsNone(trend_note(h))
        self.assertIsNone(h.recurring)
        self.assertEqual(h.series["Cooldowns"], [23.07])
        self.assertEqual(list(h.series)[:3], ["Damage", "Activity", "Cooldowns"])     # the card's order
        self.assertEqual(plate_text(h), ("One scored visit so far — come back to compare",
                                         "Visits with under 60 s in combat are too short to compare."))
        self.assertEqual(history_meta(h), "4 visits · 1 scored · best 75 B · last 75 B · as DPS")
        # a single visit
        h = build_history(visits(blackfathom()[2:3]))
        self.assertEqual(plate_text(h), ("One visit so far — come back to compare", None))
        self.assertEqual(history_meta(h), "1 visit · 1 scored · best 75 B · last 75 B · as DPS")
        # none scored
        h = build_history(visits(blackfathom()[:2]))
        self.assertEqual((h.best, h.last, h.trend, h.recurring, h.series), (None, None, None, None, {}))
        self.assertEqual(plate_text(h), ("No scored visit yet — come back after a full run",
                                         "Visits with under 60 s in combat are too short to compare."))
        self.assertEqual(history_meta(h), "2 visits · none scored")


@unittest.skipUnless(HAVE_QT, "needs PyQt6")
class HistoryTabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_dungeon_page_tabs_and_history(self):
        from PyQt6.QtCore import QPoint, Qt
        from PyQt6.QtTest import QTest
        from dips_score.ui.pages import DungeonPage
        page = DungeonPage()
        self.assertEqual([page.tabText(i) for i in range(page.count())], ["History", "Bosses", "Records"])
        pairs = blackfathom()
        page.show_dungeon("Blackfathom Deeps", [r for r, _ in pairs], {r.id: a for r, a in pairs if a})
        tab = page.history
        self.assertEqual((tab.page.title, tab.page.sub),
                         ("Blackfathom Deeps", "4 visits · 1 scored · best 75 B · last 75 B · as DPS"))
        self.assertEqual(tab.plate.title, "One scored visit so far — come back to compare")
        self.assertFalse(tab.plate.has_button)          # no recurring fix: nowhere to go
        self.assertEqual(len(tab.measures.view.series), 7)
        page.resize(1200, 900)
        page.show()
        self.assertFalse(page.grab().isNull())          # paints
        opened = []
        page.open_run.connect(opened.append)
        t = tab.table
        top, bottom, rid = t.hits[0]
        QTest.mouseDClick(t, Qt.MouseButton.LeftButton, pos=QPoint(40, round((top + bottom) / 2)))
        top, bottom, _ = t.hits[3]
        QTest.mouseDClick(t, Qt.MouseButton.LeftButton, pos=QPoint(40, round((top + bottom) / 2)))
        self.assertEqual(opened, ["1795069645-Bao", "broken"])
        from dips_score.ui.historytab import VisitTable
        from dips_score.ui.theme import tok
        cells = [VisitTable._cells(v)[3] for v in tab.view.visits]      # the Score column
        self.assertEqual(["".join(s for s, _, _ in c) for c in cells],
                         ["75 B", "too short to judge", "58 D · too short to compare", "couldn't be analysed"])
        self.assertEqual({ink.name() for _, _, ink in cells[2]}, {tok("mu").name()})     # muted, the letter too
        for i in (1, 2):
            page.setCurrentIndex(i)
            self.assertFalse(page.grab().isNull())

    def test_best_words_keep_off_the_last(self):
        """the best's words go over its dot, under it, or stacked over the last's words; with no room, nowhere"""
        from dips_score.ui.historytab import ScoreLine
        chart = ScoreLine()
        chart.resize(760, chart.heightForWidth(760))
        chart.show()

        def at(scores: tuple) -> str | None:        # newest first
            chart.set_view(build_history([visit(26 - 2 * k, s, {}) for k, s in enumerate(scores)]))
            self.assertFalse(chart.grab().isNull())
            self.assertEqual(len(chart.last_rects), 3)     # the number, "Last …" and the trend
            r = chart.best_rect
            self.assertFalse(r is not None and any(r.adjusted(-4, -4, 4, 4).intersects(o) for o in chart.last_rects))
            return chart.best_at
        self.assertEqual(at((80.0, 82.0, 70.0)), "over")                # room over the best dot (the mock-up's)
        self.assertEqual(at((80.0, 99.0, 70.0)), "under")               # none over it, at the top
        self.assertEqual(at((80.0, 80.0) + (70.0,) * 10), "stacked")    # neighbours, level: over the last's words
        self.assertIsNone(at((97.0, 99.0) + (40.0,) * 10))              # no room anywhere: the best's dot alone

    def test_recurring_plate_opens_the_last_visit(self):
        from dips_score.ui.historytab import HistoryTab
        tab = HistoryTab()
        h = build_history(history())
        tab.show_view("Blackfathom Deeps", history_meta(h), h)
        self.assertEqual(tab.plate.title, "Abilities on time cost you points in 6 of 6 visits")
        self.assertEqual(tab.plate.body, "Average −7.9 points a visit.")
        opened = []
        tab.open_run.connect(opened.append)
        tab.plate.button.click()
        self.assertEqual(opened, ["r18"])
        tab.resize(1500, 1400)
        tab.show()
        self.assertFalse(tab.grab().isNull())
        tab.resize(1000, 1400)                          # narrow: labels thin out, nothing breaks
        self.assertFalse(tab.grab().isNull())


if __name__ == "__main__":
    unittest.main()
