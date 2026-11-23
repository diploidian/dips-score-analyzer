"""The window.

Left, the rail: Dungeons, Raids, Fights and Habits, then the dungeons, each opening into its visits. Right: picking a
dungeon shows its page (your score on every visit); picking a visit shows its tabs (Debrief, Timeline, Pulls,
Spells, Group). The window watches the add-on's saved file and reloads when the game saves (/reload, logout);
a new visit opens by itself.
"""
from __future__ import annotations

import sys
import traceback
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QFileSystemWatcher, QStandardPaths, Qt, QTimer
from PyQt6.QtGui import QFont, QGuiApplication, QKeySequence, QShortcut
from PyQt6.QtWidgets import (QApplication, QButtonGroup, QHBoxLayout, QInputDialog, QLabel, QMainWindow, QMenu,
                             QMessageBox, QPushButton, QSplitter, QStackedWidget, QTabWidget, QTreeWidget,
                             QTreeWidgetItem, QVBoxLayout, QWidget)

from .. import analysis, names, removed
from ..analysis import Analysis
from ..config import Paths
from ..debrief import DebriefView
from ..fight_view import run_window
from ..model.roster import Overrides
from ..scoring.classes import load_upkeep
from ..scoring.score import load_weights
from ..sources.savedvars import Run
from . import settings as app_settings
from . import share, texture, theme
from .group import GroupTab
from .pages import DungeonPage, ScoreTab, dim_label
from .pulls import PullsTab
from .spells import SpellsTab
from .timelinetab import TimelineTab
from .settings import SettingsDialog
from .tokens import THEMES
from ..live.habits import habits
from ..live.tail import LogTail
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
        names.load(paths.names_file)
        removed.load(paths.removed_file)
        self.setWindowTitle("dips score")
        self.resize(1500, 950)

        # ---- left: dungeons and their visits
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setMinimumWidth(260)
        self.tree.currentItemChanged.connect(self._picked)
        left = QWidget()
        left.setObjectName("rail")
        nav = QVBoxLayout(left)                 # the nav list runs edge to edge; the rest sits inside `ll`
        nav.setContentsMargins(0, 14, 0, 14)
        nav.setSpacing(0)
        self.mode_dungeons = QPushButton("Dungeons")
        self.mode_raids = QPushButton("Raids")
        self.mode_fights = QPushButton("Fights")
        self.mode_habits = QPushButton("Habits")
        for b in (self.mode_dungeons, self.mode_raids, self.mode_fights, self.mode_habits):
            b.setCheckable(True)
            b.setProperty("nav", "1")           # flat text items, themed in theme.stylesheet
            nav.addWidget(b)
        self.mode_dungeons.setChecked(True)
        self.raid = False                       # the tree holds raids (Raids) or the rest (Dungeons), in every mode
        self.mode_dungeons.clicked.connect(lambda: self._mode("dungeons"))
        self.mode_raids.clicked.connect(lambda: self._mode("raids"))
        self.mode_fights.clicked.connect(lambda: self._mode("fights"))
        self.mode_habits.clicked.connect(lambda: self._mode("habits"))
        ll = QVBoxLayout()
        ll.setContentsMargins(8, 12, 8, 0)
        nav.addLayout(ll, 1)
        self.fight_list = FightList()
        self.left_stack = QStackedWidget()
        self.left_stack.addWidget(self.tree)
        self.left_stack.addWidget(self.fight_list)
        ll.addWidget(self.left_stack, 1)
        ll.addSpacing(10)                       # the lists sit on the rail: keep a cut-off last row off the status
        self.status = dim_label()               # what's loaded, then the log delay (see _status)
        self.status_text = ""
        ll.addWidget(self.status)
        ll.addSpacing(14)
        look = QLabel("LOOK")
        look.setObjectName("look")      # themed in theme.stylesheet (Barlow Condensed 600)
        ll.addWidget(look)
        self.look_buttons: dict[str, QPushButton] = {}
        self.theme_group, self.mode_group = QButtonGroup(self), QButtonGroup(self)
        for key, label, group in (*((k, n, self.theme_group) for k, n in (("classical", "Classical"),
                                                                           ("timeless", "Timeless"))),
                                  *((k, n, self.mode_group) for k, n in (("day", "Day"), ("night", "Night"),
                                                                          ("auto", "Auto")))):
            b = QPushButton(label)
            b.setCheckable(True)
            group.addButton(b)
            self.look_buttons[key] = b
            b.clicked.connect(lambda _c, k=key: self._set_look(theme=k) if k in THEMES else self._set_look(mode=k))
        for keys in (("classical", "timeless"), ("day", "night", "auto")):
            r = QHBoxLayout()
            r.setSpacing(0)
            for k in keys:
                b = self.look_buttons[k]
                b.setProperty("seg", "1")
                b.setProperty("last", "1" if k == keys[-1] else "0")
                r.addWidget(b)
            ll.addLayout(r)
        links = QHBoxLayout()
        links.setContentsMargins(0, 8, 0, 0)
        links.setSpacing(16)
        for text, slot in (("Settings", self._open_settings), ("Reload", self.reload), ("Share", self._share)):
            b = QPushButton(text)
            b.setObjectName("link")             # quiet text links, themed in theme.stylesheet
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFocusPolicy(Qt.FocusPolicy.TabFocus)    # a click doesn't leave it underlined
            b.clicked.connect(slot)
            links.addWidget(b)
        links.addStretch(1)
        ll.addLayout(links)
        QShortcut(QKeySequence("Ctrl+Shift+C"), self, self._share)
        QShortcut(QKeySequence("F2"), self, self._rename)
        QShortcut(QKeySequence("Del"), self, self._delete)
        for view in (self.tree, self.fight_list):       # right-click a run or a fight: Rename…, Delete…
            view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            view.customContextMenuRequested.connect(lambda pos, v=view: self._rename_menu(v, pos))
        self.share_folder = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.PicturesLocation),
                                 "dips-score")
        self.weights: WeightsDialog | None = None
        self.settings_dialog: SettingsDialog | None = None
        # opened from the tray: share the controller's settings, so changes here reach the overlay
        self.settings = live.settings if live else app_settings.load(paths)
        self._sync_look_buttons()
        QGuiApplication.styleHints().colorSchemeChanged.connect(
            lambda *_: self._set_look() if self.settings["mode"] == "auto" else None)
        self.rescore_timer = QTimer(singleShot=True, interval=120)   # sliders move fast: score once they pause
        self.rescore_timer.timeout.connect(self._rescore)

        # ---- right: the dungeon page, or a run's tabs
        self.dungeon = DungeonPage()
        self.dungeon.open_run.connect(self._open_run_id)
        # Bosses' "Show the fight": that visit, its Timeline tab at the fight
        self.dungeon.show_fight.connect(lambda rid, a, b: (self._open_run_id(rid), self.show_on_timeline(a, b)))
        self.score, self.group, self.pulls = ScoreTab(), GroupTab(), PullsTab()
        self.score.page.settings = self.settings
        self.spells = SpellsTab()
        self.timeline_tab = TimelineTab()        # the fight picker and the idle verdict over the lanes
        self.timeline = self.timeline_tab.timeline
        self.tabs = QTabWidget()
        for w, name in ((self.score, "Debrief"), (self.timeline_tab, "Timeline"), (self.pulls, "Pulls"),
                        (self.spells, "Spells"), (self.group, "Group")):
            self.tabs.addTab(w, name)
        # only the "Show ..." buttons switch to the Timeline tab; a pick readies the timeline and stays where it is
        self.score.page.zoom.connect(self.show_on_timeline)   # Show me
        self.score.zoom.connect(self._set_timeline)           # a fight picked
        self.pulls.zoom.connect(self._set_timeline)           # a pull picked
        self.pulls.show_me.connect(self.show_on_timeline)     # Show this pull
        self.spells.show_me.connect(self.show_on_timeline)    # Show on the timeline (the ability to fix)
        self.group.show_me.connect(self.show_on_timeline)     # Show your death
        # a spell picked lights up on the timeline; a refill only clears it
        self.spells.highlight.connect(lambda guid, spell: self._set_timeline(None, None, guid, spell) if guid
                                      else self.timeline.highlight(None, None))
        self.group.changed.connect(self._group_changed)
        self.tabs.currentChanged.connect(self._tab_changed)
        self.group.forget.connect(self._forget_picks)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.dungeon)
        self.stack.addWidget(self.tabs)
        self.fight_detail = FightDetail()
        self.stack.addWidget(self.fight_detail)          # 2
        self.habits_page = HabitsPage()
        self.stack.addWidget(self.habits_page)           # 3
        self.habits_page.open_fights.connect(lambda: self._mode("fights"))     # R8: the list stays unfiltered
        self.fight_list.picked.connect(self._show_fight)
        self.fight_detail.show_me.connect(self._fight_on_timeline)     # Show on the timeline (R7: the loaded run)
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
        self.live.fight.connect(lambda _f: self._status())
        self.fight_list.set_fights(self.live.history.fights)

    def _status(self, text: str | None = None):
        """the rail's quiet line: what's loaded (when given), then the log delay once a fight has measured it"""
        if text is not None:
            self.status_text = text
        lag = self.live.live.lag if hasattr(self, "live") else None    # the first reload runs before the controller
        self.status.setText(self.status_text + ("" if lag is None else f" · log delay {lag:.1f} s"))
        self.status.setToolTip("" if lag is None else
                               "Log delay: how long the game takes to write a fight to its log file. "
                               "The app cannot shorten it.")

    # ------------------------------------------------------------------ loading
    def _changed(self, *_):
        self.debounce.start()

    def _watch(self):
        for paths in (self.watcher.files(), self.watcher.directories()):
            if paths:
                self.watcher.removePaths(paths)
        if self.saved and self.saved.exists():
            self.watcher.addPath(str(self.saved))
        # every character's folder, so a first save (or another character's) is noticed too
        # shortcut: a character or realm created after the app opened isn't watched until the next reload
        dirs = [str(d) for d in self.paths.accounts.glob("*/*/*") if d.is_dir()]
        dirs += [str(d) for d in self.paths.accounts.glob("*/*/*/SavedVariables")]
        if dirs:
            self.watcher.addPaths(dirs)
        # not the combat log: it grows all through combat, and runs only change when the game saves

    def reload(self):
        cur = self.tree.currentItem()
        keep = cur.data(0, RUN_ROLE) if cur else None
        had = set(self.by_id)
        try:
            self.saved, self.runs = analysis.load_saved(self.paths)
        except Exception as e:  # a half-written file while the game is saving: try again shortly
            self._status(f"Couldn't read the saved file yet ({e}); retrying.")
            self.debounce.start()
            return
        if hasattr(self, "live"):      # the first reload runs before the controller exists; it loads them itself
            self.live.load_chars()
        self._watch()
        self.by_id = {r.id: r for r in self.runs}
        new = [r for r in self.runs if had and r.id not in had]
        if new and all((r.kind == "raid") != self.raid for r in new):    # the game saved a visit of the other section
            self.raid = not self.raid
            if self.left_stack.currentIndex() == 0:
                self.mode_dungeons.setChecked(not self.raid)
                self.mode_raids.setChecked(self.raid)
        self._fill_tree(keep, had)

    def _fill_tree(self, keep: str | None, had: set):
        """the section's dungeons and their visits; opens the visit `keep` (or a fresh one, or the newest)"""
        self.tree.blockSignals(True)
        self.tree.clear()
        bold = QFont()
        bold.setBold(True)
        select = fresh = None
        for zone, visits in analysis.dungeons(self.runs, raid=self.raid).items():
            top = QTreeWidgetItem([f"{zone}   ({len(visits)})"])
            top.setFont(0, bold)
            top.setData(0, RUN_ROLE, "zone:" + zone)
            self.tree.addTopLevelItem(top)
            for r in visits:
                child = QTreeWidgetItem([self._run_label(r)])
                child.setToolTip(0, f"{r.start_time:%a %d %b  %H:%M}")     # the date, when a name is in its place
                child.setData(0, RUN_ROLE, r.id)
                top.addChild(child)
                if r.id == keep:
                    select = child
                if had and r.id not in had and fresh is None:    # a visit the game just saved
                    fresh = child
            if top.data(0, RUN_ROLE) == keep:
                select = select or top
            top.setExpanded(True)
        self.tree.blockSignals(False)
        select = fresh or select        # a new visit opens by itself, over the one you were on
        if not self.runs:
            self._status(f"No runs yet. Looking in {self.paths.accounts}" if self.paths.found() else
                         f"Game folder not found: {self.paths.wow}. Pick it in Settings.")
            return
        if self.raid and not self.tree.topLevelItemCount():    # the add-on records raids only with its Raids option on
            self._status("No raids recorded. Tick Raids in the add-on's options (/dscore).")
            return
        who = self.paths.character_of(self.saved) if self.saved else "?"
        self._status(f"{who} · {len(self.runs)} visits · updates when the game saves")
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
        when = names.get(r.id) or f"{r.start_time:%a %d %b  %H:%M}"     # your name for it, else its date
        return f"{when}{score}"

    def _key(self, run: Run) -> tuple:
        picks = self.paths.roster_file.stat().st_mtime if self.paths.roster_file.exists() else 0
        return analysis.run_key(run, sorted(self.paths.logs.glob("WoWCombatLog*.txt")), picks)

    def _cached(self, run: Run) -> Analysis | None:
        return self.cache.get(self._key(run))

    def _analysis(self, run: Run) -> Analysis:
        key = self._key(run)
        if key not in self.cache:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                a = analysis.analyze(run, self.paths)
            finally:
                QApplication.restoreOverrideCursor()
            for old in [k for k in self.cache if k[0] == run.id]:    # one analysis per run, the newest
                del self.cache[old]
            self.cache[key] = a
        return self.cache[key]

    # ------------------------------------------------------------------ showing
    def _picked(self, it: QTreeWidgetItem | None, _prev=None):
        if it is None:
            return
        key = it.data(0, RUN_ROLE) or ""
        if self.left_stack.currentIndex() == 1:     # Fights or Habits: a reload's visit still loads behind the page,
            if key in self.by_id:                   # so its fights get Show on the timeline (R7)
                page = self.stack.currentIndex()
                self._show_run(self.by_id[key])
                self.stack.setCurrentIndex(page)
                if page == 2:
                    self._show_fight(self._fight())
            return
        if key.startswith("zone:"):
            zone = key[5:]
            visits = analysis.dungeons(self.runs, raid=self.raid).get(zone, [])
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
        for tab in (self.score, self.group, self.pulls, self.spells, self.timeline_tab):
            tab.set_analysis(self.current)      # None: no tab keeps showing the last run
        if self.current is None:
            self.score.page.show_view(DebriefView(), names.titled(run.id, run.zone),
                                      "Couldn't analyze this run - see the terminal.")
        self.stack.setCurrentIndex(1)
        self._refresh_labels()

    def _tab_changed(self, i: int):
        if self.tabs.widget(i) not in (self.spells, self.timeline_tab):   # a spell's pick lasts while it's in view
            self.spells.pick(None)          # unlit on the timeline too (its highlight signal)

    def _set_timeline(self, start: float | None = None, end: float | None = None, guid: str | None = None,
                      spell: str | None = None):
        """the timeline zoomed to start..end and a player's spell lit up, each when given, without leaving the tab;
        the Timeline tab's picker follows the view"""
        if start is not None and end is not None:
            self.timeline.set_view(start, end)
            self.timeline_tab.follow(start, end)
        if guid:
            self.timeline.highlight(guid, spell)

    def show_on_timeline(self, start: float, end: float, guid: str | None = None, spell: str | None = None):
        """the Timeline tab, zoomed to start..end, and with a player's spell lit up when given"""
        self._set_timeline(start, end, guid, spell)
        self.tabs.setCurrentWidget(self.timeline_tab)

    def _mode(self, which: str):
        self.mode_dungeons.setChecked(which == "dungeons")
        self.mode_raids.setChecked(which == "raids")
        self.mode_fights.setChecked(which == "fights")
        self.mode_habits.setChecked(which == "habits")
        self.left_stack.setCurrentIndex(0 if which in ("dungeons", "raids") else 1)
        if which == "habits":
            self._show_habits()
        elif which == "fights":
            self.stack.setCurrentIndex(2)
            if self.fight_list.currentRow() < 0 and self.fight_list.count():
                self.fight_list.setCurrentRow(0)
            else:      # shown again, against the run loaded now
                self._show_fight(self._fight())
        elif (which == "raids") != self.raid:      # the other section: its tree, opened on its newest visit
            self.raid = which == "raids"
            self._fill_tree(None, set())
            if self.tree.currentItem() is None:
                self.stack.setCurrentIndex(0)
        elif self.tree.currentItem() is None:
            self.stack.setCurrentIndex(0)      # no runs yet: _picked would return early and leave the old page
        else:
            self._picked(self.tree.currentItem())

    def _fight(self) -> dict | None:
        """the fight picked in the list"""
        row = self.fight_list.currentRow()
        return self.fight_list.fights[row] if row >= 0 else None

    def _show_fight(self, f: dict | None):
        """a live fight on its page, with Show on the timeline only when it falls inside the loaded run (R7)"""
        d = self.current.data if self.current else None
        self.fight_detail.show_fight(f, run_window(f, d.start, d.duration) if f and d else None)

    def _fight_on_timeline(self, start: float, end: float):
        """a live fight's Show on the timeline: the loaded run's Timeline tab (the fight is inside it), zoomed to it"""
        self._open_run_id(self.current.data.run.id)      # in Fights mode the tree only takes the pick
        self._mode("raids" if self.raid else "dungeons")     # which shows the run's tabs again
        self.stack.setCurrentIndex(1)
        self.show_on_timeline(start, end)

    def _show_habits(self):
        h = self.live.history
        me = h.fights[-1]["me"] if h.fights else ""
        self.habits_page.show_habits(habits(h.fights, h.chars.get(me), h.book(me) if me else None))
        self.stack.setCurrentIndex(3)

    def _share(self):
        """the page showing (the tab picked, on a page of tabs) on the clipboard and saved as a PNG"""
        page, tab = self.stack.currentWidget(), ""
        if isinstance(page, QTabWidget):
            page, tab = page.currentWidget(), page.tabText(page.currentIndex())
        title = getattr(share.page_widget(page), "title", "")
        try:
            path = share.share(page, self.share_folder, " ".join(s for s in (title, tab) if s))
        except OSError as e:      # the folder can't be written: the clipboard has it anyway
            self._status(f"Copied to the clipboard · couldn't save it ({e})")
            return
        self._status(f"Copied to the clipboard · saved {path}")

    def _rename_menu(self, view, pos):
        it = view.itemAt(pos)
        if it is None:
            return
        view.setCurrentItem(it)
        if self._rename_id():
            menu = QMenu(self)
            menu.addAction("Rename…").triggered.connect(self._rename)
            menu.addAction("Delete…").triggered.connect(self._delete)
            menu.exec(view.viewport().mapToGlobal(pos))

    def _rename_id(self) -> str | None:
        """the run or fight picked in the rail's list showing (a dungeon row isn't renamed)"""
        if self.left_stack.currentIndex() == 0:
            it = self.tree.currentItem()
            key = it.data(0, RUN_ROLE) if it else None
            return key if key in self.by_id else None
        f = self._fight()
        return f.get("id") if f else None

    def _rename(self):
        rid = self._rename_id()
        if rid:
            text, ok = QInputDialog.getText(self, "Rename", "Your name for it (empty: none):", text=names.get(rid))
            if ok:
                self.set_name(rid, text)

    def set_name(self, rid: str, text: str):
        """your name for a run or fight (empty takes it off), on its rail row and its page"""
        try:
            names.rename(self.paths.names_file, rid, text)
        except OSError as e:      # names.json can't be written: the name lasts until the app closes
            self._status(f"Couldn't save the name ({e})")
        self._redraw()      # the rail's rows too

    def _delete(self):
        rid = self._rename_id()
        if not rid:
            return
        run = self.by_id.get(rid)
        ask = (f"Delete this run and the {len(self._fights_in(run))} fights in it? This can't be undone." if run
               else "Delete this fight? This can't be undone.")
        if QMessageBox.question(self, "Delete", ask) == QMessageBox.StandardButton.Yes:
            self.delete_item(rid)

    def _fights_in(self, run: Run) -> list[str]:
        """the ids of the fights that began inside a run (both naive local time, as in run_window)"""
        end = datetime.fromtimestamp(run.end_estimate)
        return [f["id"] for f in self.live.history.fights
                if run.start_time <= datetime.fromisoformat(f["start"]) <= end]

    def delete_item(self, rid: str):
        """a run (hidden: the game's saved file is its own) with the fights in it, or a fight"""
        run = self.by_id.get(rid)
        ids = [*run.parts, *self._fights_in(run)] if run else [rid]
        try:
            removed.add(self.paths.removed_file, ids)
            self.live.history.remove(ids)
            names.rename(self.paths.names_file, rid, "")
        except OSError as e:      # a file can't be written: it stays gone until the app closes
            self._status(f"Couldn't save the delete ({e})")
        if run:
            for k in [k for k in self.cache if k[0] == rid]:
                del self.cache[k]
            if self.current and self.current.data.run.id == rid:     # else _redraw shows it again
                self.current = None
            self.reload()
        self._redraw()

    def _open_settings(self):
        if self.settings_dialog is None:
            d = SettingsDialog(self.paths, self.settings["theme"], self, self.settings)
            d.theme_changed.connect(self._set_theme)
            d.texture_changed.connect(lambda: self._set_theme(self.settings["theme"]))
            d.assets_rescanned.connect(lambda: self._set_theme(self.settings["theme"]))
            d.open_weights.connect(self._open_weights)
            d.test_overlay.connect(self.live.show_last)
            d.imported.connect(self._imported)
            d.folders_changed.connect(self._folders_changed)
            d.overlay_changed.connect(self.live.refresh)
            d.move_overlay.connect(self.live.move_mode)
            self.settings_dialog = d
        self.settings_dialog.show()
        self.settings_dialog.raise_()

    def _folders_changed(self):
        # a fresh tail skips what's already in the new folder's log, like at start-up
        self.live.live.tail = LogTail(self.paths.logs)
        self.reload()

    def _set_theme(self, name: str):
        self._set_look(theme=name)

    def _sync_look_buttons(self):
        for k in (self.settings["theme"], self.settings["mode"]):
            self.look_buttons[k].setChecked(True)

    def _set_look(self, theme: str | None = None, mode: str | None = None):
        """switch the look and redraw everything open"""
        self.settings["theme"] = theme or self.settings["theme"]
        self.settings["mode"] = mode or self.settings["mode"]
        self._sync_look_buttons()
        if self.settings_dialog:
            self.settings_dialog.set_theme(self.settings["theme"])
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
            self._show_fight(self._fight())
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
        """new weights: score every analyzed visit again and redraw what's showing (the pages with scores on them),
        keeping the Debrief's fight, the Timeline's view and a spell lit from Spells"""
        for a in self.cache.values():
            analysis.rescore(a)
        self._refresh_labels()
        if self.stack.currentIndex() == 1 and self.current:
            fight = self.score.fight
            view, lit = (self.timeline.v0, self.timeline.v1), (self.timeline.hl_guid, self.timeline.hl_spell)
            for page in (self.score, self.group, self.timeline_tab):    # the Timeline keeps its scope (same run)
                page.set_analysis(self.current)
            if fight >= 0:
                self.score.show_fight(fight)
            self.timeline.set_view(*view)
            self.timeline.highlight(*lit)
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
    theme.load_fonts()
    os_dark = QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
    theme.apply(settings["theme"], settings["mode"], os_dark)
    on, alpha, _ = app_settings.texture_choice(paths, settings)
    theme.set_texture(texture.tile(paths, alpha) if on else None)
    QApplication.instance().setStyleSheet(theme.stylesheet())


def run_app(paths: Paths) -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    settings = app_settings.load(paths)
    if not paths.found():       # first start, or the game moved: ask rather than show an empty window
        found = app_settings.pick_wow(None, paths.wow)
        if found:
            paths.wow = found
            settings["wow_folder"] = str(found)
            app_settings.save(paths, settings)
    apply_look(paths, settings)     # after the pick: the dips-Core texture is in the game folder
    load_weights(paths.weights_file)
    load_upkeep(paths.classes_file)
    w = Window(paths)
    w.show()
    return app.exec()

