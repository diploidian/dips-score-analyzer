"""The window's shell (ui/app.py): the run tabs; a pick readies the timeline, a "Show ..." button goes to it.
Needs PyQt6, so it is skipped on a Python without it:
PYTHONPATH=<folder with PyQt6> python -m unittest discover -s tests"""
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
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


if __name__ == "__main__":
    unittest.main()
