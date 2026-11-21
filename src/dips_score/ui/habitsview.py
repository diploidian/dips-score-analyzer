"""The Habits page: what you keep doing right or wrong across many fights, painted from a HabitsView (see
dips_score/habits_view.py): your efficiency over the last 20 fights against the ones before, the habit to fix on the
plate, this sitting's key figures, the efficiency of every fight, and the habits grouped Fix · Build · Keep.

Sizes follow docs/design/mockups/habits.html (CSS px). The shared parts come from kit.py.
"""
from __future__ import annotations

import re

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QScrollArea, QVBoxLayout

from ..habits_view import NO_FIGHTS, RECENT, HabitsView, build_habits
from .debrief import NARROW
from .kit import (HEAD_H, Hero, KeyFigures, Part, Plate, Sheet, Side, adv, baseline, draw_hand_circle,
                  draw_hand_note, draw_label_tab, draw_tag, elide, font, halo_text, hand_font, line, rule, text_at,
                  wrapped)
from .pages import dim_label
from .theme import tok

HERO_W = (280, 236)      # the hero's column (narrow)
SIDE_W = 470             # the Habits column, its 28px gutter included
SQUARE = {"Fix": "gD", "Build": "m-cast", "Keep": "m-dmg"}      # each group's 8px square
PLATE_TAG = "habit to fix"


class HabitFigures(KeyFigures):
    """the key figures as the mock-up sets them: in columns (the last wider), the number over its muted caption, its
    units smaller ("46s", "96% / 95%"), between the hero's rule and its own"""

    def draw(self, p, w):
        if not self.items:
            return 0
        k = len(self.items)
        big, small = (26, 17) if self.narrow else (30, 19)
        gap = 14 if self.narrow else 20
        unit = (w - gap * (k - 1)) / (k + 0.4)
        bf, uf, cf = font(big, 700, num=True), font(small, 600, num=True), font(12)
        h = 1 + 12 + big + 4 + 12 * 1.4 + 11
        if p:
            rule(p, 0, 0, w, tok("ln"))
            x, base = 0.0, baseline(bf, 1 + 12, big)
            for i, (num, cap) in enumerate(self.items):
                cw = unit * (1.4 if i == k - 1 else 1)
                nx = x
                for j, run in enumerate(re.split(r"([A-Za-z%]+)", num)):     # odd runs are the units
                    nx += text_at(p, uf if j % 2 else bf, tok("tx"), nx, base, run)
                line(p, cf, tok("mu"), x, 1 + 12 + big + 4, 12 * 1.4, elide(cf, cap, cw))
                x += cw + gap
            rule(p, 0, h, w, tok("ln"))
        return h + 1


