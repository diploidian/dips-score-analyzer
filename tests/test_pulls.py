"""What the Pulls page shows (dips_score/pulls_view.py), on the real Blackfathom run's 64 pulls (copied in as a
literal) and on stubs; the page itself when PyQt6 is there:
PYTHONPATH=<folder with PyQt6> python -m unittest discover -s tests"""
import importlib.util
import os
import sys
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dips_score.pulls_view import (PullRow, build_pulls, fix_plate, pulls_view, resource_at,  # noqa: E402
                                   safety_figures, slide_note, slide_rows)

HAVE_QT = importlib.util.find_spec("PyQt6") is not None

# Blackfathom Deeps, 18 Nov 22:27 (run 6), as dump_mock_data.py sampled it: n, at, start, end, label, boss,
# mobs, packs, extra_packs, pulled_by, you_pulled, how, length_s, gap_before_s, you_died, hp, mana
PULLS = [
    (1, "0:36", 36.2, 75.0, "Trash", False, 4, 2, 1, "Anaruz Lightborne", False, "Judgement", 33, None, False, 1.0, 1.0),
    (2, "1:43", 103.4, 116.9, "Trash", False, 1, 1, 0, "Anaruz Lightborne", False, "body pull", 12, 28, False, 1.0, 1.0),
    (3, "2:32", 152.6, 182.8, "Trash", False, 3, 2, 1, "Anaruz Lightborne", False, "Judgement", 29, 36, False, 1.0, 1.0),
    (4, "3:10", 190.1, 208.5, "Trash", False, 2, 1, 0, "Anaruz Lightborne", False, "body pull", 15, 7, False, 0.97, 0.95),
    (5, "3:46", 227.0, 258.2, "Ghamoo-ra", True, 1, 1, 0, "Anaruz Lightborne", False, "Judgement", 31, 18, False, 1.0, 1.0),
    (6, "4:38", 278.6, 336.7, "Trash", False, 4, 3, 2, "Anaruz Lightborne", False, "body pull", 49, 20, False, 0.96, 0.95),
    (7, "6:25", 385.3, 475.1, "Trash", False, 6, 4, 3, "Anaruz Lightborne", False, "Holy Strike", 90, 49, False, 1.0, 1.0),
    (8, "8:44", 524.8, 586.2, "Trash", False, 4, 3, 2, "Anaruz Lightborne", False, "Holy Strike", 60, 50, False, 1.0, 0.93),
    (9, "9:56", 596.9, 620.4, "Trash", False, 2, 1, 0, "Anaruz Lightborne", False, "melee", 22, 11, False, 1.0, 0.99),
    (10, "10:22", 622.8, 633.8, "Trash", False, 1, 1, 0, "Piraña Segundo", False, "Throw", 9, 2, False, 0.99, 0.89),
    (11, "10:35", 635.6, 648.9, "Trash", False, 1, 1, 0, "Anaruz Lightborne", False, "Judgement", 13, 2, False, 0.93, 0.98),
    (12, "10:55", 655.4, 677.8, "Trash", False, 2, 1, 0, "Anaruz Lightborne", False, "body pull", 20, 6, False, 1.0, 0.91),
    (13, "11:22", 683.0, 708.4, "Lady Sarevess", True, 1, 1, 0, "Anaruz Lightborne", False, "Judgement", 24, 5, False, 0.99, 0.99),
    (14, "12:27", 747.7, 757.1, "Trash", False, 1, 1, 0, "Bao Kahn", True, "Judgement", 9, 39, False, 1.0, 1.0),
    (15, "13:06", 786.8, 799.8, "Trash", False, 1, 1, 0, "Anaruz Lightborne", False, "body pull", 11, 30, False, 0.98, 0.86),
    (16, "14:08", 848.1, 870.6, "Trash", False, 2, 1, 0, "Anaruz Lightborne", False, "melee", 21, 48, False, 1.0, 1.0),
    (17, "14:32", 873.0, 915.8, "Trash", False, 4, 2, 1, "Anaruz Lightborne", False, "body pull", 40, 2, False, 1.0, 0.9),
    (18, "15:24", 924.8, 947.5, "Trash", False, 2, 1, 0, "Anaruz Lightborne", False, "melee", 22, 9, False, 0.96, 0.9),
    (19, "15:54", 954.9, 964.6, "Trash", False, 1, 1, 0, "Bao Kahn", True, "Judgement", 10, 7, False, 1.0, 0.65),
    (20, "16:09", 969.6, 1020.9, "Trash", False, 4, 3, 2, "Anaruz Lightborne", False, "melee", 50, 5, False, 1.0, 0.59),
    (21, "17:10", 1030.4, 1062.4, "Trash", False, 3, 1, 0, "Anaruz Lightborne", False, "Retribution Aura", 27, 10, False, 0.9, 0.44),
    (22, "17:45", 1066.0, 1081.2, "Trash", False, 1, 1, 0, "Evilguy Verybad", False, "Auto Shot", 11, 4, False, 1.0, 0.52),
    (23, "18:15", 1095.4, 1204.9, "Trash", False, 7, 4, 3, "Anaruz Lightborne", False, "melee", 105, 14, True, 1.0, 0.44),
    (24, "28:16", 1696.0, 1721.7, "Trash", False, 2, 2, 1, "Bao Kahn", True, "body pull", 26, 491, False, 1.0, 1.0),
    (25, "29:10", 1750.5, 1806.8, "Trash", False, 1, 1, 0, "Shizuka Tsuruta", False, "body pull", 56, 29, False, 1.0, 0.9),
    (26, "30:24", 1824.3, 1875.1, "Geilhast", True, 3, 2, 1, "Anaruz Lightborne", False, "Judgement of Fury", 51, 17, False, 0.99, 0.95),
    (27, "32:19", 1939.5, 1986.5, "Trash", False, 4, 1, 0, "Anaruz Lightborne", False, "melee", 41, 64, False, 1.0, 0.92),
    (28, "33:38", 2018.7, 2047.6, "Trash", False, 2, 1, 0, "Anaruz Lightborne", False, "melee", 26, 32, False, 1.0, 0.93),
    (29, "34:19", 2059.7, 2085.4, "Trash", False, 2, 1, 0, "Anaruz Lightborne", False, "melee", 23, 12, False, 1.0, 0.86),
    (30, "34:55", 2095.1, 2114.7, "Trash", False, 2, 1, 0, "Anaruz Lightborne", False, "body pull", 17, 10, False, 1.0, 0.97),
    (31, "35:28", 2128.1, 2157.9, "Trash", False, 3, 1, 0, "Anaruz Lightborne", False, "Judgement", 27, 13, False, 0.97, 0.99),
    (32, "36:24", 2184.3, 2222.2, "Trash", False, 3, 1, 0, "Evilguy Verybad", False, "Serpent Sting", 35, 26, False, 1.0, 1.0),
    (33, "37:07", 2227.1, 2251.6, "Trash", False, 2, 1, 0, "Anaruz Lightborne", False, "body pull", 24, 5, False, 1.0, 0.85),
    (34, "37:35", 2255.1, 2285.8, "Trash", False, 2, 1, 0, "Bao Kahn", True, "Judgement", 31, 4, False, 0.97, 0.86),
    (35, "38:34", 2314.8, 2360.2, "Trash", False, 4, 2, 1, "Anaruz Lightborne", False, "melee", 33, 29, False, 1.0, 0.93),
    (36, "40:06", 2406.9, 2445.6, "Trash", False, 3, 2, 1, "Anaruz Lightborne", False, "Judgement", 34, 47, False, 1.0, 1.0),
    (37, "41:02", 2462.4, 2500.6, "Trash", False, 3, 1, 0, "Anaruz Lightborne", False, "Holy Strike", 35, 17, False, 1.0, 1.0),
    (38, "42:06", 2526.7, 2551.0, "Trash", False, 2, 1, 0, "Anaruz Lightborne", False, "Judgement", 22, 26, False, 1.0, 1.0),
    (39, "42:46", 2566.9, 2588.9, "Trash", False, 2, 1, 0, "Anaruz Lightborne", False, "body pull", 21, 16, False, 1.0, 0.96),
    (40, "43:12", 2592.6, 2626.8, "Trash", False, 3, 1, 0, "Bao Kahn", True, "Judgement", 34, 4, False, 1.0, 1.0),
    (41, "43:54", 2634.5, 2649.6, "Trash", False, 1, 1, 0, "Anaruz Lightborne", False, "melee", 12, 8, False, 0.96, 1.0),
    (42, "44:20", 2660.3, 2694.8, "Trash", False, 3, 1, 0, "Anaruz Lightborne", False, "Consecration", 32, 11, False, 1.0, 0.92),
    (43, "45:09", 2709.9, 2738.8, "Trash", False, 3, 1, 0, "Anaruz Lightborne", False, "body pull", 29, 15, False, 1.0, 1.0),
    (44, "45:47", 2747.8, 2829.3, "Trash", False, 6, 2, 1, "Anaruz Lightborne", False, "Judgement", 81, 9, False, 0.92, 0.87),
    (45, "47:51", 2871.1, 2898.8, "Trash", False, 2, 2, 1, "Anaruz Lightborne", False, "melee", 26, 42, False, 1.0, 1.0),
    (46, "48:34", 2914.2, 2931.3, "Trash", False, 2, 2, 1, "Anaruz Lightborne", False, "body pull", 16, 15, False, 0.97, 0.85),
    (47, "48:53", 2933.7, 2972.8, "Trash", False, 2, 2, 1, "Shizuka Tsuruta", False, "Shadow Word: Pain", 39, 2, False, 0.91, 1.0),
    (48, "51:17", 3077.2, 3105.3, "Trash", False, 2, 2, 1, "Anaruz Lightborne", False, "body pull", 27, 104, False, 1.0, 1.0),
    (49, "52:05", 3125.9, 3184.7, "Trash", False, 4, 2, 1, "Shizuka Tsuruta", False, "Shadow Word: Pain", 59, 21, False, 1.0, 0.87),
    (50, "53:59", 3239.2, 3262.2, "Trash", False, 1, 1, 0, "Anaruz Lightborne", False, "Judgement", 22, 54, False, 1.0, 1.0),
    (51, "54:28", 3268.3, 3294.4, "Trash", False, 2, 1, 0, "Anaruz Lightborne", False, "melee", 26, 6, False, 1.0, 0.71),
    (52, "55:02", 3302.9, 3318.8, "Trash", False, 1, 1, 0, "Bao Kahn", True, "Judgement", 16, 9, False, 1.0, 0.91),
    (53, "55:24", 3324.4, 3370.1, "Twilight Lord Kelris", True, 2, 1, 0, "Anaruz Lightborne", False, "Judgement", 44, 6, False, 1.0, 0.95),
    (54, "56:41", 3401.8, 3483.7, "Trash", False, 7, 1, 0, "Anaruz Lightborne", False, "melee", 79, 32, False, 1.0, 0.96),
    (55, "58:27", 3507.5, 3539.4, "Trash", False, 2, 2, 1, "Anaruz Lightborne", False, "Judgement", 28, 24, False, 0.97, 1.0),
    (56, "59:52", 3592.1, 3609.2, "Trash", False, 10, 2, 1, "Anaruz Lightborne", False, "body pull", 16, 53, False, 1.0, 1.0),
    (57, "60:21", 3621.8, 3652.7, "Trash", False, 2, 2, 1, "Anaruz Lightborne", False, "body pull", 31, 13, False, 1.0, 0.92),
    (58, "61:08", 3668.2, 3686.5, "Trash", False, 1, 1, 0, "Anaruz Lightborne", False, "melee", 18, 15, False, 1.0, 0.91),
    (59, "61:33", 3693.6, 3745.8, "Aku'mai", True, 1, 1, 0, "Anaruz Lightborne", False, "Judgement", 50, 7, False, 1.0, 1.0),
    (60, "63:27", 3807.6, 3846.2, "Trash", False, 2, 2, 1, "Anaruz Lightborne", False, "body pull", 26, 62, False, 0.57, 1.0),
    (61, "64:16", 3856.2, 3874.3, "Trash", False, 1, 1, 0, "Anaruz Lightborne", False, "Judgement", 7, 10, False, 0.93, 0.92),
    (62, "64:45", 3885.2, 3904.8, "Old Serra'kis", True, 1, 1, 0, "Anaruz Lightborne", False, "Judgement", 20, 11, False, 1.0, 1.0),
    (63, "67:29", 4049.7, 4071.3, "Trash", False, 2, 1, 0, "Anaruz Lightborne", False, "Consecration", 7, 145, False, 1.0, 1.0),
    (64, "69:28", 4168.3, 4185.2, "Trash", False, 0, 0, 0, None, False, "", 17, 97, False, 1.0, 1.0),
]


