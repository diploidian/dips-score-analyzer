"""The dungeon page: dungeon_view.py (no Qt), and its widgets in ui/historytab.py, ui/bossestab.py and
ui/recordstab.py (skipped without PyQt6: PYTHONPATH=<folder with PyQt6> python -m unittest discover -s tests).

R2: the cards below are the real Blackfathom Deeps visits' (18 Nov 22:16, 22:17 and 22:27), as literals, and so are
22:27's bosses and fights (from group-data.json)."""
import importlib.util
import os
import sys
import unittest
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dips_score.dungeon_view import (TOO_SHORT, UNJUDGED, Record, Visit, bosses_text, build_bosses,  # noqa: E402
                                     build_history, build_records, history_meta, plate_text, records_text,
                                     trend_note, visits)
from dips_score.model.run import Fight  # noqa: E402
from dips_score.scoring.score import Category, Scorecard, grade  # noqa: E402

HAVE_QT = importlib.util.find_spec("PyQt6") is not None
ME = "Player-5826-0217F1D2"
TODAY = date(2026, 11, 18)


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


def card(total: float, lost: dict | None = None) -> Scorecard:
    """a card scoring total whose points_lost() is lost: each lost category weighs 10 of the 100"""
    cats = [Category(n, 100 - 10 * p, 10, "") for n, p in (lost or {}).items()]
    return Scorecard(total, grade(total), "dps", cats + [Category("Input", 100.0, 100 - 10 * len(cats), "")])


def fight(at: float, length: float, score: float, boss=None, damage=None, share=None, lost=None, killed=True):
    """a fight's result: its start and length in the run's seconds; damage and share: yours"""
    return SimpleNamespace(fight=Fight(at, at + length, boss, None, killed if boss else None), card=card(score, lost),
                           damage=None if damage is None else (damage, share))


# 22:27's six bosses: start, length, score, your damage and its share of an even split, the points lost
BOSSES = [fight(227, 31, 85.5, "Ghamoo-ra", 1087, 1.06, {"Damage": 8.0, "Upkeep": 6.5}),
          fight(683, 24.4, 100.0, "Lady Sarevess", 2071, 1.5),
          fight(1824, 51, 98.7, "Geilhast", 3550, 1.54, {"Casting": 1.3}),
          fight(3326, 44, 90.5, "Twilight Lord Kelris", 2664, 1.2, {"Activity": 4.0, "Damage": 2.8, "Casting": 1.9}),
          fight(3695, 50, 99.1, "Aku'mai", 3256, 1.5, {"Survival": 0.6, "Upkeep": 0.3}),
          fight(3885, 20, 98.4, "Old Serra'kis", 1373, 1.33, {"Upkeep": 1.6})]
# and its fights from 10:24 to 15:54 round Lady Sarevess: 11:23 to 15:25, six, is its longest run scoring 90 or more
TRASH = [fight(624, 9, 100), fight(635, 13, 97), fight(657, 20, 86), fight(747, 9, 93), fight(788, 11, 97),
         fight(849, 21, 97), fight(875, 40, 99), fight(925, 22, 99), fight(954, 10, 81)]


def run(rid: str, when: datetime, pieces: int = 1):
    return SimpleNamespace(id=rid, start_time=when, parts=[rid] * pieces)


def analysed(card, duration, combat, bosses=(0, 0), mine=0, others=0, wipes=0, kills=0, fights=()):
    return SimpleNamespace(card=card, data=SimpleNamespace(duration=duration, player_guid=ME),
                           metrics=SimpleNamespace(combat_time=combat, kills=kills),
                           summary=SimpleNamespace(bosses_killed=bosses[0], bosses=bosses[1]),
                           deaths=[SimpleNamespace(guid=ME)] * mine + [SimpleNamespace(guid="Player-2")] * others,
                           wipes=[None] * wipes, fights=list(fights))


