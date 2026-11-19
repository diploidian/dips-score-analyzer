"""The window.

Left: dungeons, each opening into its visits. Right: picking a dungeon shows its page (your score
on every visit); picking a visit shows its tabs (Score, Group, Pulls, Spells, Summary) above the
timeline. The window watches the add-on's saved file and reloads when the game saves (/reload,
logout); a new visit opens by itself.
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

from PyQt6.QtCore import QFileSystemWatcher, Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (QApplication, QHBoxLayout, QMainWindow, QPushButton, QScrollArea, QSplitter,
                             QStackedWidget, QTabWidget, QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
                             QWidget)

from .. import analysis
from ..analysis import Analysis
from ..config import Paths
from ..model.roster import Overrides
from ..scoring.classes import load_upkeep
from ..scoring.score import load_weights
from ..sources.savedvars import Run
from . import settings as app_settings
from . import texture, theme
from .pages import DungeonPage, GroupTab, PullsTab, ScoreTab, SpellsTab, dim_label
from .summary import SummaryTab
from .timeline import Timeline
from .settings import SettingsDialog
from ..live.habits import habits
from .fightsview import FightDetail, FightList
from .habitsview import HabitsPage
from .live_ui import LiveController
from .weights import WeightsDialog

RUN_ROLE = Qt.ItemDataRole.UserRole


class Window(QMainWindow):
    def __init__(self, paths: Paths, live=None):
        super().__init__()
        self.paths = paths
        self.saved: Path | None = None
        self.runs: list[Run] = []
        self.by_id: dict[str, Run] = {}
        self.current: Analysis | None = None
        self.cache: dict[tuple, Analysis] = {}
        self.setWindowTitle("dips score")
        self.resize(1500, 950)

        # ---- left: dungeons and their visits
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setMinimumWidth(260)
        self.tree.currentItemChanged.connect(self._picked)
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(8, 8, 0, 8)
        modes = QHBoxLayout()
        self.mode_dungeons = QPushButton("Dungeons")
        self.mode_fights = QPushButton("Fights")
        self.mode_habits = QPushButton("Habits")
        for b in (self.mode_dungeons, self.mode_fights, self.mode_habits):
            b.setCheckable(True)
            modes.addWidget(b)
        self.mode_dungeons.setChecked(True)
        self.mode_dungeons.clicked.connect(lambda: self._mode("dungeons"))
        self.mode_fights.clicked.connect(lambda: self._mode("fights"))
        self.mode_habits.clicked.connect(lambda: self._mode("habits"))
        ll.addLayout(modes)
        self.fight_list = FightList()
        self.left_stack = QStackedWidget()
        self.left_stack.addWidget(self.tree)
        self.left_stack.addWidget(self.fight_list)
        ll.addWidget(self.left_stack, 1)
        self.status = dim_label()
        ll.addWidget(self.status)
        self.lag = dim_label()
        self.lag.setToolTip("How long the game takes to write a fight to its log file. The app cannot shorten it.")
        self.lag.hide()
        ll.addWidget(self.lag)
        weights_btn = QPushButton("Scoring weights...")
        weights_btn.clicked.connect(self._open_weights)
        ll.addWidget(weights_btn)
        row = QHBoxLayout()
        reload_btn = QPushButton("Reload")
        reload_btn.clicked.connect(self.reload)
        row.addWidget(reload_btn, 1)
        cog = QToolButton()
        cog.setText("\u2699")            # the settings cog
        cog.setToolTip("Settings: the look (Azeroth or Classic) and the game art it uses")
        cog.setStyleSheet("font-size: 14pt; padding: 1px 8px;")
        cog.clicked.connect(self._open_settings)
        row.addWidget(cog)
        ll.addLayout(row)
        self.weights: WeightsDialog | None = None
        self.settings_dialog: SettingsDialog | None = None
        self.settings = app_settings.load(paths)
        self.rescore_timer = QTimer(singleShot=True, interval=120)   # sliders move fast: score once they pause
        self.rescore_timer.timeout.connect(self._rescore)

        # ---- right: the dungeon page, or a run's tabs above the timeline
        self.dungeon = DungeonPage()
        self.dungeon.open_run.connect(self._open_run_id)
        self.score, self.group, self.pulls = ScoreTab(), GroupTab(), PullsTab()
        self.spells, self.summary = SpellsTab(), SummaryTab()
        self.tabs = QTabWidget()
        for w, name in ((self.score, "Score"), (self.group, "Group"), (self.pulls, "Pulls"),
                        (self.spells, "Spells"), (self.summary, "Summary")):
            self.tabs.addTab(w, name)
        self.timeline = Timeline()
        self.score.zoom.connect(self.timeline.set_view)
        self.pulls.zoom.connect(self.timeline.set_view)
        self.spells.highlight.connect(self.timeline.highlight)
        self.group.changed.connect(self._group_changed)
        # the Spells tab's highlight only makes sense while it's showing
        self.tabs.currentChanged.connect(lambda i: None if self.tabs.widget(i) is self.spells
                                         else self.timeline.highlight(None, None))
        self.group.forget.connect(self._forget_picks)
        scroll = QScrollArea()
        scroll.setWidget(self.timeline)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        tl = QWidget()
        tll = QVBoxLayout(tl)
        tll.setContentsMargins(0, 0, 0, 0)
        tll.addWidget(dim_label("Timeline - wheel to zoom, drag to pan, double-click for the whole run, hover for "
                                "details (shift+wheel scrolls down to everyone's rows)"))
        tll.addWidget(scroll, 1)
        run_page = QSplitter(Qt.Orientation.Vertical)
        run_page.addWidget(self.tabs)
        run_page.addWidget(tl)
        run_page.setSizes([430, 520])
        self.stack = QStackedWidget()
        self.stack.addWidget(self.dungeon)
        self.stack.addWidget(run_page)
        self.fight_detail = FightDetail()
        self.stack.addWidget(self.fight_detail)          # 2
        self.habits_page = HabitsPage()
        self.stack.addWidget(self.habits_page)           # 3
        self.fight_list.picked.connect(self.fight_detail.show_fight)
        self.fight_list.itemClicked.connect(lambda _i: self._mode("fights") if self.mode_habits.isChecked() else None)
        rw = QWidget()
        rl = QVBoxLayout(rw)
        rl.setContentsMargins(8, 8, 8, 8)
        rl.addWidget(self.stack)

        split = QSplitter()
        split.addWidget(left)
        split.addWidget(rw)
        split.setSizes([280, 1220])
        self.setCentralWidget(split)

        # follow the game's saves: the file is rewritten (sometimes replaced) on /reload and logout
        self.watcher = QFileSystemWatcher()
        self.watcher.fileChanged.connect(self._changed)
        self.watcher.directoryChanged.connect(self._changed)
        self.debounce = QTimer(singleShot=True, interval=1500)
        self.debounce.timeout.connect(self.reload)
        self.reload()

        # live: every fight summed up as it ends (overlay + the Fights page)
        self.live = live or LiveController(paths, self.settings)
        self.live.fight.connect(self.fight_list.add_fight)
        self.live.fight.connect(lambda _f: self._show_habits() if self.stack.currentIndex() == 3 else None)
        self.live.fight.connect(self._show_lag)
        self.fight_list.set_fights(self.live.history.fights)

    def _show_lag(self, *_):
        lag = self.live.live.lag
        self.lag.setVisible(lag is not None)
        if lag is not None:
            self.lag.setText(f"log delay {lag:.1f} s")

    # ------------------------------------------------------------------ loading
    def _changed(self, *_):
        self.debounce.start()

    def _watch(self):
        for paths in (self.watcher.files(), self.watcher.directories()):
            if paths:
                self.watcher.removePaths(paths)
        if self.saved and self.saved.exists():
            self.watcher.addPath(str(self.saved))
            self.watcher.addPath(str(self.saved.parent))
        # not the combat log: it grows all through combat, and runs only change when the game saves

    def reload(self):
        cur = self.tree.currentItem()
        keep = cur.data(0, RUN_ROLE) if cur else None
        had = set(self.by_id)
        try:
            self.saved, self.runs = analysis.load_saved(self.paths)
        except Exception as e:  # a half-written file while the game is saving: try again shortly
            self.status.setText(f"Couldn't read the saved file yet ({e}); retrying.")
            self.debounce.start()
            return
        if hasattr(self, "live"):      # the first reload runs before the controller exists; it loads them itself
            self.live.load_chars()
        self._watch()
        self.by_id = {r.id: r for r in self.runs}
        self.tree.blockSignals(True)
        self.tree.clear()
        bold = QFont()
        bold.setBold(True)
        select = None
        for zone, visits in analysis.dungeons(self.runs).items():
            top = QTreeWidgetItem([f"{zone}   ({len(visits)})"])
            top.setFont(0, bold)
            top.setData(0, RUN_ROLE, "zone:" + zone)
            self.tree.addTopLevelItem(top)
            for r in visits:
                child = QTreeWidgetItem([self._run_label(r)])
                child.setData(0, RUN_ROLE, r.id)
                top.addChild(child)
                if r.id == keep or (had and r.id not in had and select is None):
                    select = child
            if top.data(0, RUN_ROLE) == keep:
                select = select or top
            top.setExpanded(True)
        self.tree.blockSignals(False)
        if not self.runs:
            self.status.setText(f"No runs yet. Looking in {self.paths.accounts}")
            return
        who = self.paths.character_of(self.saved) if self.saved else "?"
        self.status.setText(f"{who} · {len(self.runs)} visits · updates when the game saves")
        if select is None:  # the newest visit
            top = self.tree.topLevelItem(0)
            select = top.child(0) if top and top.childCount() else top
        if self.tree.currentItem() is select:   # same item as before: no signal, so show it ourselves
            self._picked(select, None)
        else:
            self.tree.setCurrentItem(select)     # shows it (currentItemChanged)

    def _run_label(self, r: Run) -> str:
        a = self._cached(r)
        score = ""
        if a and not a.card.empty:
            score = f"   {a.card.total:.0f} {a.card.grade}"
        return f"{r.start_time:%a %d %b  %H:%M}{score}"

    def _key(self, run: Run) -> tuple:
        logs = tuple((p.name, p.stat().st_mtime) for p in sorted(self.paths.logs.glob("WoWCombatLog*.txt")))
        picks = self.paths.roster_file.stat().st_mtime if self.paths.roster_file.exists() else 0
        return (run.id, run.line_count, logs, picks)

    def _cached(self, run: Run) -> Analysis | None:
        return self.cache.get(self._key(run))

    def _analysis(self, run: Run) -> Analysis:
        key = self._key(run)
        if key not in self.cache:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                self.cache[key] = analysis.analyze(run, self.paths)
            finally:
                QApplication.restoreOverrideCursor()
        return self.cache[key]

    # ------------------------------------------------------------------ showing
    def _picked(self, it: QTreeWidgetItem | None, _prev=None):
        if it is None or self.left_stack.currentIndex() == 1:
            return
        key = it.data(0, RUN_ROLE) or ""
        if key.startswith("zone:"):
            zone = key[5:]
            visits = analysis.dungeons(self.runs).get(zone, [])
            analyses = {}
            for r in visits:
                try:
                    analyses[r.id] = self._analysis(r)
                except Exception:
                    traceback.print_exc()
            self._refresh_labels()
            self.dungeon.show_dungeon(zone, visits, analyses)
            self.stack.setCurrentIndex(0)
            return
        run = self.by_id.get(key)
        if run:
            self._show_run(run)

    def _show_run(self, run: Run):
        try:
            self.current = self._analysis(run)
        except Exception:
            traceback.print_exc()
            self.current = None
            self.score.card.show_card(run.zone, "Couldn't analyze this run - see the terminal.", None, None)
            self.stack.setCurrentIndex(1)
            return
        a = self.current
        for tab in (self.score, self.group, self.pulls, self.spells, self.summary):
            tab.set_analysis(a)
        self.timeline.set_analysis(a)
        self.stack.setCurrentIndex(1)
        self._refresh_labels()

    def _mode(self, which: str):
        self.mode_dungeons.setChecked(which == "dungeons")
        self.mode_fights.setChecked(which == "fights")
        self.mode_habits.setChecked(which == "habits")
        self.left_stack.setCurrentIndex(0 if which == "dungeons" else 1)
        if which == "habits":
            self._show_habits()
        elif which == "fights":
            self.stack.setCurrentIndex(2)
            if self.fight_list.currentRow() < 0 and self.fight_list.count():
                self.fight_list.setCurrentRow(0)
            elif not self.fight_list.count():
                self.fight_detail.show_fight(None)
        elif self.tree.currentItem() is None:
            self.stack.setCurrentIndex(0)      # no runs yet: _picked would return early and leave the old page
        else:
            self._picked(self.tree.currentItem())

    def _show_habits(self):
        h = self.live.history
        me = h.fights[-1]["me"] if h.fights else ""
        self.habits_page.show_habits(habits(h.fights, h.chars.get(me), h.book(me) if me else None))
        self.stack.setCurrentIndex(3)

    def _open_settings(self):
        if self.settings_dialog is None:
            d = SettingsDialog(self.paths, self.settings["theme"], self, self.settings)
            d.theme_changed.connect(self._set_theme)
            d.texture_changed.connect(lambda: self._set_theme(self.settings["theme"]))
            d.assets_rescanned.connect(lambda: self._set_theme(self.settings["theme"]))
            d.open_weights.connect(self._open_weights)
            d.test_overlay.connect(self.live.show_last)
            d.imported.connect(self._imported)
            self.settings_dialog = d
        self.settings_dialog.show()
        self.settings_dialog.raise_()

    def _set_theme(self, name: str):
        """switch the look and redraw everything open"""
        self.settings["theme"] = name
        app_settings.save(self.paths, self.settings)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            apply_look(self.paths, self.settings)
        finally:
            QApplication.restoreOverrideCursor()
        self._redraw()

    def _imported(self):
        self.live.history.load()
        self.fight_list.set_fights(self.live.history.fights)
        self._mode("habits" if self.mode_habits.isChecked() else "fights")

    def _redraw(self):
        """re-show what's open, so widgets that set their own colors pick up the theme"""
        tab = self.tabs.currentIndex()
        view = (self.timeline.v0, self.timeline.v1)
        self.fight_list.set_fights(self.live.history.fights)
        if self.stack.currentIndex() == 3:
            self._show_habits()
        elif self.stack.currentIndex() == 2:
            self.fight_detail.show_fight(self.fight_list.fights[self.fight_list.currentRow()]
                                         if self.fight_list.currentRow() >= 0 else None)
        elif self.stack.currentIndex() == 1 and self.current:
            self._show_run(self.current.data.run)
            self.tabs.setCurrentIndex(tab)
            self.timeline.set_view(*view)
        else:
            self._picked(self.tree.currentItem())
        self._refresh_labels()

    def _open_weights(self):
        if self.weights is None:
            self.weights = WeightsDialog(self.paths, self)
            self.weights.changed.connect(self.rescore_timer.start)
        self.weights.show()
        self.weights.raise_()

    def _rescore(self):
        """new weights: score every analyzed visit again and redraw what's showing"""
        for a in self.cache.values():
            analysis.rescore(a)
        self._refresh_labels()
        if self.stack.currentIndex() == 1 and self.current:
            rows = self.score.fights.selectionModel().selectedRows()
            self.score.set_analysis(self.current)
            if rows:
                self.score.fights.selectRow(rows[0].row())
        else:
            self._picked(self.tree.currentItem())

    def _refresh_labels(self):
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            for j in range(top.childCount()):
                child = top.child(j)
                run = self.by_id.get(child.data(0, RUN_ROLE))
                if run:
                    child.setText(0, self._run_label(run))

    def _open_run_id(self, rid: str):
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            for j in range(top.childCount()):
                if top.child(j).data(0, RUN_ROLE) == rid:
                    self.tree.setCurrentItem(top.child(j))
                    return

    def _group_changed(self, guid: str, cls: str, role: str):
        Overrides(self.paths.roster_file).set(guid, cls, role)
        self._reshow(keep_tab=True)

    def _forget_picks(self):
        if not self.current:
            return
        o = Overrides(self.paths.roster_file)
        for g in self.current.roster:
            o.clear(g)
        self._reshow(keep_tab=True)

    def _reshow(self, keep_tab: bool):
        tab = self.tabs.currentIndex()
        view = (self.timeline.v0, self.timeline.v1)
        if self.current:
            self._show_run(self.current.data.run)
        if keep_tab:
            self.tabs.setCurrentIndex(tab)
            self.timeline.set_view(*view)


def apply_look(paths: Paths, settings: dict):
    """theme, then the dips-Core texture, then the style for both"""
    theme.apply(settings["theme"])
    on, alpha, _ = app_settings.texture_choice(paths, settings)
    theme.set_texture(texture.tile(paths, alpha) if on else None)
    QApplication.instance().setStyleSheet(theme.stylesheet())


def run_app(paths: Paths) -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    apply_look(paths, app_settings.load(paths))
    load_weights(paths.weights_file)
    load_upkeep(paths.classes_file)
    w = Window(paths)
    w.show()
    return app.exec()