def info(guid, hp, power_type, power, max_power=100):
    return SimpleNamespace(guid=guid, max_hp=100, hp_pct=hp, power_type=power_type, power=power,
                           max_power=max_power)


def stub_run(deaths):
    """two pulls with no health or mana samples: you pull the first, the tank the second (a pack joins it)"""
    def pull(start, end, *packs):
        return SimpleNamespace(start=start, packs=list(packs), enemies=[e for pk in packs for e in pk.enemies],
                               fight=SimpleNamespace(start=start, end=end, label="Trash", boss=None,
                                                     duration=end - start))

    def pack(start, puller, extra):
        return SimpleNamespace(start=start, puller=puller, how="melee", extra=extra, enemies=["mob", "mob"])

    return SimpleNamespace(
        pulls=[pull(10.0, 40.0, pack(10.0, "me", False)),
               pull(60.0, 95.0, pack(60.0, "tank", False), pack(70.0, "tank", True))],
        deaths=deaths, roster={"me": SimpleNamespace(name="Bao Kahn"), "tank": SimpleNamespace(name="Anaruz")},
        data=SimpleNamespace(events=[], player_guid="me", start=datetime(2026, 11, 18, 22, 27)))


class PullsViewTests(unittest.TestCase):
    def test_resource_at(self):
        events = [SimpleNamespace(ts=1.0, info=info("me", 0.9, 0, 50)),
                  SimpleNamespace(ts=2.0, info=info("me", 0.8, 1, 20)),     # rage: not mana
                  SimpleNamespace(ts=3.0, info=info("tank", 0.1, 0, 1)),     # someone else
                  SimpleNamespace(ts=4.0, info=None),
                  SimpleNamespace(ts=9.0, info=info("me", 0.2, 0, 10))]
        self.assertEqual(resource_at(events, "me", 0.5), (None, None))
        self.assertEqual(resource_at(events, "me", 5.0), (0.8, 0.5))      # the last mana sample, before the rage one
        self.assertEqual(resource_at(events[1:2], "me", 5.0), (0.8, None))
        self.assertEqual(resource_at(events, "me", 9.0), (0.2, 0.1))      # at t counts

    def test_pulls_blackfathom(self):
        rows = [PullRow(*r) for r in PULLS]
        v = pulls_view(rows)
        self.assertEqual((v.total, v.fix.at), (64, "18:15"))
        self.assertEqual((v.under_half_hp, v.lowest_hp), (0, (0.57, "63:27")))
        self.assertEqual((v.under_half_mana, v.joined), (["17:10", "18:15"], 22))
        self.assertEqual(v.you_pulled, ["12:27", "15:54", "28:16", "37:35", "43:12", "55:02"])
        self.assertEqual(v.breaks, [("20:04", "28:16", 8)])
        self.assertEqual((v.pullers[0], v.pullers[-1], sum(n for _, n in v.pullers)),
                         (("Anaruz Lightborne", 51), (None, 1), 64))
        # the slide as the rule reads (each pull lower than the one before, under 30 s apart): 17:45 (52%) comes
        # up from 17:10 (44%), so the run is 15:24 to 17:10, not the mock-up's five pulls to 18:15
        self.assertEqual(v.slide, (0.9, 0.44, 4, "15:24", "17:10"))
        self.assertEqual(slide_note(slide_rows(rows)), "15:24 to 17:10: four pulls, gaps of 5–10 s, mana 90% to 44%")
        self.assertEqual(v.verdict, "You never entered a pull under 50% health. Mana slid from 90% to 44% over four "
                                    "quick pulls, and the 18:15 pull — three packs joined mid-fight — is where you died.")
        self.assertEqual(fix_plate(v.fix), ("18:15 · 105 s · 4 packs, 3 joined mid-fight", "44% mana",
                                            "when you entered · you died",
                                            "Rest when mana is under 50% before the next pull"))
        self.assertEqual(safety_figures(v), [
            ("0", "entered under 50% health", "lowest was 57%, at 63:27"),
            ("2", "entered under 50% mana", "17:10 and 18:15, both at 44%"),
            ("22", "pulls had packs join mid-fight", "3 joined the 18:15 pull"),
            ("6", "you pulled", "12:27, 15:54, 28:16, 37:35, 43:12, 55:02")])

    def test_pulls_without_resources(self):
        v = build_pulls(stub_run([SimpleNamespace(guid="me", t=80.0), SimpleNamespace(guid="tank", t=20.0)]))
        self.assertEqual([(r.at, r.hp, r.mana, r.pulled_by, r.you_pulled, r.extra_packs, r.you_died, r.gap_before_s)
                          for r in v.rows],
                         [("0:10", None, None, "Bao Kahn", True, 0, False, None),
                          ("1:00", None, None, "Anaruz", False, 1, True, 20)])
        self.assertEqual([r.died for r in v.rows], [["Anaruz"], ["Bao"]])   # everyone, by first name
        self.assertEqual((v.fix.at, v.lowest_hp, v.under_half_mana, v.slide), ("1:00", None, [], None))
        self.assertEqual(v.verdict, "The 1:00 pull — one pack joined mid-fight — is where you died.")
        self.assertEqual(fix_plate(v.fix), ("1:00 · 35 s · 2 packs, 1 joined mid-fight", None, "you died", None))
        self.assertEqual([n for n, _, _ in safety_figures(v)], ["–", "–", "1", "1"])
        quiet = build_pulls(stub_run([]))
        self.assertIsNone(quiet.fix)
        self.assertNotIn("50% health", quiet.verdict)
        self.assertEqual(fix_plate(None), ("No risky pulls", None, None, None))
        self.assertEqual(pulls_view([]).verdict, "No pulls in this run.")


