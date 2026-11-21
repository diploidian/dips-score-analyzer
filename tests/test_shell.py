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

    def test_leaving_spells_unpicks_the_spell(self):
        """a spell stays picked (row lifted, drawer row selected, lit on the timeline) on Spells and Timeline; left
        for another tab, it lets go everywhere, so nothing on Spells looks picked that the timeline doesn't show"""
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])  # noqa: F841 (kept alive for the window)
        from dips_score.config import Paths
        from dips_score.model.casts import SpellRow
        from dips_score.spells_view import spells_view
        from dips_score.ui.app import Window
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"APPDATA": tmp}):
            w = Window(Paths(Path(tmp) / "no game"))
            w.live.timer.stop()
            s = w.spells
            s.who.addItem("Bao Kahn (you)", "me")
            s.show_view(spells_view([SpellRow(None, "Judgement", 10, 0, 500, 0, 0, 10, 1)], 60.0), "Somewhere", "")
            w.tabs.setCurrentWidget(s)
            s.damage.clicked.emit("Judgement")          # a damage row picked
            w.tabs.setCurrentWidget(w.timeline_tab)     # in view on the timeline: still picked
            self.assertEqual((s.damage.sel, w.timeline.hl_spell), ("Judgement", "Judgement"))
            w.tabs.setCurrentWidget(w.pulls)            # left: unpicked, and unlit
            self.assertEqual((s.damage.sel, w.timeline.hl_spell), (None, None))
            w.tabs.setCurrentWidget(s)
            s.every.selectRow(0)                        # a drawer row picked
            self.assertEqual(w.timeline.hl_spell, "Judgement")
            w.tabs.setCurrentWidget(w.group)
            self.assertEqual((s.every.selectionModel().hasSelection(), w.timeline.hl_spell), (False, None))

    def test_a_run_that_fails_clears_every_tab(self):
        """a run that can't be analysed: the Debrief says so, and no other tab keeps showing the last run"""
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])  # noqa: F841 (kept alive for the window)
        from dips_score.config import Paths
        from dips_score.ui.app import Window
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"APPDATA": tmp}):
            w = Window(Paths(Path(tmp) / "no game"))
            w.live.timer.stop()
            pages = (w.timeline_tab, w.pulls, w.spells, w.group)
            for tab in pages:
                tab.page.title = "Blackfathom Deeps"         # the last run's
            with mock.patch.object(Window, "_analysis", side_effect=ValueError("broken log")), \
                    mock.patch("dips_score.ui.app.traceback.print_exc"):
                w._show_run(SimpleNamespace(id="r9", zone="Wailing Caverns"))
            self.assertIsNone(w.current)
            self.assertEqual((w.score.page.title, w.score.page.sub),
                             ("Wailing Caverns", "Couldn't analyze this run - see the terminal."))
            self.assertEqual([tab.page.title for tab in pages], ["No run selected"] * 4)
            self.assertEqual((w.stack.currentIndex(), w.score.who.count()), (1, 0))

    def test_reload_in_fights_mode_follows_the_visit(self):
        """a reload while the rail shows Fights still loads the picked visit as saved now (or a new visit, when a
        dungeon is picked) behind the page, so a fight in it gets Show on the timeline; the page stays on Fights"""
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])  # noqa: F841 (kept alive for the window)
        from dips_score.config import Paths
        from dips_score.ui.app import Window
        fight = {"start": "2026-11-18T23:38:49.824000", "duration": 112.458, "damage": 2583, "dps": 23.0,
                 "taken": 433, "healing": 53, "result": "they got away", "kind": "PvP", "target": "Blackfathom Oracle"}

        def run(rid, start, length):
            return SimpleNamespace(id=rid, zone="Kalimdor", kind="world", started=start.timestamp(), start_time=start,
                                   line_count=9, parts=[rid], length=length)

        def analysed(_self, r):
            return SimpleNamespace(data=SimpleNamespace(run=r, start=r.start_time, duration=r.length),
                                   card=SimpleNamespace(empty=True))
        start = datetime(2026, 11, 18, 23, 30)          # the fight is 530 s to 642 s into the visit
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"APPDATA": tmp}):
            w = Window(Paths(Path(tmp) / "no game"))
            w.live.timer.stop()
            for tab in (w.score, w.group, w.pulls, w.spells, w.timeline_tab):
                tab.set_analysis = lambda _a: None          # the stub visits aren't drawn
            w.dungeon.show_dungeon = lambda *_a: None
            w.fight_list.set_fights([fight])
            later = start.replace(minute=50)
            with mock.patch("dips_score.analysis.load_saved", return_value=(None, [run("r7", start, 300.0)])) as load, \
                    mock.patch.object(Window, "_analysis", analysed):
                w.reload()                                  # the visit, as the game last saved it
                w._mode("fights")
                self.assertFalse(w.fight_detail.plate.has_button)     # the fight came after that save
                load.return_value = (None, [run("r7", start, 900.0)])
                w.reload()                                  # a /reload in game: the visit grew, the fight's in it
                self.assertEqual((w.current.data.duration, w.stack.currentIndex()), (900.0, 2))
                self.assertTrue(w.fight_detail.plate.has_button)
                w._mode("dungeons")
                w.tree.setCurrentItem(w.tree.topLevelItem(0))       # a dungeon picked, then Fights
                w._mode("fights")
                load.return_value = (None, [run("r7", start, 900.0), run("r8", later, 600.0)])
                w.reload()                                  # a new visit: it opens behind the page
                self.assertEqual((w.current.data.run.id, w.stack.currentIndex()), ("r8", 2))
                self.assertFalse(w.fight_detail.plate.has_button)     # the fight was before it
            self.assertTrue(w.mode_fights.isChecked())

    def test_new_weights_redraw_group_and_timeline(self):
        """a weights change scores the run showing again on the Debrief, Group and Timeline, and keeps the tab, the
        Timeline's view, the Debrief's fight and a spell lit from Spells"""
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])  # noqa: F841 (kept alive for the window)
        from dips_score.config import Paths
        from dips_score.ui.app import Window
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"APPDATA": tmp}):
            w = Window(Paths(Path(tmp) / "no game"))
            w.live.timer.stop()
            a = SimpleNamespace(data=SimpleNamespace(run=SimpleNamespace(id="r6")))
            w.current, w.cache = a, {("r6",): a}
            w.stack.setCurrentIndex(1)
            w.tabs.setCurrentWidget(w.spells)
            w.timeline.set_view(400.0, 425.0)
            w.timeline.highlight("me", "Judgement")
            w.score.fight = 2
            # the lanes' own set_analysis starts over: the whole run, nothing lit
            with mock.patch("dips_score.analysis.rescore") as rescore, \
                    mock.patch.object(w.score, "set_analysis"), mock.patch.object(w.score, "show_fight") as fight, \
                    mock.patch.object(w.group, "set_analysis") as group, \
                    mock.patch.object(w.timeline_tab, "set_analysis",
                                      side_effect=lambda _a: w.timeline.set_data(None)) as timeline:
                w._rescore()
            rescore.assert_called_once_with(a)
            group.assert_called_once_with(a)
            timeline.assert_called_once_with(a)
            fight.assert_called_once_with(2)
            self.assertIs(w.tabs.currentWidget(), w.spells)
            self.assertEqual((w.timeline.v0, w.timeline.v1), (400.0, 425.0))
            self.assertEqual((w.timeline.hl_guid, w.timeline.hl_spell), ("me", "Judgement"))

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
