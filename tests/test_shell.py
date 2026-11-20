"""The window's shell (ui/app.py): the run tabs; a pick readies the timeline, a "Show ..." button goes to it.
Needs PyQt6, so it is skipped on a Python without it:
PYTHONPATH=<folder with PyQt6> python -m unittest discover -s tests"""
import importlib.util
import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

HAVE_QT = importlib.util.find_spec("PyQt6") is not None


@unittest.skipUnless(HAVE_QT, "needs PyQt6")
class ShellTests(unittest.TestCase):
    def test_tabs_and_show_on_timeline(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])  # noqa: F841 (kept alive for the window)
        from dips_score.config import Paths
        from dips_score.ui.app import Window
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"APPDATA": tmp}):
            w = Window(Paths(Path(tmp) / "no game"))     # no game folder: an empty window, nothing read
            tabs = w.tabs
            self.assertEqual([tabs.tabText(i) for i in range(tabs.count())],
                             ["Debrief", "Timeline", "Pulls", "Spells", "Group"])
            w.spells.highlight.emit(None, None)          # a refill clears, and stays on the Debrief
            self.assertEqual(tabs.currentIndex(), 0)
            tabs.setCurrentWidget(w.spells)
            view = (w.timeline.v0, w.timeline.v1)
            w.spells.highlight.emit("guid-1", "Fireball")  # a spell picked: lit up, same view, still on Spells
            self.assertIs(tabs.currentWidget(), w.spells)
            self.assertEqual((w.timeline.hl_guid, w.timeline.hl_spell), ("guid-1", "Fireball"))
            self.assertEqual((w.timeline.v0, w.timeline.v1), view)
            tabs.setCurrentIndex(0)
            self.assertIsNone(w.timeline.hl_guid)        # left for the Debrief: the spell's highlight went
            w.score.zoom.emit(385.0, 480.0)               # a fight picked: zoomed, still on the Debrief
            self.assertEqual(tabs.currentIndex(), 0)
            self.assertEqual((w.timeline.v0, w.timeline.v1), (385.0, 480.0))
            self.assertEqual(w.timeline_tab.scope, (385.0, 480.0))     # its picker followed (no run: a custom view)
            w.score.page.zoom.emit(100.0, 200.0)          # Show me: the Timeline tab
            self.assertIs(tabs.currentWidget(), w.timeline_tab)
            self.assertEqual((w.timeline.v0, w.timeline.v1), (100.0, 200.0))
            tabs.setCurrentWidget(w.pulls)
            w.pulls.zoom.emit(300.0, 400.0)               # a pull picked in the drawer: zoomed, still on Pulls
            self.assertIs(tabs.currentWidget(), w.pulls)
            self.assertEqual((w.timeline.v0, w.timeline.v1), (300.0, 400.0))
            w.pulls.show_me.emit(1092.4, 1207.9)          # Show this pull: the Timeline tab
            self.assertIs(tabs.currentWidget(), w.timeline_tab)
            self.assertEqual((w.timeline.v0, w.timeline.v1), (1092.4, 1207.9))
            tabs.setCurrentWidget(w.spells)
            w.spells.show_me.emit(382.5, 478.1, "guid-1", "Consecration")   # Show on the timeline: there, lit
            self.assertIs(tabs.currentWidget(), w.timeline_tab)
            self.assertEqual((w.timeline.v0, w.timeline.v1), (382.5, 478.1))
            self.assertEqual((w.timeline.hl_guid, w.timeline.hl_spell), ("guid-1", "Consecration"))
            tabs.setCurrentWidget(w.group)
            w.group.show_me.emit(1184.9, 1209.9)          # Show your death: the Timeline tab
            self.assertIs(tabs.currentWidget(), w.timeline_tab)
            self.assertEqual((w.timeline.v0, w.timeline.v1), (1184.9, 1209.9))
            w.live.timer.stop()

    def test_live_fight_shows_on_the_loaded_run(self):
        """R7: a live fight's Show on the timeline is there only when the fight falls inside the loaded run, and
        goes to that run's Timeline tab, zoomed to the fight"""
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])  # noqa: F841 (kept alive for the window)
        from dips_score.config import Paths
        from dips_score.ui.app import Window
        fight = {"start": "2026-11-18T23:38:49.824000", "duration": 112.458, "damage": 2583, "dps": 23.0,
                 "taken": 433, "healing": 53, "result": "they got away", "kind": "PvP", "target": "Blackfathom Oracle",
                 "auto": {"swings": 13, "speed": 3.4, "lost": 12, "lost_casting": 0, "lost_other": 12,
                          "damage_lost": 1537.8}}
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"APPDATA": tmp}):
            w = Window(Paths(Path(tmp) / "no game"))
            w.live.timer.stop()
            w.fight_list.set_fights([fight])
            w._mode("fights")                           # no run loaded: no button
            self.assertEqual(w.stack.currentIndex(), 2)
            self.assertFalse(w.fight_detail.plate.has_button)
            w.current = SimpleNamespace(data=SimpleNamespace(run=SimpleNamespace(id="r7"),
                                                             start=datetime(2026, 11, 18, 23, 37), duration=600.0))
            w._mode("fights")                           # coming back re-shows the fight against the loaded run
            self.assertTrue(w.fight_detail.plate.has_button)
            w.fight_detail.plate.button.click()
            self.assertTrue(w.mode_dungeons.isChecked())
            self.assertEqual(w.stack.currentIndex(), 1)
            self.assertIs(w.tabs.currentWidget(), w.timeline_tab)
            self.assertEqual((round(w.timeline.v0, 3), round(w.timeline.v1, 3)), (106.824, 225.282))
            w.current.data.duration = 200.0             # the run ended mid-fight: no button
            w._mode("fights")
            self.assertFalse(w.fight_detail.plate.has_button)

    def test_habit_to_fix_opens_fights(self):
        """R8: the Habits plate's Open Fights switches the rail to Fights mode"""
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])  # noqa: F841 (kept alive for the window)
        from dips_score.config import Paths
        from dips_score.ui.app import Window
        from test_habits import fight
        row = {"name": "Judgement", "cd": 10, "lost": 200, "missed": 1, "counted": 1}
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"APPDATA": tmp}):
            w = Window(Paths(Path(tmp) / "no game"))
            w.live.timer.stop()
            w.live.history.fights = [fight(i, cooldowns=[row]) for i in range(6)]
            w.mode_habits.click()
            self.assertEqual(w.stack.currentIndex(), 3)
            self.assertEqual(w.habits_page.plate.title, "Judgement left unused")
            w.habits_page.plate.button.click()
            self.assertTrue(w.mode_fights.isChecked())
            self.assertEqual((w.stack.currentIndex(), w.left_stack.currentIndex()), (2, 1))


if __name__ == "__main__":
    unittest.main()
