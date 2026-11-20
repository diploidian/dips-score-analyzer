"""What the Spells page shows (dips_score/spells_view.py), on the real Blackfathom run's 25 spell rows (copied in as a
literal) and on stubs; the page itself when PyQt6 is there:
PYTHONPATH=<folder with PyQt6> python -m unittest discover -s tests"""
import importlib.util
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dips_score.model.casts import SpellRow  # noqa: E402
from dips_score.spells_view import merge_by_name, spells_view  # noqa: E402

HAVE_QT = importlib.util.find_spec("PyQt6") is not None

# Blackfathom Deeps, 18 Nov 22:27 (run 6), your spell_table as dump_mock_data.py saw it: spell, casts, failed, damage,
# healing, overheal, hits, crits
SPELLS = [
    ("Melee", 0, 0, 52475, 0, 0, 458, 43),
    ("Seal of Command", 138, 10, 16332, 0, 0, 133, 15),
    ("Judgement of Command", 0, 0, 12967, 0, 0, 150, 7),
    ("Holy Strike", 179, 109, 11386, 0, 0, 171, 15),
    ("Consecration", 0, 0, 10272, 0, 0, 1600, 107),
    ("Touch of the Grave", 0, 0, 6418, 2683, 2627, 182, 0),
    ("Holy Light", 7, 5, 0, 1833, 316, 7, 0),
    ("Cannibalize", 0, 0, 0, 100, 0, 1, 0),
    ("Judgement", 206, 39),
    ("Seal of Command", 91, 22),
    ("Consecration", 90, 16),
    ("Seal of the Crusader", 61, 1),
    ("Blessing of Freedom", 12, 1),
    ("Blessing of Might", 10, 0),
    ("Blessing of Wisdom", 4, 0),
    ("Blessing of Kings", 1, 0),
    ("Restore Mana", 1, 0),
    ("Divine Protection", 1, 0),
    ("Hammer of Justice", 1, 0),
    ("Redemption", 1, 0),
    ("Retribution Aura", 1, 0),
    ("Sharpen Blade II", 1, 0),
    ("Will of the Forsaken", 1, 0),
    ("Cannibalize", 1, 0),
    ("Exorcism", 0, 1),
]
COMBAT = 1977.6     # a.metrics.combat_time, seconds
# a.cooldowns.rows on the same run: name, free seconds, casts missed, damage lost
COOLDOWNS = [SimpleNamespace(name="Consecration", free=75.2, missed=8.44, lost=1177.22),
             SimpleNamespace(name="Judgement", free=20.2, missed=2.52, lost=166.54),
             SimpleNamespace(name="Holy Strike", free=7.2, missed=0.72, lost=51.03)]
WHERE = {"Consecration": (382.3, 478.1), "Judgement": (3123.1, 3170.4)}    # the fight where each cost most


def rows(spec) -> list[SpellRow]:
    return [SpellRow(None, name, *nums) for name, *nums in spec]


