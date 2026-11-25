"""The window's shell (ui/app.py): the run tabs; a pick readies the timeline, a "Show ..." button goes to it.
Needs PyQt6, so it is skipped on a Python without it:
PYTHONPATH=<folder with PyQt6> python -m unittest discover -s tests"""
import importlib.util
import io
import os
import re
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
    def setUp(self):
        from dips_score.ui.loader import Loader
        inline = mock.patch.object(Loader, "threaded", False)      # a run is in as soon as it's asked for
        inline.start()
        self.addCleanup(inline.stop)
        rows = mock.patch("dips_score.ui.app.run_row", return_value={"me": None, "name": ""})     # stub analyses
        rows.start()
        self.addCleanup(rows.stop)

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
            with mock.patch("dips_score.analysis.analyze", side_effect=ValueError("broken log")), \
                    mock.patch("sys.stderr", io.StringIO()):
                w._show_run(SimpleNamespace(id="r9", zone="Wailing Caverns", line_count=9, end_estimate=0))
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
                                   line_count=int(length), parts=[rid], length=length,
                                   end_estimate=start.timestamp() + length)

        def analysed(r, _paths):
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
                    mock.patch("dips_score.analysis.analyze", analysed), mock.patch("dips_score.analysis.rescore"):
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

    def test_a_new_visit_opens_by_itself(self):
        """a reload that brings a visit the game just saved opens it, even over another visit you had open; a
        reload with nothing new keeps your pick; a run's key changing keeps only its newest analysis"""
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])  # noqa: F841 (kept alive for the window)
        from dips_score.config import Paths
        from dips_score.ui.app import Window
        start = datetime(2026, 11, 18, 22, 0)

        def run(rid, minute):
            at = start.replace(minute=minute)
            return SimpleNamespace(id=rid, zone="Blackfathom Deeps", kind="party", started=at.timestamp(),
                                   start_time=at, line_count=9, parts=[rid], end_estimate=at.timestamp() + 600)
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"APPDATA": tmp}):
            w = Window(Paths(Path(tmp) / "no game"))
            w.live.timer.stop()
            shown = []
            w._show_run = lambda r: shown.append(r.id)
            r6, r7 = run("r6", 10), run("r7", 20)
            with mock.patch("dips_score.analysis.load_saved", return_value=(None, [r6, r7])) as load:
                w.reload()
                pick = next(w.tree.topLevelItem(0).child(i) for i in range(2)
                            if w.tree.topLevelItem(0).child(i).data(0, Qt.ItemDataRole.UserRole) == "r6")
                w.tree.setCurrentItem(pick)                 # an older visit open
                load.return_value = (None, [r6, r7])
                w.reload()                                  # nothing new: it stays
                self.assertEqual(shown[-1], "r6")
                load.return_value = (None, [r6, r7, run("r8", 40)])
                w.reload()                                  # the game saved a new visit: it opens
                self.assertEqual(shown[-1], "r8")
            with mock.patch("dips_score.analysis.rescore"):
                for key in (("r6", 1), ("r6", 2)):          # the log changed under it: analysed again
                    w.wanted.add("r6")
                    w._arrived("r6", key, SimpleNamespace(card=SimpleNamespace(empty=True)), "")
            self.assertEqual([k for k in w.cache if k[0] == "r6"], [("r6", 2)])

    def test_raids_have_their_own_section(self):
        """Raids shows only raid visits, Dungeons the rest; no raids says how to record them; a raid the game just
        saved opens under Raids"""
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])  # noqa: F841 (kept alive for the window)
        from dips_score.config import Paths
        from dips_score.ui.app import Window
        start = datetime(2026, 11, 18, 22, 0)

        def run(rid, zone, kind, minute):
            at = start.replace(minute=minute)
            return SimpleNamespace(id=rid, zone=zone, kind=kind, started=at.timestamp(), start_time=at, line_count=9,
                                   parts=[rid], end_estimate=at.timestamp() + 600)

        def zones():
            return [w.tree.topLevelItem(i).text(0) for i in range(w.tree.topLevelItemCount())]
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"APPDATA": tmp}):
            w = Window(Paths(Path(tmp) / "no game"))
            w.live.timer.stop()
            shown = []
            w._show_run = lambda r: shown.append(r.id)
            sm = run("r6", "Scarlet Monastery", "party", 10)
            with mock.patch("dips_score.analysis.load_saved", return_value=(None, [sm])) as load:
                w.reload()
                w.mode_raids.click()                        # no raids yet
                self.assertEqual((zones(), w.left_stack.currentIndex()), ([], 0))
                self.assertIn("Tick Raids", w.status_text)
                w.mode_dungeons.click()
                self.assertEqual((zones(), shown[-1]), (["Scarlet Monastery   (1)"], "r6"))
                load.return_value = (None, [sm, run("m1", "Molten Core", "raid", 30)])
                w.reload()                                  # a raid just saved: Raids, opened on it
                self.assertEqual((zones(), shown[-1]), (["Molten Core   (1)"], "m1"))
                self.assertTrue(w.mode_raids.isChecked() and not w.mode_dungeons.isChecked())
                w.mode_dungeons.click()
                self.assertEqual(zones(), ["Scarlet Monastery   (1)"])

    def test_share_copies_and_saves_the_whole_page(self):
        """Share puts the page showing on the clipboard and in a PNG, all of it, the part scrolled off screen too"""
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtGui import QImage
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        from dips_score.config import Paths
        from dips_score.ui.app import Window
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"APPDATA": tmp}):
            w = Window(Paths(Path(tmp) / "no game"))
            w.live.timer.stop()
            w.share_folder = Path(tmp) / "pictures"
            w.stack.setCurrentIndex(1)
            w.score.page.title = "Blackfathom Deeps"
            w.score.page.setMinimumHeight(3000)          # taller than the window: it scrolls
            w.show()
            app.processEvents()
            w._share()
            w.close()
            self.assertFalse(app.clipboard().image().isNull())
            saved = list((Path(tmp) / "pictures").glob("Blackfathom Deeps Debrief-*.png"))
            self.assertEqual(len(saved), 1)
            self.assertIn(str(saved[0]), w.status_text)
            self.assertEqual(QImage(str(saved[0])).height(), w.score.page.height())
            self.assertGreaterEqual(w.score.page.height(), 3000)

    def test_rename_a_run_and_a_fight(self):
        """a name takes the date's place on the run's rail row and sits beside the zone in the Debrief's title; a
        fight's takes the target's place on its row and sits beside its name on its page; empty takes it off"""
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])  # noqa: F841 (kept alive for the window)
        from dips_score.config import Paths
        from dips_score.ui.app import Window
        at = datetime(2026, 11, 18, 22, 0)
        run = SimpleNamespace(id="r6", zone="Blackfathom Deeps", kind="party", started=at.timestamp(), start_time=at,
                              line_count=9, parts=["r6"], end_estimate=at.timestamp() + 600)
        fight = {"id": "20261118233849824000", "start": "2026-11-18T23:38:49.824000", "duration": 112.458,
                 "damage": 2583, "dps": 23.0, "taken": 433, "healing": 53, "result": "they got away", "kind": "PvP",
                 "target": "Blackfathom Oracle"}
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"APPDATA": tmp}):
            w = Window(Paths(Path(tmp) / "no game"))
            w.live.timer.stop()
            w.live.history.fights = [fight]
            row = lambda: w.tree.topLevelItem(0).child(0)      # noqa: E731
            with mock.patch("dips_score.analysis.load_saved", return_value=(None, [run])), \
                    mock.patch("dips_score.analysis.analyze", side_effect=ValueError("no log")), \
                    mock.patch("sys.stderr", io.StringIO()):
                w.reload()
                self.assertTrue(row().text(0).startswith("Wed 18 Nov"))
                w.set_name("r6", "guild run with Anna")
                self.assertEqual((row().text(0), row().toolTip(0)), ("guild run with Anna", "Wed 18 Nov  22:00"))
                self.assertEqual(w.score.page.title, "Blackfathom Deeps — guild run with Anna")
                w.mode_fights.click()
                w.set_name(fight["id"], "the oracle")
                self.assertEqual(w.fight_list.item(0).text(), "the oracle")
                self.assertEqual(w.fight_detail.page.title, "Blackfathom Oracle — the oracle")
                w.mode_dungeons.click()
                w.set_name("r6", "")
                self.assertEqual(w.score.page.title, "Blackfathom Deeps")
            self.assertTrue((Path(tmp) / "dips-score" / "names.json").exists())

    def test_delete_a_run_and_a_fight(self):
        """a deleted run leaves the rail with the fights inside it and its name, and stays gone on reload; a deleted
        fight leaves the Fights list and the file"""
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])  # noqa: F841 (kept alive for the window)
        from dips_score import names, removed
        from dips_score.config import Paths
        from dips_score.sources.savedvars import Line, Run, Segment
        from dips_score.ui.app import RUN_ROLE, Window
        self.addCleanup(removed.IDS.clear)
        self.addCleanup(names.NAMES.clear)
        at = int(datetime(2026, 11, 18, 22, 0).timestamp())
        seg = lambda: [Segment(0, [], [Line(0, "X", []), Line(60000, "X", [])])]     # noqa: E731
        runs = [Run("r6", "x", "Blackfathom Deeps", "party", 1, 48, at, at + 600, seg()),
                Run("r7", "x", "Scarlet Monastery", "party", 1, 189, at + 7200, at + 7800, seg())]
        inside = {"id": "20261118220500000000", "start": "2026-11-18T22:05:00", "duration": 30.0, "damage": 900,
                  "dps": 30.0, "taken": 100, "healing": 0, "result": "killed", "kind": "Trash", "target": "Murloc"}
        after = dict(inside, id="20261118233849824000", start="2026-11-18T23:38:49.824000", target="Oracle")
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"APPDATA": tmp}):
            w = Window(Paths(Path(tmp) / "no game"))
            w.live.timer.stop()
            w.live.history.fights = [inside, after]
            tops = lambda: [w.tree.topLevelItem(i) for i in range(w.tree.topLevelItemCount())]     # noqa: E731
            rows = lambda: [t.child(j).data(0, RUN_ROLE) for t in tops() for j in range(t.childCount())]  # noqa: E731
            with mock.patch("dips_score.analysis.load_runs", return_value=runs), \
                    mock.patch.object(Paths, "saved_files", return_value=[Path(tmp) / "dips-Score.lua"]), \
                    mock.patch("dips_score.analysis.analyze", side_effect=ValueError("no log")), \
                    mock.patch("sys.stderr", io.StringIO()):
                w.reload()
                self.assertEqual(rows(), ["r7", "r6"])
                w.set_name("r6", "guild run with Anna")
                w.delete_item("r6")
                self.assertEqual(rows(), ["r7"])
                self.assertEqual([f["id"] for f in w.live.history.fights], [after["id"]])
                self.assertEqual(names.get("r6"), "")
                w.reload()
                self.assertEqual(rows(), ["r7"])
                w.mode_fights.click()
                w.delete_item(after["id"])
                self.assertEqual(w.fight_list.count(), 0)
                w.live.history.load()
                self.assertEqual(w.live.history.fights, [])

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
            w._fight = lambda: {"id": "picked"}       # a fight picked in the Fights list before
            w.mode_habits.click()
            self.assertEqual(w.stack.currentIndex(), 3)
            self.assertIsNot(w.left_stack.currentWidget(), w.fight_list)     # Habits shows no fight list
            self.assertIsNone(w._rename_id())          # so F2 and Del don't act on a fight you can't see
            del w._fight                                # the real one again, for Fights below
            self.assertEqual(w.habits_page.plate.title, "Judgement left unused")
            w.habits_page.plate.button.click()
            self.assertTrue(w.mode_fights.isChecked())
            self.assertEqual((w.stack.currentIndex(), w.left_stack.currentIndex()), (2, 1))

    def test_profile_page(self):
        """Profile: no fight list, the view's text, refreshed as a fight is saved, Open Habits; a finished slice is
        saved only once every run's figures are in"""
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from datetime import timedelta
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])  # noqa: F841 (kept alive for the window)
        from dips_score.config import Paths
        from dips_score.ui.app import Window
        from dips_score.ui.profileview import grow
        from test_fight_view import ORACLE
        from test_profile import fight
        now = datetime.now()

        def at(days):
            return {**ORACLE, **fight(start=(now - timedelta(days=days)).isoformat(), abilities=ORACLE["abilities"],
                                      helped=False)}
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"APPDATA": tmp}):
            (Path(tmp) / "no game" / "WTF").mkdir(parents=True)
            w = Window(Paths(Path(tmp) / "no game"))
            w.live.timer.stop()
            page, fights = w.profile_page, [at(20) for _ in range(10)] + [at(1) for _ in range(9)]
            w.live.history.fights = fights
            w.by_id = {"r1": None}          # a run still to come in
            w._fight = lambda: {"id": "picked"}
            w.mode_profile.click()
            self.assertEqual(w.stack.currentIndex(), 5)
            self.assertIsNot(w.left_stack.currentWidget(), w.fight_list)
            self.assertIsNone(w._rename_id())
            del w._fight
            self.assertEqual(page.need.head, "Your profile needs 10 fights from the last 15 days (9 so far).")
            self.assertTrue(page.body.isHidden())
            saved = w.paths.data_dir / "profile_history.json"
            self.assertFalse(saved.exists())
            self.assertTrue(page.foot.isHidden())

            w.run_rows["r1"] = None         # it came in (it couldn't be analysed)
            fights.append(at(0.5))
            w.live.fight.emit(fights[-1])
            self.assertTrue(saved.exists())
            self.assertFalse(page.body.isHidden() or page.foot.isHidden())
            self.assertTrue(page.need.isHidden())
            self.assertEqual((page.page.title, page.hero.big, page.hero.verdict),
                             ("A", "100", "Careful world damage dealer."))
            self.assertTrue(page.plate.isHidden())             # under 90% of possible damage: no plate
            self.assertEqual([r.name for r in page.roles.rows], ["Damage", "Healer", "Tank"])
            self.assertEqual((page.hands.rows, page.hands_fold.isHidden()), ([], True))     # no recorded run
            self.assertEqual((page.crest.crest.title, page.outdated.isHidden()), ("Slayer of Blackfathom Deeps", True))
            self.assertEqual(len(page.earlier.rows), 1)
            for part in (page.crest, page.hero, page.need, page.signature, page.table, page.card, page.hands, page.roles,
                         page.places, page.traits, page.earlier):
                self.assertTrue(part.accessibleName(), part)
            self.assertIn("no run graded as healer yet", page.roles.accessibleName())
            self.assertIn("Careful world damage dealer.", page.hero.accessibleName())
            before = saved.stat().st_mtime_ns
            w._redraw()                     # a look change: shown again, nothing new to save
            self.assertEqual((w.stack.currentIndex(), saved.stat().st_mtime_ns), (5, before))

            w.settings["motion"] = False    # reduced motion: settled at once
            w.stack.setCurrentIndex(0)
            w.mode_profile.click()
            self.assertEqual(page.roles.p, 1.0)
            w.settings["motion"] = True
            w.stack.setCurrentIndex(0)
            w.mode_profile.click()          # one entrance a visit, not one a refresh
            self.assertEqual(page.roles.p, 0.0)
            self.assertEqual((grow(0.0, 0), grow(1.0, 20)), (0.0, 1.0))
            page.entrance.stop()
            page.set_progress(0.5)
            w.mode_profile.click()
            self.assertEqual(page.roles.p, 0.5)
            w._show_habits = lambda: w.stack.setCurrentIndex(3)      # these fights lack what Habits reads
            page.plate.button.click()
            self.assertTrue(w.mode_habits.isChecked())
            self.assertEqual(w.stack.currentIndex(), 3)
            for f in fights[10:]:
                f["damage"] = 100
                f["cooldowns"] = [{"name": n, "lost": 9 - k, "counted": 1} for k, n in enumerate(("Judge", "Conse", "Strike"))]
            w._show_profile()
            self.assertFalse(page.plate.isHidden())
            self.assertEqual((page.plate.title, page.plate.rows),
                             ("Judge sat ready", [("Conse", "80 damage"), ("Strike", "70 damage")]))
            self.assertTrue(page.plate.accessibleName().startswith("Worth changing: Judge sat ready. about 90 damage. "))
            self.assertTrue(page.plate.accessibleName().endswith("Next: Conse 80 damage, Strike 70 damage"))

    def profile_page(self):
        """a ProfilePage in motion off and a view to show on it"""
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication
        self.app = QApplication.instance() or QApplication([])
        from dips_score.profile_view import OUTDATED, Crest, Plate, ProfileView, Row, TraitRow
        from dips_score.ui.profileview import ProfilePage
        tempo = Row("Time between fights", "25", "s", ink="m-pace", mark="new: Relentless", chip="+6 pts vs the 15 days before")
        edge = Row("Possible damage reached", "86", "%", ink="m-dmg", bar=.86, chip="+6 pts vs the 15 days before")
        split = Row("Auto attack or abilities", "47", "% auto attack", "44% abilities, 9% procs and items", "m-dmg")
        pace = [TraitRow("Tempo", "Time between fights", "25", "s", "", .9, "Relentless", ink="m-pace"),
                TraitRow("Streak", "Longest run without a death", "97", "", "", .44, "Surviving",
                         ("15", "200"), "How it counts <here>.\nYou: 97.", "m-pace")]
        nerve = [TraitRow(k, f"Nerve {k}", "9", "%", "", .4, "Daring", ("5%", "25%"), "How.", "m-surv") for k in "abc"]
        v = ProfileView(title="Bao", crest=Crest("Undead Paladin, level 37", "the Lone Storm, Crusader of the Wilds", "Wins on the edge.",
                                                 ["won after dropping to 2% health against Bloodscalp Berserker"]),
                        outdated=OUTDATED, ring="new: Relentless", ring_key="Tempo", card=[tempo, edge, split], hero="25", hero_unit="s",
                        plate=Plate("Your last 15 days were clean", "93% of possible damage", "in 300 fights where you did damage", tab="Going well"),
                        hands=[Row("Keys or clicks", "99", "% keys"), Row("Presses per minute", "21.2"), Row("Refused presses")],
                        traits=[("Pace", pace), ("Nerve", nerve), ("Road", nerve[:2])])
        page = ProfilePage()
        page.settings = {"motion": False}
        page.show_view(v)
        page.enter()
        return page, v

    def show_at(self, page, w):
        page.resize(w, 800)
        page.show()
        for _ in range(4):
            self.app.processEvents()
        self.assertFalse(page.widget().grab().isNull())     # the scrolled-off parts too

    def test_profile_title(self):
        """never cut, "of the" with its word, a line more only when it makes the title that much bigger"""
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])  # noqa: F841
        from dips_score.live.titles import NOUNS, THE
        from dips_score.live.traits import NAMED, TRAITS
        from dips_score.ui import theme
        from dips_score.ui.kit import adv, font
        from dips_score.ui.profileview import broken, fit_title
        theme.load_fonts()
        longest = lambda xs: max(xs, key=len)  # noqa: E731
        noun, place = longest(n for t in NOUNS.values() for n in t.values()), "the " + longest(THE)
        named = longest(n for *_, n in NAMED)
        titles = [f"{longest(e for t in TRAITS for e in t.epithets)} {noun} of {place}", f"{named}, {noun} of {place}",
                  f"{named}, {noun}, Scourge of the Twilight's Hammer", "Slayer"]
        for title in titles:
            for w in (200, 340, 406, 620):
                with self.subTest(title=title, w=w):
                    px, lines = fit_title(title, w)
                    self.assertEqual(" ".join(lines), title)
                    self.assertTrue(all(adv(font(px, 700, num=True), x) <= w for x in lines))
                    self.assertLessEqual(len(lines), 4)
                    self.assertFalse(any(x.endswith((" of", " the")) for x in lines))
                    if len(lines) > 2:          # one line fewer is at least 15% smaller
                        f = font(int(px / 1.15) + 1, 700, num=True)
                        few = broken(re.findall(r"(?:(?:of|the) )*\S+", title), f, w)
                        self.assertTrue(len(few) >= len(lines) or max(adv(f, x) for x in few) > w)
        self.assertEqual(fit_title("The Unfelled, Rimecaller of the Wilds", 700)[1][0], "The Unfelled,")
        self.assertFalse(any(x == "The" for w in range(60, 700, 20) for x in fit_title("The Unfelled, Crusader", w)[1]))
        self.assertEqual(" ".join(fit_title("Relentless Crusader", 60)[1]), "Relentless Crusader")    # too narrow for any size
        self.assertEqual([fit_title("Slayer", w)[0] for w in (620, 406, 204)], [74, 56, 44])

    def test_profile_parts(self):
        """accessible names, the ring's place, the drawers, what is hidden when there is nothing to show"""
        from dips_score.profile_view import ProfileView
        page, v = self.profile_page()
        self.show_at(page, 1200)
        self.assertEqual((page.crest.p, page.card.p), (1.0, 1.0))
        self.assertEqual(page.crest.accessibleName(),
                         "Crest: Undead Paladin, level 37. The Lone Storm, Crusader of the Wilds. Wins on the edge. "
                         "Won after dropping to 2% health against Bloodscalp Berserker")
        self.assertIn("Longest run without a death 97, Surviving, bar from 15 to 200, How it counts <here>. You: 97. Nerve:",
                      page.traits.accessibleName())         # what the hover says too
        from dips_score.ui.kit import Tips
        self.assertIsInstance(page.traits, Tips)
        self.assertEqual(len(page.traits.tips), 6)          # a region per row with a tip, none over another
        self.assertIn("How it counts &lt;here&gt;.</p>", page.traits.tips[0][1])
        rects = [r for r, _ in page.traits.tips]
        self.assertFalse(any(a.intersects(b) for i, a in enumerate(rects) for b in rects[:i]))
        self.assertTrue(all(page.traits.rect().toRectF().contains(r) for r in rects))
        self.assertIn("Time between fights 25 s, new: Relentless", page.traits.accessibleName())
        self.assertEqual((page.traits_drawer.accessibleName(), page.hands_drawer.accessibleName()), ("All traits (7)", "Hands (3)"))
        self.assertTrue(page.plate.accessibleName().startswith("Going well: Your last 15 days were clean"))
        self.assertEqual(page.plate.label, "Going well")
        self.assertEqual((page.traits_drawer.open, page.hands_drawer.open), (True, False))

        # All traits open: the ring goes round its chip, inside the table, and on no other part
        self.assertEqual((page.traits.new, page.card.marks, page.crest.note), ("Tempo", False, ""))
        ring, tier = page.traits.ring, page.traits.tier
        self.assertTrue(ring.contains(tier))
        self.assertGreaterEqual(ring.left(), 0)
        self.assertLessEqual(ring.width() - tier.width(), 24)
        # shut: round the card's figure, never its chip
        page.traits_drawer.flip()
        self.show_at(page, 1200)
        self.assertEqual((page.traits.new, page.card.marks, page.crest.note), (None, True, ""))
        ring, figure = page.card.ring, page.card.figure
        self.assertTrue(ring.contains(figure))
        self.assertLess(ring.height(), 48)          # one line tall: the chip is a line lower
        self.assertLess(ring.right(), page.card.width() - 17)       # in the card's frame, its 17px in
        # on no row: only the note, on the crest's second line
        v.card[0].mark = None
        page.show_view(v)
        self.assertEqual(page.crest.note, "new: Relentless")
        self.assertIn("new: Relentless", page.crest.accessibleName())
        self.show_at(page, 1200)
        before = page.crest.height()
        v.ring = None
        page.show_view(v)
        self.show_at(page, 1200)
        self.assertEqual((page.crest.note, page.crest.height()), ("", before))      # and it takes no room

        self.assertFalse(page.outdated.isHidden() or page.card.isHidden() or page.traits_fold.isHidden())
        v.outdated, v.card, v.traits, v.hands, v.plate = "", [], [], [], None
        page.show_view(v)
        self.assertTrue(all(x.isHidden() for x in (page.outdated, page.card, page.traits_fold, page.hands_fold, page.plate)))
        self.assertEqual(page.outdated.accessibleName(), "")
        self.show_at(page, 1200)
        page.show_view(ProfileView(need="Your profile needs 10 fights"))
        self.assertTrue(page.crest.isHidden() and page.body.isHidden())
        page.show_view(v)
        self.assertFalse(page.crest.isHidden() or page.body.isHidden())
        page.hide()

    def test_profile_stacks_and_widens_back(self):
        """the columns, the plate and All traits across the stacking width both ways, with nothing sideways; the entrance
        and the keyboard focus stay where they were"""
        page, v = self.profile_page()
        for d in (page.hands_drawer, page.spells_drawer):
            d.flip()
        self.show_at(page, 1200)
        page.activateWindow()
        page.traits_drawer.setFocus()
        page.set_progress(0.5)
        top = lambda x: x.mapTo(page.widget(), x.rect().topLeft()).y()  # noqa: E731
        for w, stacked, tight in ((1200, False, False), (960, True, False), (430, True, True), (278, True, True),
                                  (960, True, False), (1200, False, False)):
            with self.subTest(w):
                self.show_at(page, w)
                self.assertEqual(page.fit[1:], (stacked, tight))
                self.assertEqual(page.horizontalScrollBar().maximum(), 0)
                self.assertEqual(page.traits_drawer.open, not stacked)
                self.assertEqual(top(page.side) > top(page.hands), stacked)
                self.assertEqual(top(page.plate) > top(page.hero), tight)
                self.assertGreater(top(page.traits_fold), top(page.card))
                self.assertEqual(page.traits_fold.width(), page.body.width())
                self.assertEqual((page.roles.p, page.card.p, page.focusWidget()), (0.5, 0.5, page.traits_drawer))
        self.assertEqual(page.side.width(), 460)
        cols = page.traits.columns(1100)
        self.assertEqual((len(cols), [f for col in cols for f, _ in col]), (2, ["Pace", "Nerve", "Road"]))
        self.assertEqual([len(c) for c in page.traits.columns(699)], [3])
        page.traits_drawer.flip()           # shut by you: it stays shut
        self.show_at(page, 600)
        self.show_at(page, 1200)
        self.assertFalse(page.traits_drawer.open)
        # the crest and All traits stand still in the entrance unless something in them is drawn on
        for note, new, moves in (("", None, False), ("new: X", "Tempo", True)):
            page.crest.note, page.traits.new = note, new
            with mock.patch.object(page.crest, "update") as crest, mock.patch.object(page.traits, "update") as traits:
                page.set_progress(0.7)
            self.assertEqual((crest.called, traits.called, page.crest.p), (moves, moves, 0.7))
        page.hide()

    def test_profile_saves_own_data_only(self):
        """slices and run rows are saved only when the add-on's file was read and is the newest fight's character's"""
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from datetime import timedelta
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])  # noqa: F841 (kept alive for the window)
        from dips_score.config import Paths
        from dips_score.live import profile_history, profile_runs
        from dips_score.ui.app import Window
        from test_profile import fight, run
        now = datetime.now()

        def row(me, name="A"):
            return run(me=me, name=name, parts=["r1"], start=now - timedelta(days=2))
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"APPDATA": tmp}):
            w = Window(Paths(Path(tmp) / "no game"))
            w.live.timer.stop()
            wtf = Path(tmp) / "no game" / "WTF"
            wtf.mkdir(parents=True)
            w.live.history.fights = [fight(start=(now - timedelta(days=d)).isoformat(), helped=False)
                                     for d in [20] * 10 + [1] * 10]
            files = [m.file(w.paths) for m in (profile_history, profile_runs)]

            def saved(fresh=True):
                w._show_profile()
                out = [f.exists() for f in files]
                for f in files if fresh else ():
                    f.unlink(missing_ok=True)
                return out
            w.saved = Path(tmp) / "Account" / "X" / "Realm" / "B" / "SavedVariables" / "dips-Score.lua"
            w.by_id, w.run_rows = {"r1": SimpleNamespace(player_name="B")}, {"r1": row("B", "B")}
            self.assertEqual(saved(), [False, False])       # another character's file
            w.run_rows = {"r1": None}
            self.assertEqual(saved(), [False, False])       # no run says whose: by name
            w.by_id, w.run_rows = {}, {}
            self.assertEqual(saved(), [False, False])       # no run at all: by the folder
            w.saved = w.saved.parents[2] / "A" / "SavedVariables" / "dips-Score.lua"
            self.assertEqual(saved(), [True, False])
            w.by_id, w.run_rows = {"r1": SimpleNamespace(player_name="A")}, {"r1": row("A")}
            self.assertEqual(saved(), [True, True])

            with mock.patch("dips_score.analysis.load_saved", side_effect=ValueError("half-written")):
                w.reload()
            w.debounce.stop()
            self.assertEqual(saved(), [False, False])       # the last reload failed
            w.reload()                                      # no file at all: nothing to wait for
            self.assertEqual(w.saved, None)
            wtf.rmdir()                                     # the game folder gone (an unplugged drive): can't tell
            self.assertEqual(saved(), [False, False])
            wtf.mkdir()
            self.assertEqual(saved(fresh=False), [True, True])

            w.run_rows = {}                                 # the next start: the add-on dropped the run, its row stays
            self.assertEqual([r["presses"] for r in w._profile_runs()[0]], [100])
            before = [f.read_bytes() for f in files]
            w._show_profile()
            self.assertEqual([f.read_bytes() for f in files], before)
            with mock.patch.object(profile_history, "load", return_value=None), \
                    mock.patch.object(profile_history, "save") as save:         # unreadable now: nothing over it
                w.run_rows = {"r1": row("A")}
                w._show_profile()
            save.assert_not_called()
            files[0].unlink()
            files[1].write_text("{", encoding="utf-8")      # the run rows broken: no slice without them this time
            self.assertEqual(saved(fresh=False), [False, False])
            self.assertEqual(saved(), [True, True])

    def test_slices_are_saved_from_any_page(self):
        """the last run in saves the finished slices with the run rows, the Profile never opened"""
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from datetime import timedelta
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])  # noqa: F841 (kept alive for the window)
        from dips_score.live import profile_history, profile_runs
        from test_profile import fight, run
        now = datetime.now()
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"APPDATA": tmp}), \
                mock.patch("dips_score.ui.app.run_row", return_value=run(me="A", name="A", parts=["r1"], start=now)):
            (Path(tmp) / "no game" / "WTF").mkdir(parents=True)
            w = self.loading_window(tmp, [self.visit("r1", 1), self.visit("r2", 2)])
            w.live.history.fights = [fight(start=(now - timedelta(days=d)).isoformat(), helped=False)
                                     for d in [20] * 10 + [1] * 10]
            w._warm_up()
            self.arrive(w, "r1")
            files = [m.file(w.paths) for m in (profile_history, profile_runs)]
            self.assertEqual([f.exists() for f in files], [False, False])       # r2 still to come
            self.arrive(w, "r2")
            self.assertNotEqual(w.stack.currentIndex(), 5)
            self.assertEqual([f.exists() for f in files], [True, True])

    def test_import_drops_what_was_analysed(self):
        """Settings' old-logs import: the loader is stopped before the replay, the analyses in memory go after it, and
        the note says what it did"""
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])  # noqa: F841 (kept alive for the window)
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"APPDATA": tmp}):
            w = self.loading_window(tmp, [self.visit("r1", 1)])
            self.arrive(w, "r1")
            w.scores[("r0",)] = "  87"
            w._open_settings()
            d = w.settings_dialog
            for out, note in (((0, 0), "Nothing new to add."), ((0, 1234), "Refreshed 1,234 saved fights."),
                              ((1, 0), "Added 1 fight."), ((2, 1), "Added 2 fights, refreshed 1 saved fight.")):
                calls = mock.Mock()
                calls.replay.return_value = out
                with mock.patch.object(w.loader, "stop", calls.stop), \
                        mock.patch("dips_score.live.history.replay", calls.replay), \
                        mock.patch.object(w.loader, "threaded", True):
                    d._import()
                self.assertEqual([c[0] for c in calls.method_calls], ["stop", "replay"])
                self.assertEqual(d.imp_note.text(), note)
                self.assertEqual((w.cache, w.scores, w.run_rows), ({}, {}, {}))
                self.assertTrue(w.warm_timer.isActive())
            w.warm_timer.stop()

    def test_leaving_profile_while_a_run_loads(self):
        """a run that comes in after you left Profile for another page leaves you there; a later failure keeps its
        good row; new weights redraw an open Profile"""
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])  # noqa: F841 (kept alive for the window)
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"APPDATA": tmp}):
            w = self.loading_window(tmp, [])
            w.mode_profile.click()
            with mock.patch("dips_score.analysis.load_saved", return_value=(None, [self.visit("r1", 1)])):
                w.reload()
            self.assertTrue(w.waiting)
            self.assertEqual(w.stack.currentIndex(), 5)     # it loads behind Profile
            w.mode_habits.click()
            self.arrive(w, "r1")
            self.assertEqual((w.waiting, w.stack.currentIndex()), (None, 3))
            good = w.run_rows["r1"]
            w._arrived("r1", ("r1",), None, "")
            self.assertIs(w.run_rows["r1"], good)
            w.mode_profile.click()
            with mock.patch.object(w, "_show_profile") as show:
                w._rescore()
            show.assert_called()

    def loading_window(self, tmp, runs):
        """a window whose runs are asked for but don't come in until _arrived is called (the loader's thread)"""
        from dips_score.config import Paths
        from dips_score.ui.app import Window
        w = Window(Paths(Path(tmp) / "no game"))
        w.live.timer.stop()
        for tab in (w.score, w.group, w.pulls, w.spells, w.timeline_tab):
            tab.set_analysis = lambda _a: None          # the stub visits aren't drawn
        w.asked = []
        w.loader.want = lambda run, key, urgent: w.asked.append((run.id, key, urgent))
        load = mock.patch("dips_score.analysis.load_saved", return_value=(None, runs))
        load.start()
        self.addCleanup(load.stop)
        rescore = mock.patch("dips_score.analysis.rescore")
        rescore.start()
        self.addCleanup(rescore.stop)
        w.reload()
        return w

    def arrive(self, w, rid):
        """the loader's answer for a run asked for"""
        key = next(k for r, k, _u in w.asked if r == rid)
        a = SimpleNamespace(data=SimpleNamespace(run=w.by_id[rid]), card=SimpleNamespace(empty=True))
        w._arrived(rid, key, a, "")
        return a

    @staticmethod
    def visit(rid, minute, zone="Blackfathom Deeps"):
        at = datetime(2026, 11, 18, 22, minute)
        return SimpleNamespace(id=rid, zone=zone, kind="party", started=at.timestamp(), start_time=at, line_count=9,
                               parts=[rid], end_estimate=at.timestamp() + 600)

    def test_a_run_shows_a_loading_page_until_it_is_in(self):
        """picking a run not in memory: the loading page with a moving bar, then its tabs once it's in, on the tab
        you were on"""
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])  # noqa: F841 (kept alive for the window)
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"APPDATA": tmp}):
            w = self.loading_window(tmp, [self.visit("r6", 10)])      # the newest visit opens: asked for
            self.assertEqual([(r, u) for r, _k, u in w.asked], [("r6", True)])
            self.assertIs(w.stack.currentWidget(), w.wait_page)
            self.assertEqual((w.wait_page.title, w.wait_page.sub), ("Blackfathom Deeps", "Analysing this run…"))
            self.assertEqual(w.wait_bar.maximum(), 0)                   # moving
            w.tabs.setCurrentWidget(w.spells)
            a = self.arrive(w, "r6")
            self.assertEqual((w.stack.currentIndex(), w.current), (1, a))
            self.assertIs(w.tabs.currentWidget(), w.spells)
            w.dungeon.show_dungeon = lambda *_a: None
            w.tree.setCurrentItem(w.tree.topLevelItem(0))
            w.tree.setCurrentItem(w.tree.topLevelItem(0).child(0))      # picked again: in memory, no ask
            self.assertEqual((len(w.asked), w.stack.currentIndex()), (1, 1))

    def test_a_dungeon_page_counts_its_visits_in(self):
        """a dungeon's page: n of N on the loading page, then the page once all its visits are in"""
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])  # noqa: F841 (kept alive for the window)
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"APPDATA": tmp}):
            w = self.loading_window(tmp, [self.visit("r6", 10), self.visit("r7", 20)])
            shown = []
            w.dungeon.show_dungeon = lambda zone, visits, analyses: shown.append((zone, sorted(analyses)))
            w.tree.setCurrentItem(w.tree.topLevelItem(0))
            self.assertIs(w.stack.currentWidget(), w.wait_page)
            self.assertEqual(w.wait_page.sub, "Analysing Blackfathom Deeps · 0 of 2")
            self.arrive(w, "r7")
            self.assertEqual((w.wait_page.sub, w.wait_bar.value(), w.wait_bar.maximum()),
                             ("Analysing Blackfathom Deeps · 1 of 2", 1, 2))
            self.assertEqual(shown, [])
            self.arrive(w, "r6")
            self.assertEqual(shown, [("Blackfathom Deeps", ["r6", "r7"])])
            self.assertEqual(w.stack.currentIndex(), 0)

    def test_a_key_is_worked_out_once_until_a_save_a_pick_or_new_picks(self):
        """arrivals (and the dungeon page they redo) reuse each run's key: working one out stats the logs, which
        hands the interpreter to the loader's thread; a reload, a pick and new role picks work them out again"""
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])  # noqa: F841 (kept alive for the window)
        from dips_score import analysis
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"APPDATA": tmp}):
            w = self.loading_window(tmp, [self.visit(f"r{i}", 10 + i) for i in range(4)])
            w.dungeon.show_dungeon = lambda *_a: None
            with mock.patch("dips_score.analysis.run_key", side_effect=analysis.run_key) as run_key:
                w.tree.setCurrentItem(w.tree.topLevelItem(0))       # the dungeon: its 4 visits asked for
                for i in range(4):
                    self.arrive(w, f"r{i}")
                self.assertEqual(w.stack.currentIndex(), 0)
                self.assertEqual(run_key.call_count, 4)              # once a run, the arrivals' redo included
                w.reload()
                self.assertGreaterEqual(run_key.call_count, 8)       # the game saved: anew
                n = run_key.call_count
                w.current = SimpleNamespace(data=SimpleNamespace(run=w.by_id["r3"]))
                w._group_changed("guid", "PALADIN", "tank")         # new role picks: anew
                self.assertGreater(run_key.call_count, n)

    def test_picking_another_run_while_one_loads_shows_the_new_one(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])  # noqa: F841 (kept alive for the window)
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"APPDATA": tmp}):
            w = self.loading_window(tmp, [self.visit("r6", 10), self.visit("r8", 30, "Wailing Caverns")])
            self.assertEqual(w.wait_page.title, "Wailing Caverns")          # the newest, asked for
            w.tree.setCurrentItem(w.tree.topLevelItem(1).child(0))          # then the other, while it loads
            self.assertEqual(w.wait_page.title, "Blackfathom Deeps")
            self.arrive(w, "r8")                                            # the first in: kept, not shown
            self.assertIs(w.stack.currentWidget(), w.wait_page)
            a = self.arrive(w, "r6")
            self.assertEqual((w.stack.currentIndex(), w.current), (1, a))
            self.assertEqual(len(w.cache), 2)

    def test_a_run_opens_from_the_store_next_time(self):
        """a run analysed once is read back from disk by the next window (the next start), not analysed again;
        the warm-up gets the rest: their scores on the rail, their analyses on disk only"""
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])  # noqa: F841 (kept alive for the window)
        from dips_score.config import Paths
        from dips_score.ui.app import Window
        runs = [self.visit("r6", 10), self.visit("r7", 20)]

        def analysed(r, _paths):
            return SimpleNamespace(data=SimpleNamespace(run=r), card=SimpleNamespace(empty=False, total=87, grade="A"))

        def window():
            load.return_value = (None, [])
            w = Window(Paths(Path(tmp) / "no game"))
            w.live.timer.stop()
            for tab in (w.score, w.group, w.pulls, w.spells, w.timeline_tab):
                tab.set_analysis = lambda _a: None          # the stub visits aren't drawn
            load.return_value = (None, runs)
            w.reload()
            return w
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"APPDATA": tmp}), \
                mock.patch("dips_score.analysis.load_saved") as load, mock.patch("dips_score.analysis.rescore"):
            with mock.patch("dips_score.analysis.analyze", side_effect=analysed) as analyze:
                w = window()
                self.assertEqual((w.current.data.run.id, analyze.call_count), ("r7", 1))
                w._warm_up()                                # the 3 s timer's, with the loader inline
                self.assertEqual((analyze.call_count, len(w.cache), list(w.scores.values())), (2, 1, ["   87 A"]))
                self.assertTrue(w.tree.topLevelItem(0).child(1).text(0).endswith("87 A"))
                self.assertNotIn("Getting runs ready", w.status.text())
            with mock.patch("dips_score.analysis.analyze") as analyze:
                again = window()
                again.tree.setCurrentItem(again.tree.topLevelItem(0).child(1))
                analyze.assert_not_called()
                self.assertEqual((again.current.data.run.id, again.current.card.total), ("r6", 87))
            self.assertEqual(sorted(f.name for f in (Path(tmp) / "dips-score" / "cache" / "analysis").iterdir()),
                             ["r6.pkl", "r7.pkl"])


if __name__ == "__main__":
    unittest.main()
