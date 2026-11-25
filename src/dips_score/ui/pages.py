"""The Debrief tab and the dungeon page (its History, Bosses and Records tabs are historytab.py, bossestab.py and
recordstab.py); Pulls is pulls.py, Spells is spells.py, Group is group.py."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (QAbstractItemView, QComboBox, QFrame, QHeaderView, QLabel, QScrollArea, QTableWidget,
                             QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)

from .. import names
from ..analysis import Analysis
from ..debrief import (DebriefView, build_view, combat_figures, combat_span, fight_cells, fight_of, fmt_time, run_auto_share,
                       worst_fight)
from ..dungeon_view import build_bosses, build_history, build_records, history_meta, visits
from ..scoring.group import ordinal, player_card
from ..scoring.score import Scorecard
from ..sources.savedvars import Run
from ..timeline_view import fight_window
from . import assets
from .bossestab import BossesTab
from .debrief import DebriefPage
from .historytab import HistoryTab
from .recordstab import RecordsTab
from .timeline import text_color


def fmt_num(n: float) -> str:
    if n >= 1e6:
        return f"{n / 1e6:.1f}M"
    if n >= 1e4:
        return f"{n / 1e3:.0f}K"
    if n >= 1e3:
        return f"{n / 1e3:.1f}K"
    return f"{n:.0f}"


def table(headers: list[str], stretch: int | None = None) -> QTableWidget:
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.verticalHeader().setVisible(False)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    hh = t.horizontalHeader()
    hh.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    if stretch is not None:
        hh.setSectionResizeMode(stretch, QHeaderView.ResizeMode.Stretch)
    return t


def item(text, color: QColor | None = None, align_right: bool = False, data=None) -> QTableWidgetItem:
    it = QTableWidgetItem(str(text))
    if color is not None:
        it.setForeground(color)
    if align_right:
        it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    if data is not None:
        it.setData(Qt.ItemDataRole.UserRole, data)
    return it


def dim_label(text: str = "") -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("dim")
    lbl.setWordWrap(True)
    return lbl


# ============================================================================ Debrief
ROLE_NAME = {"dps": "DPS"}


def run_meta(a: Analysis, role: bool = True) -> str:
    """a run page's meta line: when, how long, in combat, fights, and (role) the role you were scored as"""
    rd = a.data
    parts = f" ({len(rd.run.parts)} pieces)" if len(rd.run.parts) > 1 else ""
    sub = (f"{rd.run.start_time:%a %d %b %H:%M}{parts} · {fmt_time(rd.duration)} long · "
           f"{fmt_time(a.metrics.combat_time)} in combat · {len(rd.fights)} fights")
    return sub if a.card.empty or not role else f"{sub} · as {ROLE_NAME.get(a.card.role, a.card.role)}"


