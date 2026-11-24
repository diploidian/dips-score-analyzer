"""The shared painted parts (ui/kit.py): what the generic options add, and that every part paints.
Needs PyQt6, so it is skipped on a Python without it:
PYTHONPATH=<folder with PyQt6> python -m unittest discover -s tests"""
import importlib.util
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

HAVE_QT = importlib.util.find_spec("PyQt6") is not None


@unittest.skipUnless(HAVE_QT, "needs PyQt6")
class KitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def paints(self, w):
        w.resize(500, max(1, w.heightForWidth(500) if w.hasHeightForWidth() else w.sizeHint().height()))
        self.assertFalse(w.grab().isNull())

    def test_drawer_shows_its_body_from_the_keyboard(self):
        from PyQt6.QtCore import Qt
        from PyQt6.QtTest import QTest
        from PyQt6.QtWidgets import QWidget
        from dips_score.ui.kit import Drawer
        body = QWidget()
        d = Drawer("All pulls", body)
        d.set_count(64)
        got = []
        d.toggled.connect(got.append)
        self.assertEqual((d.label, d.accessibleName()), ("ALL PULLS (64)", "All pulls (64)"))
        self.assertTrue(body.isHidden())
        QTest.keyClick(d, Qt.Key.Key_Space)
        self.assertFalse(body.isHidden())
        QTest.keyClick(d, Qt.Key.Key_Return)
        self.assertEqual((got, body.isHidden()), ([True, False], True))
        self.paints(d)

    def test_plate_button_is_optional_and_clicks_through(self):
        from dips_score.ui.kit import Plate
        plate = Plate("Pull to fix")
        plate.set("18:15 · 105 s", "44% mana", "when you entered · you died", None, [])
        self.assertTrue(plate.button.isHidden())
        bare = plate.heightForWidth(400)
        got = []
        plate.clicked.connect(lambda: got.append(1))
        plate.set("18:15 · 105 s", "44% mana", "when you entered · you died", "Show on the timeline",
                  [("next", "−1.0")])
        self.assertGreater(plate.heightForWidth(400), bare)
        plate.button.click()
        self.assertEqual(got, [1])
        self.paints(plate)
        h = plate.heightForWidth(400)
        plate.price_px = 46                  # the fight page's bigger price
        self.assertGreater(plate.heightForWidth(400), h)

    def test_plate_wraps_a_long_caption_and_only_that(self):
        from dips_score.ui.kit import Plate
        plate = Plate("Going well")
        plate.price_words = True
        plate.set("Clean", "94%", "in 300 fights where you did damage", None, [])
        self.assertGreater(plate.heightForWidth(218), plate.heightForWidth(400))
        self.paints(plate)
        plate.set("Clean", "94%", "in 3 fights", None, [])
        self.assertEqual(plate.heightForWidth(218), plate.heightForWidth(400))      # it fits: as before
        words = Plate("Fix")                # a price with no caption keeps its own line, whatever its width
        words.set("Fix", "1,234,567 damage", None, None, [])
        self.assertEqual(words.heightForWidth(120), words.heightForWidth(800))

    def test_hero_caption_and_chip_take_room(self):
        from dips_score.ui.kit import Hero
        hero = Hero()
        hero.set("77", "%", None, None, "Efficiency is dropping.")
        bare = hero.heightForWidth(280)
        hero.set("77", "%", "efficiency, last 20 fights", "−10 pts vs the 18 before", "Efficiency is dropping.")
        self.assertGreater(hero.heightForWidth(280), bare)
        self.paints(hero)
        hero.set("95", "S", None, "+6 vs last visit", "Every boss 90 or better.")
        self.paints(hero)
        hero.set("49", "%", "of the damage that was possible", None, "12 swings lost.")
        bare = hero.heightForWidth(330)
        hero.bar = (0.49, "m-cd")            # the bullet bar and its CLEAN tick, under the caption
        self.assertEqual(hero.heightForWidth(330), bare + 4 + 38)
        self.paints(hero)

    def test_bar_rows_key_figures_and_tag_paint(self):
        from PyQt6.QtGui import QPainter, QPixmap
        from dips_score.ui.kit import BarRow, BarRows, KeyFigures, draw_tag
        rows = BarRows("Where the damage went")
        rows.set([BarRow("Swings lost", "≈1,538", 1.0, "m-act", "×12"),
                  BarRow("Judgement sat ready", "≈614", 0.4, "m-cd")], None)
        bare = rows.heightForWidth(500)
        rows.set(rows.rows, ("Left on the table · estimate", "≈2,705"))
        self.assertGreater(rows.heightForWidth(500), bare)
        self.paints(rows)
        kf = KeyFigures()
        self.assertEqual(kf.heightForWidth(500), 0)          # nothing to show takes no room
        kf.set([("2,583", "damage"), ("23", "DPS"), ("433", "taken"), ("53", "healing")])
        self.assertEqual(kf.heightForWidth(500), 51)
        self.paints(kf)
        kf.set([("0", "entered under 50% health", "lowest was 57%, at 63:27"),    # stacked: a muted line under each
                ("6", "you pulled", "12:27, 15:54, 28:16, 37:35, 43:12, 55:02")])
        self.assertGreater(kf.heightForWidth(500), 51)
        self.paints(kf)
        pm = QPixmap(60, 18)
        p = QPainter(pm)
        self.assertEqual(draw_tag(p, 0, 9, "PvP"), draw_tag(None, 0, 9, "PvP"))     # painted as it measures
        p.end()
        h = rows.heightForWidth(500)
        rows.top_rule = False                # under a part that ends on a rule: same height, no rule of its own
        self.assertEqual(rows.heightForWidth(500), h)
        self.paints(rows)


if __name__ == "__main__":
    unittest.main()