@unittest.skipUnless(HAVE_QT, "needs PyQt6")
class PullsPageTests(unittest.TestCase):
    def test_page_paints_and_picks(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])  # noqa: F841 (kept alive for the page)
        from dips_score.ui.pulls import PullsTab
        tab = PullsTab()
        tab.resize(1200, 900)
        v = pulls_view([PullRow(*r) for r in PULLS])
        tab.show_view(v, "Blackfathom Deeps", "Wed 18 Nov 22:27 · 69:45 long", 4185.0)
        self.assertEqual(tab.drawer.label, "ALL PULLS (64)")
        self.assertEqual(tab.table.rowCount(), 64)
        self.assertEqual((tab.table.horizontalHeaderItem(10).text(), tab.table.item(0, 10).text()), ("Died", "—"))
        self.assertTrue(tab.drawer.body.isHidden())         # the drawer starts shut
        shown, zoomed = [], []
        tab.show_me.connect(lambda a, b: shown.append((a, b)))
        tab.zoom.connect(lambda a, b: zoomed.append((a, b)))
        tab.plate.button.click()                            # Show this pull: the 18:15 pull
        self.assertEqual(shown, [(1092.4, 1207.9)])
        tab.drawer.flip()
        tab.table.selectRow(1)                              # a row picked: the timeline readies there
        self.assertEqual(zoomed, [(100.4, 119.9)])
        self.assertFalse(tab.grab().isNull())
        tab.show_view(pulls_view([]), "Nothing", "", 0.0)   # no pulls: no crash
        self.assertFalse(tab.grab().isNull())

    def test_bubble_click_opens_its_row(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtCore import QPoint
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])  # noqa: F841
        from dips_score.ui.pulls import LANE, SECTION_H, PullsTab
        tab = PullsTab()
        tab.resize(1200, 900)
        v = pulls_view([PullRow(*r) for r in PULLS])
        tab.show_view(v, "Blackfathom Deeps", "", 4185.0)
        self.assertIsNone(tab.safety.tag)
        tr = tab.track
        r = v.rows[5]
        centre = QPoint(round(tr._x(r.start, tr.width())), SECTION_H + LANE)
        self.assertEqual(tr._hit(centre), 5)
        self.assertIsNone(tr._hit(QPoint(centre.x(), SECTION_H + LANE + 60)))
        zoomed = []
        tab.zoom.connect(lambda a, b: zoomed.append((a, b)))
        tr.picked.emit(5)
        self.assertTrue(tab.drawer.open)
        self.assertEqual(tab.table.currentRow(), 5)
        self.assertEqual(zoomed, [(r.start - 3, r.end + 3)])
        self.assertEqual(tr.sel, 5)
        tr.picked.emit(5)       # the same bubble again (the timeline may have moved): readied again
        self.assertEqual(zoomed, [(r.start - 3, r.end + 3)] * 2)
        tab.show_view(v, "Blackfathom Deeps", "", 4185.0)
        self.assertIsNone(tr.sel)


if __name__ == "__main__":
    unittest.main()