class ScoreTab(QWidget):
    """the Debrief tab: a player's debrief for the whole run, or for the fight picked. You get your full
    scorecard; anyone else is scored from the combat log alone (as on the Group tab)."""
    zoom = pyqtSignal(float, float)     # a fight picked: where the timeline should show (Show me is page.zoom)

    def __init__(self):
        super().__init__()
        self.a: Analysis | None = None
        self.fight = -1                    # the fight showing; -1: the whole run
        self.cards: list[Scorecard] = []   # the picked player's card for each fight
        self.others: list[float] = []      # your runs' shares in combat, up to this one (app.py sets it)
        self.span = None                   # the run's time in combat and length (debrief.combat_span)
        self.cells: list = []
        self.deaths: list = []             # the picked player's
        self.page = DebriefPage()
        self.page.picked.connect(self._pick)
        self.who = QComboBox()
        self.who.setMinimumWidth(220)
        self.who.currentIndexChanged.connect(self._who_changed)
        self.page.head.addWidget(dim_label("Player"), 0, Qt.AlignmentFlag.AlignTop)
        self.page.head.addWidget(self.who, 0, Qt.AlignmentFlag.AlignTop)
        scroll = QScrollArea()          # small windows: scroll rather than squeeze
        scroll.setWidget(self.page)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(scroll)

    # ------------------------------------------------------------------ who
    def _guid(self) -> str | None:
        return self.who.currentData()

    def _is_me(self) -> bool:
        a = self.a
        return bool(a) and self._guid() == a.data.player_guid

    def set_analysis(self, a: Analysis | None):
        keep = self._guid()
        self.a = a
        self.who.blockSignals(True)
        self.who.clear()
        if a:
            ranks = {pl.guid: pl.rank for pl in a.ranking}
            players = sorted(a.roster.values(), key=lambda p: (not p.is_me, ranks.get(p.guid, 9)))
            for p in players:
                place = f"  ({ordinal(ranks[p.guid])})" if p.guid in ranks else ""
                self.who.addItem(p.name + (" (you)" if p.is_me else "") + place, p.guid)
                if (ic := assets.icon(assets.class_icon_name(p.cls) or "")) is not None:
                    self.who.setItemIcon(self.who.count() - 1, ic)
                self.who.setItemData(self.who.count() - 1, text_color(p), Qt.ItemDataRole.ForegroundRole)
            idx = self.who.findData(keep) if keep else -1
            self.who.setCurrentIndex(idx if idx >= 0 else 0)   # you, by default
        self.who.blockSignals(False)
        self._who_changed()

    def _who_changed(self):
        a, guid = self.a, self._guid()
        self.cards, self.cells, self.deaths = [], [], []
        if a and guid:
            p = a.roster[guid]
            me = self._is_me()
            self.who.setToolTip(
                "your full scorecard, from the add-on and the combat log" if me else
                f"scored from the combat log as {(p.role or 'DPS').lower() if p.role != 'DPS' else 'a damage dealer'} "
                f"(the add-on only records your own presses and movement)")
            self.cards = [fr.card if me else player_card(a, guid, [(fr.fight.start, fr.fight.end)]) for fr in a.fights]
            self.cells = fight_cells(a, guid, self.cards)
            self.deaths = [d for d in a.deaths if d.guid == guid]
        self.show_whole()

    # ------------------------------------------------------------------ showing
    def _window(self, i: int) -> tuple[float, float]:
        f = self.a.fights[i].fight
        return fight_window(f.start, f.end)

    def _show(self, card: Scorecard, share: float | None, deaths: int, title: str, sub: str, fight: int | None,
              m=None):
        """fight: where "Show me" zooms (None: the fight whose card lost the most in the fix's category); m: your
        Metrics for the melee share line (None: another player's, not measured)"""
        view = build_view(card, self.cells, share, deaths, self._is_me())
        view.auto_share = run_auto_share(m) if m is not None and view.categories else None
        if view.fix and fight is None:
            fight = worst_fight(self.cards, view.fix.category)
        role = ROLE_NAME.get(card.role, card.role)
        whose = "your" if self._is_me() else f"{self.a.roster[self._guid()].name}'s"
        self.page.show_view(view, title, sub if card.empty else f"{sub} · as {role}",
                            self._window(fight) if view.fix and fight is not None else None, whose, self.fight >= 0)

    def set_others(self, others: list[float]):
        """your runs' shares in combat, up to this one: the range beside its own, on the whole run's debrief"""
        self.others = others
        if self.fight < 0:
            self.page.combat.set(combat_figures(self.span, others))

    def show_whole(self):
        a = self.a
        self.fight = -1
        if not a or not self._guid():
            self.span = None
            self.page.combat.set([])
            self.page.show_view(DebriefView(), "No run selected", "")
            return
        rd = a.data
        zone = names.titled(rd.run.id, rd.run.zone)
        when = run_meta(a, role=False)     # _show adds the role of the card it shows
        self.span = combat_span(a)
        self.page.combat.set(combat_figures(self.span, self.others))
        if self._is_me():
            sync = "; ".join(s.describe() for s in rd.sync if s.anchors) or "no clock anchors"
            if rd.has_combat_log and not rd.has_advanced:
                sync += " · advanced logging: off"
            self._show(a.card, a.damage[1] if a.damage else None, len(self.deaths), zone,
                       f"{when} · sync: {sync}", None, a.metrics)
            return
        pl = next((x for x in a.ranking if x.guid == self._guid()), None)
        p = a.roster[self._guid()]
        sub = when + (f" · placed {ordinal(pl.rank)} of {len(a.ranking)}" if pl else "")
        self._show(pl.card if pl else player_card(a, p.guid), None, len(self.deaths), f"{p.name} - {zone}",
                   sub, None)

    def _pick(self, i: int):
        """a fight picked (or Whole run): its debrief, and the Timeline tab zoomed to the fight; a rescore redraws
        with show_fight, so it stays on the tab it's on"""
        self.show_fight(i)
        if self.fight >= 0:
            self.zoom.emit(*self._window(self.fight))

    def show_fight(self, i: int):
        """one fight's debrief (-1: the whole run)"""
        a = self.a
        if not a or not self._guid() or not 0 <= i < len(a.fights):
            self.show_whole()
            return
        self.fight = i
        self.page.combat.set([])        # the run's, not a fight's
        fr = a.fights[i]
        f = fr.fight
        me = self._is_me()
        kill = "" if f.killed is None else (" - killed" if f.killed else " - wipe")
        who = "" if me else f"{a.roster[self._guid()].name} · "
        deaths = len(fight_of(self.deaths, a.data.fights).get(i, []))
        zone = names.titled(a.data.run.id, a.data.run.zone)
        self._show(self.cards[i], fr.damage[1] if me and fr.damage else None, deaths, f"{f.label}{kill}",
                   f"{who}{zone} · at {fmt_time(f.start)} · {f.duration:.0f}s", i, fr.metrics if me else None)


# ============================================================================ Dungeon page
class DungeonPage(QTabWidget):
    """a dungeon's page, in text tabs like a run's: History (your score on every visit; historytab.py), Bosses (each
    boss on the last visit; bossestab.py) and Records (your bests here; recordstab.py)"""
    open_run = pyqtSignal(str)   # run id
    show_fight = pyqtSignal(str, float, float)      # a visit's run id, and where its timeline should show

    def __init__(self):
        super().__init__()
        self.pairs: list[tuple[Run, Analysis | None]] = []     # each visit, newest first, and its analysis
        self.history, self.bosses, self.records = HistoryTab(), BossesTab(), RecordsTab()
        self.history.open_run.connect(self.open_run)
        self.bosses.show_fight.connect(self.show_fight)
        self.records.open_run.connect(self.open_run)
        self.records.to_bosses.connect(lambda: self.setCurrentWidget(self.bosses))
        for tab, name in ((self.history, "History"), (self.bosses, "Bosses"), (self.records, "Records")):
            self.addTab(tab, name)

    def show_dungeon(self, zone: str, runs: list[Run], analyses: dict[str, Analysis]):
        """runs: the dungeon's visits; analyses: theirs by run id (one that couldn't be analysed is missing)"""
        self.pairs = [(r, analyses.get(r.id)) for r in runs]
        view = build_history(visits(self.pairs))
        meta = history_meta(view)
        self.history.show_view(zone, meta, view)
        rows, weakest, average = build_bosses(self.pairs)
        self.bosses.show_view(zone, meta, rows, weakest, average, view)
        self.records.show_view(zone, meta, *build_records(self.pairs), view, rows)
