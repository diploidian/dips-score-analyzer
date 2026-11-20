"""The Habits page: what you keep doing right or wrong across many fights, and the pace of this session."""
from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QFont, QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from . import theme
from .overlay import _esc
from .pages import dim_label

EDGE = {"keep": "#50dc78", "fix": "#f0a040", "build": "#5aa0f0"}


TREND_MIN = 5            # points needed to draw the trend chart


class StatBox(QFrame):
    """moved here from the old Fights page, its last user until this page is redesigned"""
    def __init__(self, value: str, label: str):
        super().__init__()
        self.setStyleSheet(f"StatBox {{ background: {theme.panel()}; border: 1px solid {theme.EDGE.name()}; "
                           f"border-radius: 6px; }} QLabel {{ background: transparent; border: 0; }}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 8, 14, 8)
        v = QLabel(value)
        v.setStyleSheet(f"font-size: 22pt; font-weight: 700; color: {theme.TITLE.name()};")
        lay.addWidget(v)
        lay.addWidget(dim_label(label))
        self.setMinimumWidth(130)


def _fmt(v, spec: str = ".0f", unit: str = "") -> str:
    return "-" if v is None else f"{v:{spec}}{unit}"


class TrendChart(QWidget):
    """efficiency per fight, oldest left, with a mark where your level or gear level changed (drawn like
    pages.ScoreChart)"""

    def __init__(self, points: list[dict]):
        super().__init__()
        self.points = points
        self.setFixedHeight(140)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = QRectF(40, 16, self.width() - 50, self.height() - 26)
        p.setFont(QFont(theme.FONT, 8))
        for v in (0, 50, 100):
            y = r.bottom() - v / 100 * r.height()
            p.setPen(theme.GRID)
            p.drawLine(int(r.left()), int(y), int(r.right()), int(y))
            p.setPen(theme.DIM)
            p.drawText(QRectF(0, y - 8, 34, 16), Qt.AlignmentFlag.AlignRight, f"{v}%")
        n = len(self.points)
        x = lambda i: r.left() + (i + 0.5) * r.width() / n  # noqa: E731
        for i in range(1, n):
            a, b = self.points[i - 1], self.points[i]
            if a["gear"] is not None and b["gear"] is not None and a["gear"] != b["gear"]:
                p.setPen(QPen(theme.MOVE, 1, Qt.PenStyle.DashLine))
                p.drawLine(QPointF(x(i - 0.5), r.top()), QPointF(x(i - 0.5), r.bottom()))
            if a["level"] is not None and b["level"] is not None and a["level"] != b["level"]:
                p.setPen(QPen(theme.DIM, 1))
                p.drawLine(QPointF(x(i - 0.5), r.top()), QPointF(x(i - 0.5), r.bottom()))
                p.drawText(QRectF(x(i - 0.5) - 20, 0, 40, 14), Qt.AlignmentFlag.AlignCenter, str(b["level"]))
        p.setPen(QPen(theme.HP, 2))                # not ACCENT: gold in the WoW theme, like the gear marks
        pts = [QPointF(x(i), r.bottom() - min(1.0, pt["efficiency"]) * r.height())
               for i, pt in enumerate(self.points) if pt["efficiency"] is not None]
        p.drawPolyline(QPolygonF(pts))


class HabitsPage(QWidget):
    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(self.scroll)
        self.show_habits({"cards": [], "session": None, "fights": 0})

    def show_habits(self, h: dict):
        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(12, 10, 16, 16)
        self.scroll.setWidget(body)
        if not h.get("fights"):
            lay.addWidget(dim_label("Fights appear here once you have some."))
            lay.addStretch(1)
            return
        c = h.get("char")
        if c:    # "Mapomimi, level 33 Undead Priest, Shadow, gear 31"
            kind = " ".join(x.title() for x in (c.get("race"), c.get("class")) if x)
            who = ", ".join([h["name"], " ".join(x for x in (f"level {c['level']}" if c.get("level") else "", kind) if x)]
                            + [x for x in (c.get("spec"), f"gear {c['gear']}" if c.get("gear") else "") if x])
        else:
            who = h["name"] + (f", level {h['level']}" if h.get("level") else "")
        head = QLabel(f"<span style='font-family:\"{theme.TITLE_FONT}\"; font-size:17pt; font-weight:700; "
                      f"color:{theme.TITLE.name()}'>{_esc(who)}</span> "
                      f"<span style='color:{theme.DIM.name()}'>last {h['fights']} fights</span>")
        lay.addWidget(head)
        s = h.get("session")
        if s:
            row = QHBoxLayout()
            stats = [(str(s["fights"]), "Fights"), (str(s["kills"]), "Kills"),
                     (_fmt(s["kills_per_hour"]), "Kills / hour"), (_fmt(s["avg_gap"], ".0f", " s"), "Avg gap"),
                     (_fmt(s["avg_rest"], ".0f", " s"), "Avg rest"),
                     (_fmt(s["avg_start_hp"] and s["avg_start_hp"] * 100, ".0f", "%"), "Start health"),
                     (_fmt(s["avg_start_mana"] and s["avg_start_mana"] * 100, ".0f", "%"), "Start mana")]
            for v, label in stats:
                row.addWidget(StatBox(v, label))
            row.addStretch(1)
            lay.addLayout(row)
        trend = h.get("trend") or []
        if len(trend) >= TREND_MIN:
            lay.addWidget(TrendChart(trend))
            lay.addWidget(dim_label("Efficiency in each fight, oldest left. Gray lines: you went up a level (the new "
                                    "level on top). Yellow dashes: your gear level changed."))
        for c in h["cards"]:
            card = QFrame()
            card.setStyleSheet(f"QFrame {{ background: {theme.panel()}; border: 1px solid {theme.EDGE.name()}; "
                               f"border-left: 4px solid {EDGE[c['kind']]}; border-radius: 6px; }} "
                               f"QLabel {{ background: transparent; border: 0; }}")
            cl = QVBoxLayout(card)
            title = QLabel(f"<b>{_esc(c['title'])}</b>")
            title.setWordWrap(True)
            cl.addWidget(title)
            detail = dim_label(c["detail"])
            detail.setWordWrap(True)
            detail.setTextFormat(Qt.TextFormat.PlainText)
            cl.addWidget(detail)
            lay.addWidget(card)
        lay.addStretch(1)
