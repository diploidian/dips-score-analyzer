"""The radar chart: a player's six values as a filled shape in their class color, the group average as a
dashed outline behind it. Hover for the numbers."""
from __future__ import annotations

import math

from PyQt6.QtCore import QEvent, QPointF, QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import QToolTip, QWidget

from ..scoring.radar import AXES, Radar
from . import theme

SHORT = {"Damage": "DMG", "Healing": "HEAL", "Tanking": "TANK", "Utility": "UTIL", "Kills": "KB", "Survival": "SURV"}


class RadarChart(QWidget):
    def __init__(self, size: int = 220, compact: bool = False):
        super().__init__()
        self.compact = compact
        self.radar: Radar | None = None
        self.avg: list[float] | None = None
        self.color = QColor(theme.ACCENT)
        self.name = ""
        self.setFixedSize(QSize(size, size))
        self.setMouseTracking(True)

    def set_data(self, radar: Radar | None, color: QColor, name: str = "", avg: list[float] | None = None):
        self.radar, self.color, self.name, self.avg = radar, QColor(color), name, avg
        self.update()

    def tooltip_html(self) -> str:
        if not self.radar:
            return ""
        rows = []
        for i, axis in enumerate(AXES):
            avg = f"<td style='color:#9696a0'>&nbsp;group avg {self.avg[i]:.0f}</td>" if self.avg else ""
            rows.append(f"<tr><td>{axis}</td><td align=right><b>{self.radar.values[i]:.0f}</b></td>{avg}"
                        f"<td>&nbsp;{self.radar.details[i]}</td></tr>")
        return (f"<b style='color:{self.color.name()}'>{self.name}</b> - share of the group's best on each axis "
                f"(100 = the most in the group; Survival: 100 with no deaths)"
                f"<table cellspacing=2>{''.join(rows)}</table>")

    def event(self, ev):
        if ev.type() == QEvent.Type.ToolTip:
            if self.radar:
                QToolTip.showText(ev.globalPos(), self.tooltip_html(), self)
            return True
        return super().event(ev)

    def _point(self, c: QPointF, r: float, i: int, v: float) -> QPointF:
        ang = -math.pi / 2 + 2 * math.pi * i / len(AXES)
        return QPointF(c.x() + math.cos(ang) * r * v / 100, c.y() + math.sin(ang) * r * v / 100)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()
        pad = 14 if self.compact else 34
        c = QPointF(w / 2, h / 2 + (2 if self.compact else 4))
        r = min(w, h) / 2 - pad
        n = len(AXES)
        # the web: rings at 25/50/75/100 and a spoke per axis
        grid = QColor(theme.DIM)
        grid.setAlpha(55)
        p.setPen(QPen(grid, 1))
        for ring in (25, 50, 75, 100):
            p.drawPolygon(QPolygonF([self._point(c, r, i, ring) for i in range(n)]))
        for i in range(n):
            p.drawLine(c, self._point(c, r, i, 100))
        # labels
        p.setFont(QFont(theme.FONT, 7 if self.compact else 8))
        p.setPen(theme.DIM)
        for i, axis in enumerate(AXES):
            pt = self._point(c, r + (8 if self.compact else 16), i, 100)
            label = SHORT[axis] if self.compact else axis
            box = QRectF(pt.x() - 30, pt.y() - 8, 60, 16)
            p.drawText(box, Qt.AlignmentFlag.AlignCenter, label)
        if not self.radar:
            return
        # the group average, then the player
        if self.avg:
            pen = QPen(QColor(theme.TEXT), 1, Qt.PenStyle.DashLine)
            pen.setColor(QColor(theme.TEXT.red(), theme.TEXT.green(), theme.TEXT.blue(), 120))
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPolygon(QPolygonF([self._point(c, r, i, max(2, v)) for i, v in enumerate(self.avg)]))
        shape = QPolygonF([self._point(c, r, i, max(2, v)) for i, v in enumerate(self.radar.values)])
        fill = QColor(self.color)
        fill.setAlpha(80)
        p.setBrush(fill)
        p.setPen(QPen(self.color, 1.6))
        p.drawPolygon(shape)
        p.setBrush(self.color)
        for pt in shape:
            p.drawEllipse(pt, 2.2, 2.2)