def blackfathom():
    """the three real visits, oldest first (as the rail lists them, newest first, reversed), and one whose analysis
    failed"""
    return [(run("1795069010-Bao", datetime(2026, 11, 18, 22, 16, 50)), analysed(card_2216(), 16.092, 2.209)),
            (run("1795069037-Bao", datetime(2026, 11, 18, 22, 17, 17)),
             analysed(Scorecard(0.0, "-", "dps", note="no combat in this run, nothing to score"), 20.805, 0)),
            (run("1795069645-Bao", datetime(2026, 11, 18, 22, 27, 25), pieces=2),
             analysed(card_2227(), 4185.257, 1977.628, (6, 6), mine=1, others=3, kills=31,
                      fights=sorted(BOSSES + TRASH, key=lambda fr: fr.fight.start))),
            (run("broken", datetime(2026, 11, 17, 20, 0)), None)]


def records_history(best: float = 82.0):
    """made up round the real 22:27: 8 Nov, left after the trash (faster, so not a clear); 11 Nov, a clear scoring
    best; 17 Nov, too short to compare (its big numbers never count); then 22:27"""
    left = analysed(card(71.0), 1000, 600, kills=27, fights=[
        fight(0, 30, 95, damage=2100, share=1.0), fight(100, 20, 92), fight(200, 20, 91), fight(300, 20, 95),
        fight(400, 20, 70)])
    clear = analysed(card(best, {"Cooldowns": 6.2}), 3490, 1720, (6, 6), kills=25, fights=[
        fight(0, 30, 95, "Ghamoo-ra"), fight(100, 25, 95, "Lady Sarevess", 2000, 1.4), fight(200, 30, 95, "Geilhast"),
        fight(300, 30, 95, "Twilight Lord Kelris"), fight(400, 30, 95, "Aku'mai"), fight(500, 30, 50, "Old Serra'kis")])
    short = analysed(card(64.0), 45, 40, kills=99, fights=[fight(0, 40, 99, damage=20000, share=3.0)])
    return [(run("r8", datetime(2026, 11, 8, 21, 0)), left), (run("r11", datetime(2026, 11, 11, 21, 0)), clear),
            (run("r17", datetime(2026, 11, 17, 21, 0)), short), blackfathom()[2]]


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