class SpellsViewTests(unittest.TestCase):
    def test_merge_by_name(self):
        raw = rows(SPELLS)
        merged = merge_by_name(raw)
        by = {r.spell: r for r in merged}
        self.assertEqual(len(merged), 21)
        soc = by["Seal of Command"]        # two rows of one name: summed
        self.assertEqual((soc.casts, soc.failed, soc.damage, soc.hits, soc.crits), (229, 32, 16332, 133, 15))
        self.assertEqual(raw[1].casts, 138)                 # the input rows are left as they were
        jd = by["Judgement"]               # its damage comes in as Judgement of Command
        self.assertEqual((jd.casts, jd.failed, jd.damage, jd.hits, jd.crits), (206, 39, 12967, 150, 7))
        self.assertEqual(jd.note, "damage from Judgement of Command")
        self.assertNotIn("Judgement of Command", by)
        tg = by["Touch of the Grave"]      # no "Touch" pressed: it stays
        self.assertEqual((tg.damage, tg.healing, tg.note), (6418, 2683, None))
        self.assertEqual((by["Cannibalize"].casts, by["Cannibalize"].healing), (1, 100))
        two = merge_by_name(rows([("Judgement", 20, 0), ("Judgement of Command", 0, 0, 900, 0, 0, 9, 1),
                                  ("Judgement of Righteousness", 0, 0, 400, 0, 0, 4, 0)]))
        self.assertEqual([(r.spell, r.damage, r.note) for r in two],
                         [("Judgement", 1300, "damage from Judgement of Command and Judgement of Righteousness")])

    def test_spells_blackfathom(self):
        v = spells_view(rows(SPELLS), COMBAT, COOLDOWNS, where=WHERE)
        by = {r.name: r for r in v.all_rows}
        self.assertEqual(len(v.all_rows), 21)
        self.assertEqual((v.total_damage, round(v.dps)), (109850, 56))
        hs = by["Holy Strike"]
        self.assertEqual((hs.refused, hs.casts + hs.refused, round(hs.refused_share, 2)), (109, 288, 0.38))
        self.assertAlmostEqual(by["Melee"].share + by["Seal of Command"].share, 0.63, delta=0.01)
        self.assertEqual((by["Seal of Command"].casts, by["Seal of Command"].refused), (229, 32))
        self.assertEqual((f"{by['Seal of Command'].per_min:.1f}", f"{by['Judgement'].crit:.0%}"), ("6.9", "5%"))
        self.assertEqual((by["Melee"].per_min, by["Melee"].refused_share, by["Exorcism"].crit), (None, None, None))
        self.assertEqual([r.name for r in v.damage_rows], ["Melee", "Seal of Command", "Judgement", "Holy Strike",
                                                            "Consecration", "Touch of the Grave"])
        self.assertEqual(v.damage_rows[2].note, "damage from Judgement of Command")
        self.assertEqual([(r.name, f"{r.overheal_share:.0%}") for r in v.healing_rows],
                         [("Touch of the Grave", "49%"), ("Holy Light", "15%"), ("Cannibalize", "0%")])
        # pressed, with no damage or healing (the brief's rule; the mock-up lists only the six seals, blessings, aura)
        self.assertEqual(len(v.buff_rows), 12)
        self.assertEqual(v.buff_rows[0].name, "Seal of the Crusader")
        self.assertEqual([r.name for r in v.all_rows][5:9], ["Touch of the Grave", "Holy Light", "Cannibalize",
                                                              "Seal of the Crusader"])
        self.assertEqual(v.all_rows[-1].name, "Exorcism")
        self.assertEqual(v.fix, ("Consecration sat ready 75 s", "~1,177 damage", "about 8 more casts"))
        self.assertEqual(v.show, (382.3, 478.1, "Consecration"))
        # refusals among the damage abilities (not Holy Light's 5 of 12 or Exorcism's 1 of 1), then the next cooldown
        self.assertEqual(v.next_rows, [("Holy Strike refused on 109 of 288 presses", "38% refused"),
                                       ("Judgement sat ready 20 s", "~167 damage")])
        self.assertEqual(v.verdict, "Melee and Seal of Command did 63% of your damage. Holy Strike was refused on "
                                    "109 of 288 presses, and Consecration sat ready for 75 s.")
        self.assertEqual(v.refused_most, "Holy Strike")

    def test_spells_healer(self):
        heals = rows([("Flash Heal", 40, 0, 0, 20000, 5000, 40, 4), ("Renew", 30, 0, 0, 30000, 10000, 120, 12),
                      ("Lesser Heal", 10, 0, 0, 4000, 0, 10, 0), ("Power Word: Fortitude", 5, 0)])
        v = spells_view(heals, 600.0, COOLDOWNS, who="Shizuka Tsuruta")    # someone else: their cooldowns aren't known
        self.assertEqual([(r.name, r.overheal_share) for r in v.healing_rows],
                         [("Renew", 0.25), ("Flash Heal", 0.2), ("Lesser Heal", 0.0)])
        self.assertEqual((v.fix, v.show, v.next_rows, v.damage_rows), (None, None, [], []))
        self.assertEqual((v.total_damage, v.dps), (0, 0.0))
        self.assertEqual({r.refused_share for r in v.all_rows}, {None})      # their refusals aren't in the log
        self.assertEqual(v.verdict, "Renew and Flash Heal did 93% of Shizuka Tsuruta's healing.")
        self.assertEqual([r.name for r in v.buff_rows], ["Power Word: Fortitude"])
        mine = spells_view(heals, 600.0, None)             # you, with no cooldowns measured (a healer)
        self.assertEqual((mine.fix, mine.next_rows), (None, []))
        self.assertEqual(mine.verdict, "Renew and Flash Heal did 93% of your healing.")
        empty = spells_view([], 0.0)
        self.assertEqual((empty.total_damage, empty.dps, empty.fix, empty.all_rows), (0, 0.0, None, []))
        self.assertEqual(empty.verdict, "No damage or healing logged.")
        self.assertNotIn("0%", empty.verdict)


