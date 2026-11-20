"""The debrief's fight grid: what a click or the keyboard picks, where the circles sit, scrolling past 8 rows.
Needs PyQt6, so it is skipped on a Python without it: PYTHONPATH=<folder with PyQt6> python -m unittest discover -s tests"""
import importlib.util
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dips_score.debrief import FightCell  # noqa: E402

HAVE_QT = importlib.util.find_spec("PyQt6") is not None
REVIEW = [2, 30, 65, 68]


def cells(n: int) -> list[FightCell]:
    return [FightCell(i, f"{i}:00", "Trash", 50 if i in REVIEW else 95, "D" if i in REVIEW else "S", i % 9 == 0,
                      i == 30, 0.0, 1.0) for i in range(n)]


@unittest.skipUnless(HAVE_QT, "needs PyQt6")
class FightGridTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def grid(self, n=70):
        from dips_score.ui.debrief import FightGrid
        g = FightGrid()
        g.set_cells(cells(n), REVIEW)
        got = []
        g.picked.connect(got.append)
        return g, got

    def test_click_picks_the_fight_under_it(self):
        from PyQt6.QtCore import QPointF, Qt
        from PyQt6.QtTest import QTest
        g, got = self.grid()
        for k in (0, 7, 8, 30, 69):
            self.assertEqual(g.cell_at(g.cell_rect(k).center()), k)
        self.assertIsNone(g.cell_at(g.cell_rect(70).center()))   # the empty slot after the last fight
        self.assertIsNone(g.cell_at(QPointF(100, 10)))           # the note above the grid
        QTest.mouseClick(g, Qt.MouseButton.LeftButton, pos=g.cell_rect(30).center().toPoint())
        self.assertEqual(got, [30])

    def test_keyboard_moves_and_picks(self):
        from PyQt6.QtCore import Qt
        from PyQt6.QtTest import QTest
        g, got = self.grid()
        for key in (Qt.Key.Key_Down, Qt.Key.Key_Right, Qt.Key.Key_Left, Qt.Key.Key_Return):
            QTest.keyClick(g, key)
        self.assertEqual(got, [8])          # down a row, right and back
        for _ in range(9):
            QTest.keyClick(g, Qt.Key.Key_Down)
        QTest.keyClick(g, Qt.Key.Key_Space)
        self.assertEqual(got, [8, 64])      # down stops on the last full column (70 fights: no 72)

    def test_circles_sit_on_their_cells(self):
        g, _ = self.grid()
        for k in REVIEW:
            self.assertTrue(g.cell_rect(k).contains(g.circle_at(k)), k)

    def test_scrolls_past_8_rows(self):
        from dips_score.ui.debrief import GRID_VIEW, NOTE_H, FightsColumn
        col = FightsColumn()
        col.set_cells(cells(64), REVIEW)
        self.assertEqual(col.scroll.maximumHeight(), col.grid.height())     # 8 rows: all of them
        col.set_cells(cells(70), REVIEW)
        self.assertEqual(col.scroll.maximumHeight(), NOTE_H + GRID_VIEW)
        self.assertGreater(col.grid.height(), NOTE_H + GRID_VIEW)
        col.set_cells([], [])
        self.assertTrue(col.scroll.isHidden())


@unittest.skipUnless(HAVE_QT, "needs PyQt6")
class EntranceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def show(self, page, title="Run", sub="d", view=None):
        from dips_score.debrief import DebriefView
        page.show_view(view or DebriefView(total="75", grade="B"), title, sub)

    def test_runs_for_a_new_view_only(self):
        from dips_score.ui.debrief import DebriefPage
        page = DebriefPage()
        self.show(page)
        self.assertEqual(page.entrance.state().name, "Running")
        page.entrance.stop()
        page.set_progress(1.0)
        self.show(page)                       # a redraw (theme switch, rescore): the same view
        self.assertNotEqual(page.entrance.state().name, "Running")
        self.assertEqual(page.hero.p, 1.0)
        self.show(page, title="Other run")
        self.assertEqual(page.entrance.state().name, "Running")
        page.entrance.stop()

    def test_motion_off_settles_at_once(self):
        from dips_score.ui.debrief import DebriefPage
        page = DebriefPage()
        page.settings = {"motion": False}
        self.show(page)
        self.assertNotEqual(page.entrance.state().name, "Running")
        self.assertEqual((page.hero.p, page.measures.p, page.fights.grid.p), (1.0, 1.0, 1.0))


if __name__ == "__main__":
    unittest.main()
