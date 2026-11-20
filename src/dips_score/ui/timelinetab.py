"""The Timeline tab's page: the fight picker over the lanes, how idle you were in what they show (the Activity score's
own gaps, see dips_score/timeline_view.py), then the longest idle moment on the plate beside every idle moment,
longest first.

The page speaks for its scope: a fight, the whole run, or a custom view. The picker, previous and next, and Whole run
set it; so does a view set from another page (follow), by the fight that view shows. Zooming in the tab (the wheel, a
drag, the plate's button) leaves it alone.

Sizes follow docs/design/mockups/timeline.html (CSS px). The shared parts come from kit.py, the lanes from timeline.py.
"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QPushButton, QScrollArea, QVBoxLayout

from ..debrief import fight_cells, fmt_time
from ..timeline_view import fight_window, idle_view, option_text, scope_for, step
from .debrief import NARROW
from .kit import HEAD_H, BarRow, BarRows, Hero, KeyFigures, Plate, Sheet
from .pages import dim_label, run_meta
from .timeline import Timeline

VERDICT_W = 576      # the verdict stops at 36em
FIGURES_W = 420
LIST_ROWS = 10       # the list's longest; the plate and the figures count them all


class IdleRows(BarRows):
    """the idle moments: the time, a bar filling what the row has left, the length"""
    name_w = 66

    def draw(self, p, w):
        self.bar_w = max(0.0, w - self.name_w - 78)
        return super().draw(p, w)


class TimelineTab(QScrollArea):
    """the Timeline tab: the page, scrolling when the window is small or the group is open"""

    def __init__(self):
        super().__init__()
        self.run_id = None
        self.cells, self.duration, self.combat, self.score = [], 0.0, "–", None
        self.scope = None            # a fight's index, None for the whole run, or (start, end) for a custom view
        self.moments, self.shown = [], 0
        self.narrow = None
        self.timeline = Timeline()
        self.pick = QComboBox()
        self.pick.setMinimumWidth(270)
        self.pick.setPlaceholderText("custom view")       # shown at index -1
        self.pick.currentIndexChanged.connect(self._picked)
        self.prev, self.next, self.whole = QPushButton("‹"), QPushButton("›"), QPushButton("Whole run")
        for b, name, d in ((self.prev, "Previous fight", -1), (self.next, "Next fight", 1)):
            b.setFixedWidth(32)
            b.setAccessibleName(name)
            b.setToolTip(name)
            b.clicked.connect(lambda _c, d=d: self._step(d))
        self.whole.clicked.connect(self._whole)
        self.hero, self.figures = Hero(), KeyFigures()
        self.hero.unit = (48, 42, 600, 12, 6)
        self.hero.setMaximumWidth(VERDICT_W)
        self.figures.setFixedWidth(FIGURES_W)
        self.plate, self.list = Plate("In this fight"), IdleRows("Idle moments, longest first")
        self.plate.clicked.connect(self._next_moment)

        strip = QHBoxLayout()
        strip.setContentsMargins(0, 12, 0, 12)
        strip.setSpacing(8)
        for wd in (self.prev, self.pick, self.next):
            strip.addWidget(wd)
        strip.addSpacing(10)
        note = dim_label("wheel to zoom · drag to pan")
        note.setWordWrap(False)
        strip.addWidget(note)
        strip.addStretch(1)
        strip.addWidget(self.whole)
        hero_row = QHBoxLayout()
        hero_row.setContentsMargins(0, 4, 0, 16)
        hero_row.setSpacing(0)
        hero_row.addWidget(self.hero, 100, Qt.AlignmentFlag.AlignTop)
        hero_row.addSpacing(28)
        hero_row.addStretch(1)
        hero_row.addWidget(self.figures, 0, Qt.AlignmentFlag.AlignBottom)
        after = QHBoxLayout()
        after.setContentsMargins(0, 30, 0, 0)
        after.setSpacing(40)
        after.addWidget(self.plate, 1, Qt.AlignmentFlag.AlignTop)
        after.addWidget(self.list, 1, Qt.AlignmentFlag.AlignTop)
        self.page = Sheet()
        lay = QVBoxLayout(self.page)
        lay.setContentsMargins(16, 4, 16, 16)
        lay.setSpacing(0)
        lay.addSpacing(HEAD_H)
        lay.addLayout(strip)
        lay.addLayout(hero_row)
        lay.addWidget(self.timeline)
        lay.addLayout(after)
        lay.addStretch(1)
        self.setWidget(self.page)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)

    # ------------------------------------------------------------------ the run
    def set_analysis(self, a):
        """a run on the lanes and in the picker; the same run again (a redraw, a reload) keeps the scope"""
        keep = a is not None and a.data.run.id == self.run_id
        self.run_id = a.data.run.id if a else None
        self.timeline.set_analysis(a)
        if a is None:
            self.show_run("No run selected", "", [], 0.0, "–", None)
            return
        card = a.card
        score = None if card.empty or card.grade == "-" else f"{card.total:.0f} {card.grade}"
        self.show_run(a.data.run.zone, run_meta(a), fight_cells(a), a.data.duration, fmt_time(a.metrics.combat_time),
                      score, keep)

    def show_run(self, title: str, sub: str, cells: list, duration: float, combat: str, score: str | None,
                 keep: bool = False):
        """the run's fights (debrief.FightCell) in the picker, its time in combat and score for the whole run; keep:
        the scope stays (and its view comes back), else the whole run"""
        self.page.title, self.page.sub = title, sub
        self.cells, self.duration, self.combat, self.score = cells, duration, combat, score
        self.pick.blockSignals(True)
        self.pick.clear()
        self.pick.addItems(["Whole run"] + [option_text(c) for c in cells])
        self.pick.blockSignals(False)
        scope = self.scope if keep else None
        if isinstance(scope, int) and scope >= len(cells):
            scope = None
        if isinstance(scope, int):
            self.timeline.set_view(*fight_window(cells[scope].start, cells[scope].end))
        elif scope is None:
            self.timeline.show_all()
        else:
            self.timeline.set_view(*scope)
        self._show(scope)
        self.page.update()

    def follow(self, start: float, end: float):
        """the view was set from another page: speak for the fight it shows, the whole run, or a custom view"""
        self._show(scope_for([(c.start, c.end) for c in self.cells], self.duration, (start, end)))

    # ------------------------------------------------------------------ the scope
    def _show(self, scope):
        self.scope = scope
        self.pick.blockSignals(True)
        self.pick.setCurrentIndex(scope + 1 if isinstance(scope, int) else 0 if scope is None else -1)
        self.pick.blockSignals(False)
        starts = [c.start for c in self.cells]
        self.prev.setEnabled(step(starts, scope, -1) is not None)
        self.next.setEnabled(step(starts, scope, 1) is not None)
        D = self.timeline.D
        for part in (self.figures, self.plate, self.list):
            part.setVisible(D is not None)
        if D is None:
            self.moments = []
            self.hero.set("–", None, None, None, "")
            return
        if isinstance(scope, int):
            c = self.cells[scope]
            window, label = (c.start, c.end), "In this fight"
            figures = [(f"{c.end - c.start:.0f} s", "fight length"),
                       ("–" if c.score is None else f"{c.score} {c.grade}", "fight score")]
        elif scope is None:
            window, label = (0.0, self.duration), "In this run"
            figures = [(self.combat, "in combat"), (self.score or "–", "run score")]
        else:
            window, label = scope, "In this view"
            figures = [(f"{scope[1] - scope[0]:.0f} s", "in view")]
        v = idle_view(D.idle, window)
        self.moments, self.shown = v.moments, 0
        self.hero.set(v.big, "s idle", None, None, v.verdict)
        self.figures.set([(num, cap, "") for num, cap in figures + [(str(len(v.moments)), v.gaps)]])
        self.plate.label = label
        self.plate.set(*v.plate, "Next idle moment" if v.moments else None, [])
        rows = v.rows[:LIST_ROWS]
        self.list.title = "Idle moments, longest first" + (f" ({len(rows)} of {len(v.rows)})"
                                                           if len(rows) < len(v.rows) else "")
        self.list.set([BarRow(at, length, share, "m-act") for at, length, share in rows], None)
        self.list.setVisible(bool(rows))

    def _picked(self, i: int):
        if i == 0:
            self._whole()
        elif i > 0:
            self._fight(i - 1)

    def _fight(self, i: int):
        c = self.cells[i]
        self.timeline.set_view(*fight_window(c.start, c.end))
        self._show(i)

    def _whole(self):
        self.timeline.show_all()
        self._show(None)

    def _step(self, d: int):
        i = step([c.start for c in self.cells], self.scope, d)
        if i is not None:
            self._fight(i)

    def _next_moment(self):
        """the plate's button: the next idle moment, longest first, 3 s either side, in this tab"""
        if self.moments:
            s, e = self.moments[self.shown % len(self.moments)]
            self.shown += 1
            self.timeline.set_view(s - 3, e + 3)

    def resizeEvent(self, ev):
        narrow = self.window().width() < NARROW      # the mock-up's smaller hero
        if narrow != self.narrow:
            self.narrow = narrow
            for part in (self.hero, self.figures, self.plate):
                part.narrow = narrow
                part.changed()
        super().resizeEvent(ev)