@unittest.skipUnless(HAVE_QT, "needs PyQt6")
class SpellsPageTests(unittest.TestCase):
    def test_page_paints_and_picks(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtCore import QPoint, Qt
        from PyQt6.QtTest import QTest
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])  # noqa: F841 (kept alive for the page)
        from dips_score.ui.spells import SpellsTab
        tab = SpellsTab()
        tab.resize(1200, 900)
        tab.who.addItem("Bao Kahn (you)", "me")
        lit, shown = [], []
        tab.highlight.connect(lambda g, s: lit.append((g, s)))
        tab.show_me.connect(lambda a, b, g, s: shown.append((a, b, g, s)))
        tab.show_view(spells_view(rows(SPELLS), COMBAT, COOLDOWNS, where=WHERE), "Blackfathom Deeps",
                      "Wed 18 Nov 22:27 · 69:45 long")
        self.assertEqual(lit, [(None, None)])              # a refill clears the timeline's highlight
        self.assertEqual((tab.buffs_drawer.label, tab.all_drawer.label),
                         ("SEALS, BLESSINGS AND OTHER SPELLS (12)", "ALL SPELLS (21)"))
        self.assertTrue(tab.buffs_drawer.body.isHidden() and tab.all_drawer.body.isHidden())     # both start shut
        self.assertEqual((tab.buffs.rowCount(), tab.every.rowCount()), (12, 21))
        self.assertEqual([tab.every.item(0, c).text() for c in range(7)],
                         ["Melee", "–", "–", "–", "9%", "52,475", "–"])
        self.assertEqual([tab.every.item(1, c).text() for c in (3, 4)], ["6.9", "11%"])     # Seal of Command
        tab.plate.button.click()                            # Show on the timeline: Consecration's worst fight
        self.assertEqual(shown, [(382.3, 478.1, "me", "Consecration")])
        self.assertFalse(tab.grab().isNull())

        def picked():
            """what looks picked: the lifted rows, and each drawer table's selected row"""
            return (tab.damage.sel, tab.healing.sel, *([i.row() for i in t.selectionModel().selectedRows()]
                                                       for t in (tab.buffs, tab.every)))
        top, bottom, name = tab.damage.hits[1]              # a damage row clicked: lit, the tab stays
        row = QPoint(10, round((top + bottom) / 2))
        QTest.mouseClick(tab.damage, Qt.MouseButton.LeftButton, pos=row)
        self.assertEqual((name, lit[-1]), ("Seal of Command", ("me", "Seal of Command")))
        QTest.mouseClick(tab.damage, Qt.MouseButton.LeftButton, pos=row)
        self.assertEqual((lit[-1], picked()), ((None, None), (None, None, [], [])))     # clicked again: unlit
        tab.buffs_drawer.flip()
        tab.all_drawer.flip()
        self.assertFalse(tab.grab().isNull())               # laid out, so the tables' rows have places
        QTest.mouseClick(tab.damage, Qt.MouseButton.LeftButton, pos=row)
        tab.every.selectRow(3)                              # a drawer row picked: only it looks picked
        self.assertEqual((lit[-1], picked()), (("me", "Holy Strike"), (None, None, [], [3])))
        tab.buffs.selectRow(0)                              # the other drawer's: the first one lets go
        self.assertEqual((lit[-1], picked()), (("me", "Seal of the Crusader"), (None, None, [0], [])))
        QTest.mouseClick(tab.buffs.viewport(), Qt.MouseButton.LeftButton,
                         pos=tab.buffs.visualRect(tab.buffs.model().index(0, 1)).center())   # the picked row again
        self.assertEqual((lit[-1], picked()), ((None, None), (None, None, [], [])))
        tab.every.selectRow(2)
        QTest.mouseClick(tab.damage, Qt.MouseButton.LeftButton, pos=row)    # a ruled row: the table lets go
        self.assertEqual((lit[-1], picked()),
                         (("me", "Seal of Command"), ("Seal of Command", "Seal of Command", [], [])))
        tab.every.selectRow(2)
        self.assertEqual(picked(), (None, None, [], [2]))
        QTest.keyClick(tab.every, Qt.Key.Key_Escape)       # Esc in a drawer table: unpicked
        self.assertEqual((lit[-1], picked()), ((None, None), (None, None, [], [])))
        tab.show_view(spells_view([], 0.0), "Nothing", "")  # nothing at all: no crash, and the plate emptied
        self.assertEqual((tab.plate.title, tab.plate.price, tab.plate.rows, tab.plate.has_button),
                         ("", None, [], False))
        self.assertTrue(tab.plate.isHidden())
        self.assertFalse(tab.grab().isNull())


if __name__ == "__main__":
    unittest.main()