class TrendChart(Part):
    """Efficiency, fight by fight: each fight's efficiency, oldest left, on 0 / 50 / 100% lines; the two periods'
    averages dashed (before in tx2, the last 20 in gD when lower, m-dmg when not); level (solid, the new level on top)
    and gear-level changes (dashed) in mu; and, when efficiency fell over 3 points, the drop's start circled"""

    def __init__(self):
        super().__init__()
        self.view = HabitsView()

    def set_view(self, v: HabitsView):
        self.view = v
        if v.trend:
            self.setAccessibleName(f"Efficiency per fight over the last {len(v.trend)} fights: {v.recent:.1f}% "
                                   f"over the last {min(RECENT, len(v.trend))}"
                                   + (f", {v.before:.1f}% before" if v.before is not None else ""))
        self.changed()

    def draw(self, p, w):
        draw_label_tab(p, 0, 16, "Efficiency, fight by fight")
        top = 16 + 25 + 12
        if p and self.view.trend:
            self._chart(p, w, top)
        v = self.view       # under the chart, what its upright lines mean (only those it has)
        note = " · ".join(s for marks, s in ((v.levels, "solid line: you went up a level (the new level on top)"),
                                             (v.gear_changes, "dashed line: your gear level changed")) if marks)
        return top + 280 + (wrapped(p, font(12), tok("mu"), 0, top + 284, w, 12 * 1.4, note) + 4 if note else 0)

    def _chart(self, p: QPainter, w: float, top: float):
        """drawn in the mock-up's 280px-tall frame from top, its plot from x 44 to 16 short of the right edge"""
        v, n = self.view, len(self.view.trend)
        x0, x1 = 44.0, w - 16.0
        mu, small = tok("mu"), font(11)

        def X(i: float) -> float:
            return x0 + i * (x1 - x0) / max(1, n - 1)

        def Y(e: float) -> float:
            return top + 250 - min(100.0, max(0.0, e)) / 100 * 216

        rule(p, x0, top + 34, x1 - x0, tok("ln"))
        rule(p, x0, top + 250, x1 - x0, tok("tx"))
        pen = QPen(tok("ln"), 1)
        pen.setDashPattern([3, 3])
        p.setPen(pen)
        p.drawLine(QPointF(x0, top + 142), QPointF(x1, top + 142))
        for s, y in (("100%", 34), ("50%", 142), ("0", 250)):
            text_at(p, small, mu, 36 - adv(small, s), top + y + 4, s)
        text_at(p, small, mu, x0, top + 270, "fight 1")
        for k in range(10, n - 2, 10):
            text_at(p, small, mu, X(k - 1) - adv(small, str(k)) / 2, top + 270, str(k))
        text_at(p, small, mu, x1 - adv(small, str(n)), top + 270, str(n))
        # where your level or gear level changed
        pen = QPen(mu, 1)
        pen.setDashPattern([3, 3])
        p.setPen(pen)
        for i in v.gear_changes:
            p.drawLine(QPointF((X(i - 1) + X(i)) / 2, top + 34), QPointF((X(i - 1) + X(i)) / 2, top + 250))
        for i, level in v.levels:
            xm = (X(i - 1) + X(i)) / 2
            p.fillRect(QRectF(round(xm), top + 34, 1, 216), mu)
            text_at(p, small, mu, xm - adv(small, str(level)) / 2, top + 30, str(level))
        # the periods: split where the last 20 start, each labelled
        lab = font(11, 700, num=True, spacing=0.145)
        r0 = n - min(RECENT, n)
        xs = X(r0) if v.split_at is None else (X(v.split_at - 1) + X(v.split_at)) / 2
        if v.split_at is not None:
            b0 = max(0, n - 2 * RECENT)
            p.fillRect(QRectF(round(xs), top + 12, 1, 238), tok("ln"))
            text_at(p, lab, mu, X(b0), top + 22, f"{v.split_at - b0} BEFORE")
        text_at(p, lab, mu, xs + 8, top + 22, f"LAST {n - r0}")
        # the line, then the averages over it
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(tok("tx"), 1.8, cap=Qt.PenCapStyle.RoundCap, join=Qt.PenJoinStyle.RoundJoin))
        p.drawPolyline(QPolygonF([QPointF(X(i), Y(e)) for i, e in enumerate(v.trend)]))
        af = font(17, 700, num=True)

        def average(a: float, b: float, e: float, ink: str):
            pen = QPen(tok(ink), 2)
            pen.setDashPattern([3, 2])         # in pen widths: 6px on, 4px off
            p.setPen(pen)
            p.drawLine(QPointF(a, Y(e)), QPointF(b, Y(e)))
        if v.before is not None:
            bx = X(max(0, n - 2 * RECENT))       # where the before period starts
            average(bx, xs, v.before, "tx2")
            s = f"{v.before:.1f}%"
            halo_text(p, af, tok("tx2"), (bx + xs - adv(af, s)) / 2, Y(v.before) + 20.5, s)    # over the line
        ink = "tx2" if v.before is None else "gD" if v.recent < v.before else "m-dmg"
        average(xs, x1, v.recent, ink)
        s = f"{v.recent:.1f}%"
        halo_text(p, af, tok(ink), x1 - adv(af, s), Y(v.recent) - 7.8, s)
        # the page's one highlighter mark: where the drop starts
        if v.before is not None and v.recent < v.before - 3:
            cy = (Y(v.trend[v.split_at - 1]) + Y(v.trend[v.split_at])) / 2
            draw_hand_circle(p, QRectF(xs - 17, cy - 26, 34, 52), tok("hl"), -6)
            note, tw = "drop starts here", adv(hand_font(25), "drop starts here")
            if cy + 26 + 40 <= top + 204:      # under the ring, as the mock-up; over it when the ring sits low
                anchor, to = QPointF(xs + 21, top + 204), QPointF(xs + 4, cy + 30)
            else:
                anchor, to = QPointF(xs + 21, cy - 60), QPointF(xs + 4, cy - 30)
            if anchor.x() + tw > w:
                anchor.setX(xs - 21 - tw)
            draw_hand_note(p, note, anchor, to, 25)


