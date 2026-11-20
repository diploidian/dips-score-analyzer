"""A player's map: their six values (scoring.radar.AXES) as a shape over rings at 25, 50, 75 and 100, the group's
average dashed over it. Other players' shapes are in m-cast; only yours is in the highlighter.

Sizes follow docs/design/mockups/group.html: a 208 x 184 drawing, its rings 60px out from (104, 92).
"""
import math

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPen, QPolygonF

from ..scoring.radar import AXES
from .kit import adv, font, text_at
from .theme import tok

W, H = 208, 184
CX, CY, R = 104, 92, 60
SHORT = {"Damage": "DMG", "Healing": "HEAL", "Tanking": "TANK", "Utility": "UTIL", "Kills": "KB", "Survival": "SURV"}
# each axis label's baseline point, and which way it runs from it: 0 centred, 1 to the right, -1 to the left
LABELS = [(104, 24, 0), (162, 62.5, 1), (162, 129.5, 1), (104, 168, 0), (46, 129.5, -1), (46, 62.5, -1)]
HELP = "Map: each axis is a share of the group's best (100 = the most in the group; Survival: 100 with no deaths)"


def _point(x: float, y: float, i: int, v: float) -> QPointF:
    a = -math.pi / 2 + 2 * math.pi * i / len(AXES)
    return QPointF(x + CX + math.cos(a) * R * v / 100, y + CY + math.sin(a) * R * v / 100)


def _shape(x, y, values) -> QPolygonF:
    return QPolygonF([_point(x, y, i, v) for i, v in enumerate(values)])


def _ink(key: str, alpha: float) -> QColor:
    c = tok(key)
    c.setAlphaF(alpha)
    return c


def _labels(x, y):
    """each axis label's text and the rect it's drawn in"""
    f = font(11, 600, num=True, spacing=0.08)
    for axis, (lx, base, way) in zip(AXES, LABELS):
        s = SHORT[axis]
        tw = adv(f, s)
        left = lx - tw / 2 if way == 0 else lx if way > 0 else lx - tw
        yield s, QRectF(x + left, y + base - 11, tw, 14)


def draw_map(p: QPainter, x: float, y: float, values: list[float], avg: list[float] | None, you: bool):
    """the map with its top left at (x, y)"""
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(Qt.BrushStyle.NoBrush)
    for ring in (25, 50, 75, 100):
        p.setPen(QPen(_ink("mu", 0.45) if ring == 100 else tok("ln"), 1))
        p.drawPolygon(_shape(x, y, [ring] * len(AXES)))
    p.setPen(QPen(tok("ln"), 1))
    for i in range(len(AXES)):
        p.drawLine(QPointF(x + CX, y + CY), _point(x, y, i, 100))
    ink = "hl" if you else "m-cast"
    p.setBrush(_ink(ink, 0.18))
    p.setPen(QPen(tok(ink), 2.4 if you else 1.8, join=Qt.PenJoinStyle.RoundJoin))
    p.drawPolygon(_shape(x, y, values))
    if avg:
        pen = QPen(tok("mu"), 1.4, join=Qt.PenJoinStyle.RoundJoin)
        pen.setDashPattern([4 / 1.4, 3 / 1.4])      # in pen widths: 4px on, 3px off
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(pen)
        p.drawPolygon(_shape(x, y, avg))
    f = font(11, 600, num=True, spacing=0.08)
    for s, r in _labels(x, y):
        text_at(p, f, tok("mu"), r.x(), r.y() + 11, s)
    p.restore()


def map_tips(x: float, y: float, values: list[float], details: list[str],
             avg: list[float] | None) -> list[tuple[QRectF, str]]:
    """hover help: each axis label's value and what's behind it, then the whole map's"""
    lines = [f"{axis} {v:.0f}: {d}" + (f" (group average {avg[i]:.0f})" if avg else "")
             for i, (axis, v, d) in enumerate(zip(AXES, values, details))]
    return ([(r, line) for (_, r), line in zip(_labels(x, y), lines)]
            + [(QRectF(x, y, W, H), "\n".join([HELP, *lines] + (["Dashed: the group average"] if avg else [])))])