class BossesRecordsTests(unittest.TestCase):
    def test_bosses_weakest(self):
        pairs = blackfathom()
        pairs[0][1].fights = [fight(1, 2.2, 20.0, "Ghamoo-ra", 50, 1.0)]     # R10: too short to compare, never counts
        rows, weakest, average = build_bosses(pairs, TODAY)
        self.assertEqual([r.name for r in rows], ["Ghamoo-ra", "Lady Sarevess", "Geilhast", "Twilight Lord Kelris",
                                                  "Aku'mai", "Old Serra'kis"])
        self.assertIs(weakest, rows[0])
        self.assertEqual((weakest.today, weakest.grade, weakest.kill_s, round(weakest.dps), weakest.share,
                          weakest.lost, weakest.history, weakest.best, weakest.fight),
                         (85.5, "A", 31, 35, 1.06, [("Damage", 8.0), ("Upkeep", 6.5)], [85.5], (85.5, "today"),
                          (227, 258)))
        self.assertEqual(round(average), 95)
        self.assertAlmostEqual(average, (85.5 + 100 + 98.7 + 90.5 + 99.1 + 98.4) / 6)
        self.assertEqual(bosses_text(rows, weakest, "today"), (
            "average boss score today · 6 of 6 killed",
            "Your weakest boss is Ghamoo-ra (86 A), the first one: it lost 8.0 points on Damage and 6.5 on Upkeep. "
            "Every other boss was 90 or better."))
        # an earlier visit: Kelris a wipe, Aku'mai not reached, and a boss only met then: it slots in after the boss
        # met just before it
        pairs.append((run("r11", datetime(2026, 11, 11, 21, 0)), analysed(card(82.0), 3490, 1720, kills=25, fights=[
            fight(200, 30, 88.0, "Ghamoo-ra"), fight(600, 30, 96.0, "Lady Sarevess"),
            fight(900, 30, 70.0, "Baron Aquanis"), fight(3300, 60, 40.0, "Twilight Lord Kelris", killed=False),
            fight(3800, 30, 97.0, "Old Serra'kis")])))
        rows, weakest, _ = build_bosses(pairs, TODAY)
        by = {r.name: r for r in rows}
        self.assertEqual(list(by), ["Ghamoo-ra", "Lady Sarevess", "Baron Aquanis", "Geilhast", "Twilight Lord Kelris",
                                    "Aku'mai", "Old Serra'kis"])
        self.assertIs(weakest, by["Ghamoo-ra"])
        self.assertEqual((by["Ghamoo-ra"].history, by["Ghamoo-ra"].best), ([88.0, 85.5], (88.0, "11 Nov")))
        self.assertEqual((by["Lady Sarevess"].history, by["Lady Sarevess"].best), ([96.0, 100.0], (100.0, "today")))
        self.assertEqual((by["Twilight Lord Kelris"].history, by["Twilight Lord Kelris"].missed),
                         ([None, 90.5], ["wipe", ""]))
        self.assertEqual((by["Aku'mai"].history, by["Aku'mai"].missed), ([None, 99.1], ["not reached", ""]))
        b = by["Baron Aquanis"]
        self.assertEqual((b.today, b.grade, b.kill_s, b.dps, b.lost, b.history, b.missed, b.best, b.fight),
                         (None, "-", None, None, [], [70.0, None], ["", "not reached"], (70.0, "11 Nov"), None))
        self.assertEqual(bosses_text(rows, weakest, "18 Nov")[0],
                         "average boss score on 18 Nov · 6 of 7 killed")
        self.assertEqual(build_bosses(blackfathom()[:2]), ([], None, None))       # none scored
        # met first on an earlier visit, before the last visit's first boss: it leads
        pairs = [blackfathom()[2], (run("r8", datetime(2026, 11, 8, 21, 0)), analysed(card(70.0), 3600, 1800, fights=[
            fight(50, 20, 80.0, "Lorgus Jett"), fight(200, 30, 90.0, "Ghamoo-ra")]))]
        self.assertEqual([r.name for r in build_bosses(pairs, TODAY)[0]][:3],
                         ["Lorgus Jett", "Ghamoo-ra", "Lady Sarevess"])

    def test_bosses_killed(self):
        """a boss counts as killed only when the log says so: not when that's unknown, scored or not"""
        pairs = blackfathom()
        a = pairs[2][1]
        unscored = Scorecard(0.0, "-", "dps", note="nothing counted could be judged")
        swap = {"Geilhast": fight(1824, 51, 98.7, "Geilhast", killed=None),       # unknown, scored
                "Aku'mai": SimpleNamespace(fight=Fight(3695, 3745, "Aku'mai", None, True), card=unscored, damage=None),
                "Old Serra'kis": SimpleNamespace(fight=Fight(3885, 3905, "Old Serra'kis", None, None), card=unscored,
                                                 damage=None)}                  # unknown, not scored
        a.fights = [swap.get(fr.fight.boss, fr) for fr in a.fights]
        rows, weakest, _ = build_bosses(pairs, TODAY)
        by = {r.name: r for r in rows}
        self.assertEqual([(by[n].today, by[n].missed[-1], by[n].killed)
                          for n in ("Geilhast", "Aku'mai", "Old Serra'kis")],
                         [(98.7, "", False), (None, "not scored", True), (None, "not scored", False)])
        self.assertEqual(bosses_text(rows, weakest, "today")[0], "average boss score today · 4 of 6 killed")

    def test_records_new_today(self):
        records, _ = build_records(records_history(), TODAY)
        self.assertEqual(records, [
            Record("Best score", "82 A", "11 Nov", "75 B", "7 short · within reach", False),
            Record("Fastest clear", "58:10", "11 Nov", "69:45", "11:35 behind", False, "whole visit, entry to exit"),
            Record("Least time in combat", "28:40", "11 Nov", "32:57", "4:17 behind", False),
            Record("Most killing blows", "31", "today", "31", "new record today · was 27 · 8 Nov", True),
            Record("Highest DPS in a fight", "85 DPS", "today", "85", "new record today · was 80 · 11 Nov", True,
                   "Lady Sarevess, 24s at 11:23"),
            Record("Longest S streak", "6 fights", "today", "6", "new record today · was 5 · 11 Nov", True,
                   "fights scoring 90+ in a row, 11:23 to 15:25"),
            Record("Deathless visits", "2 of 3", "last 11 Nov", "1 death", "not this visit", False,
                   "visits with no deaths")])
        # the last visit on another day: "new record", its day for "today"
        records, _ = build_records(records_history(), date(2026, 11, 20))
        self.assertEqual((records[3].when, records[3].status), ("18 Nov", "new record · was 27 · 8 Nov"))
        # the last visit the best: a new record, so nothing to reach
        records, within = build_records(records_history(best=70.0), TODAY)
        self.assertEqual(records[0],
                         Record("Best score", "75 B", "today", "75 B", "new record today · was 71 B · 8 Nov", True))
        self.assertIsNone(within)
        h = build_history(visits(records_history(best=70.0)))
        self.assertEqual(records_text(h, within, "today"), ("Today's 75 B is your best score here.",
                                                            "New best today: 75 B — come back to beat it", None))

    def test_records_within_reach(self):
        records, within = build_records(records_history(), TODAY)
        # R9: 75.3 + 10.3 (Cooldowns, the last visit's top points lost) beats 82; +7 is ceil(82 − 75.3); the
        # category by its display name, as History and Bosses have it
        self.assertEqual(within, ("Best 82 A", "+7 needed — your Abilities on time fix is worth 10.3"))
        h = build_history(visits(records_history()))
        self.assertEqual(records_text(h, within, "today"), (
            "Today's 75 B is 7 points short of your best. Your Abilities on time fix alone (−10.3) would have "
            "beaten it.", "Best 82 A: +7 needed — your Abilities on time fix is worth 10.3", None))
        # 75.3 + 10.3 doesn't beat 86: out of reach
        records, within = build_records(records_history(best=86.0), TODAY)
        self.assertIsNone(within)
        self.assertEqual(records[0].status, "11 short")
        h = build_history(visits(records_history(best=86.0)))
        self.assertEqual(records_text(h, within, "18 Nov"), (
            "The 18 Nov visit's 75 B is 11 points short of your best.",
            "Best 86 A: +11 needed — more than any one fix is worth", None))

    def test_records_single_visit(self):
        records, within = build_records(blackfathom(), TODAY)       # one scored visit; two too short; one broken
        self.assertIsNone(within)
        self.assertEqual({r.status for r in records}, {"first visit"})
        self.assertFalse(any(r.new_today for r in records))
        self.assertEqual([(r.name, r.value, r.when, r.today) for r in records], [
            ("Best score", "75 B", "today", "75 B"), ("Fastest clear", "69:45", "today", "69:45"),
            ("Least time in combat", "32:57", "today", "32:57"), ("Most killing blows", "31", "today", "31"),
            ("Highest DPS in a fight", "85 DPS", "today", "85"), ("Longest S streak", "6 fights", "today", "6"),
            ("Deathless visits", "0 of 1", "–", "1 death")])
        self.assertEqual((records[4].note, records[5].note),
                         ("Lady Sarevess, 24s at 11:23", "fights scoring 90+ in a row, 11:23 to 15:25"))
        h = build_history(visits(blackfathom()))
        self.assertEqual(records_text(h, within, "today"), (
            "Every record here is from today's visit, your only scored one.", "First visit — records start here",
            "Visits with under 60 s in combat are too short to compare."))
        self.assertEqual(build_records(blackfathom()[:2]), ([], None))       # none scored
        # a streak of one fight, and of none
        for scores, want in (((95, 50), "1 fight"), ((50, 60), "none yet")):
            one = [(run("r1", datetime(2026, 11, 18, 21, 0)), analysed(card(75.0), 3600, 1800, fights=[
                fight(100 * k, 20, s) for k, s in enumerate(scores)]))]
            self.assertEqual(build_records(one, TODAY)[0][5].value, want)
        self.assertEqual(records_text(build_history(visits(blackfathom()[:2])), None, "today")[:2],
                         ("No scored visit yet, so no records.", "No scored visit yet — come back after a full run"))


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

    @staticmethod
    def dungeon(pairs):
        from dips_score.ui.pages import DungeonPage
        page = DungeonPage()
        page.show_dungeon("Blackfathom Deeps", [r for r, _ in pairs], {r.id: a for r, a in pairs if a})
        page.resize(1500, 1100)
        page.show()
        return page

    def test_bosses_tab(self):
        page = self.dungeon(blackfathom())
        tab = page.bosses
        self.assertEqual((tab.page.title, tab.hero.big, tab.hero.suffix), ("Blackfathom Deeps", "95", "S"))
        self.assertEqual((tab.plate.title, tab.plate.price, tab.plate.caption, tab.plate.body),
                         ("Ghamoo-ra · 86 A", "−8.0 points", "Damage · then −6.5 Upkeep", "31 s · 35 DPS"))
        self.assertEqual(tab.table.heads[5], "Score by visit")      # one scored visit: no history yet
        shown = []
        page.show_fight.connect(lambda *a: shown.append(a))
        tab.plate.button.click()
        self.assertEqual(shown, [("1795069645-Bao", 224.0, 261.0)])     # that visit, at Ghamoo-ra (3 s either side)
        page.setCurrentWidget(tab)
        self.assertFalse(page.grab().isNull())
        self.assertLess(tab.route.circled.center().x(), tab.route.width() / 6)     # the weakest: the first station
        page = self.dungeon(blackfathom()[:2])          # none scored: nothing to show but the head and the plate
        self.assertEqual((page.bosses.hero.big, page.bosses.plate.has_button), ("–", False))
        self.assertTrue(page.bosses.route.isHidden() and page.bosses.table.isHidden())
        page.setCurrentWidget(page.bosses)
        self.assertFalse(page.grab().isNull())

    def test_records_tab(self):
        from PyQt6.QtCore import QPoint, Qt
        from PyQt6.QtTest import QTest
        page = self.dungeon(records_history())
        tab = page.records
        self.assertEqual((tab.hero.big, tab.hero.suffix), ("82", "A"))
        self.assertEqual(tab.plate.title, "Best 82 A: +7 needed — your Abilities on time fix is worth 10.3")
        t, b, f = tab.plate.scale
        self.assertEqual((t, b, round(f, 3)), (75.334, 82.0, 85.591))
        opened = []
        page.open_run.connect(opened.append)
        tab.plate.button.click()
        self.assertEqual(opened, ["1795069645-Bao"])
        page.setCurrentWidget(tab)
        self.assertFalse(page.grab().isNull())
        self.assertEqual(tab.board.circled, 3)      # three new records: only the first in board order is circled
        QTest.mouseClick(tab.board, Qt.MouseButton.LeftButton, pos=QPoint(60, round(tab.board.link_y + 20)))
        self.assertIs(page.currentWidget(), page.bosses)        # the Bosses row
        page = self.dungeon(blackfathom())              # one scored visit
        tab = page.records
        self.assertEqual((tab.plate.title, tab.plate.has_button, tab.plate.scale),
                         ("First visit — records start here", False, None))
        page.setCurrentWidget(tab)
        self.assertFalse(page.grab().isNull())
        self.assertIsNone(tab.board.circled)


if __name__ == "__main__":
    unittest.main()