class HabitList(Part):
    """Habits: a group each (Fix, Build, Keep) under its 8px square and count, its habits in a ruled list, title over
    detail; the plate's one tagged "habit to fix\""""

    def __init__(self):
        super().__init__()
        self.groups: list[tuple[str, list[tuple[str, str, bool]]]] = []

    def set(self, groups):
        self.groups = groups
        self.changed()

    def draw(self, p, w):
        draw_label_tab(p, 0, 0, "Habits")
        y = 25 + 2
        gf, tf, df = font(12, 700, num=True, spacing=0.14), font(15, 500), font(13)
        tag_w = draw_tag(None, 0, 0, PLATE_TAG) + 8
        for name, rows in self.groups:
            y += 14
            if p:
                p.fillRect(QRectF(0, y + 2, 8, 8), tok(SQUARE[name]))
                line(p, gf, tok("tx"), 16, y, 12, f"{name} · {len(rows)}".upper())
            y += 12 + 7
            for title, detail, plate in rows:
                if p:
                    rule(p, 0, y, w, tok("ln"))
                y += 1 + 6
                if p:
                    tw = line(p, tf, tok("tx"), 0, y, 19.5, elide(tf, title, w - (tag_w if plate else 0)))
                    if plate:
                        draw_tag(p, tw + 8, y + 19.5 / 2, PLATE_TAG)
                y += 19.5
                y += wrapped(p, df, tok("tx2"), 0, y, w, 13 * 1.35, detail) + 7
            if p:
                rule(p, 0, y, w, tok("ln"))
            y += 1
        return y + 12


class HabitsPage(QScrollArea):
    """the Habits page, scrolling when the window is small"""
    open_fights = pyqtSignal()      # the plate's "Open Fights" (R8): the rail's Fights mode, its list unfiltered

    def __init__(self):
        super().__init__()
        self.narrow = None
        self.page = Sheet()
        self.hero, self.plate = Hero(), Plate("Habit to fix")
        self.plate.price_words, self.plate.price_px = True, 36
        self.plate.clicked.connect(self.open_fights)
        self.figures, self.chart, self.habits = HabitFigures(), TrendChart(), HabitList()
        self.empty = dim_label(NO_FIGHTS)
        self.empty.setContentsMargins(0, 14, 0, 0)

        self.hero_row = QHBoxLayout()
        self.hero_row.setContentsMargins(0, 14, 0, 18)
        self.hero_row.addWidget(self.hero, 0, Qt.AlignmentFlag.AlignTop)
        self.hero_row.addWidget(self.plate, 1, Qt.AlignmentFlag.AlignTop)
        self.hero_row.addStretch(0)      # the plate hidden: the hero keeps its column on the left
        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 28, 0)
        left.setSpacing(0)
        left.addWidget(self.empty)
        left.addLayout(self.hero_row)
        left.addWidget(self.figures)
        left.addWidget(self.chart)
        left.addStretch(1)
        self.side = Side()
        self.side.setFixedWidth(SIDE_W)
        sl = QVBoxLayout(self.side)
        sl.setContentsMargins(28, 16, 0, 0)
        sl.addWidget(self.habits)
        sl.addStretch(1)
        cols = QHBoxLayout()
        cols.setSpacing(0)
        cols.addLayout(left, 1)
        cols.addWidget(self.side)
        lay = QVBoxLayout(self.page)
        lay.setContentsMargins(16, 4, 16, 16)
        lay.setSpacing(0)
        lay.addSpacing(HEAD_H)
        lay.addLayout(cols, 1)
        self.setWidget(self.page)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._fit()
        self.show_habits({"fights": 0})

    def show_habits(self, h: dict):
        """h: live.habits.habits()'s result"""
        v = build_habits(h)
        self.page.title, self.page.sub = v.title, v.meta
        some = bool(h.get("fights"))
        self.empty.setVisible(not some)
        for wd in (self.hero, self.plate, self.figures, self.chart, self.side):
            wd.setVisible(some)
        if some:
            self.hero.set("–" if v.recent is None else f"{v.recent:.0f}", None if v.recent is None else "%",
                          v.caption, v.chip, v.verdict)
            title, price, caption = v.fix or ("", None, None)
            self.plate.set(title, price, caption, "Open Fights", [])
            self.plate.setVisible(v.fix is not None)
            self.figures.set(v.figures)
            self.chart.set_view(v)
            self.chart.setVisible(bool(v.trend))
            self.habits.set(v.groups)
            self.side.setVisible(bool(v.groups))
        self.page.update()

    def resizeEvent(self, ev):
        self._fit()
        super().resizeEvent(ev)

    def _fit(self):
        """the mock-up's narrow hero and figures below a 1420px window"""
        narrow = self.window().width() < NARROW
        if narrow == self.narrow:
            return
        self.narrow, k = narrow, int(narrow)
        self.hero.setFixedWidth(HERO_W[k])
        self.hero_row.setSpacing(22 if narrow else 28)
        for part in (self.hero, self.plate, self.figures):
            part.narrow = narrow
            part.changed()
