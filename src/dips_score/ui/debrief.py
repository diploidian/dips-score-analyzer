"""The Debrief tab's page, painted from a DebriefView (see dips_score/debrief.py): the score and verdict, the one
fix on the plate, the main measures and where the points went; on the right, the run's fights as a grid with the ones to
review circled in highlighter.

Sizes follow docs/design/mockups/debrief.html (CSS px). Each part paints itself, and the same pass measures its
height for a width, so text wraps the way it is drawn.
"""
import math

from PyQt6.QtCore import QEasingCurve, QEvent, QPointF, QRectF, QSize, Qt, QVariantAnimation, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPen, QPolygonF, QTextLayout
from PyQt6.QtWidgets import (QFrame, QHBoxLayout, QPushButton, QScrollArea, QSizePolicy, QSpacerItem, QToolTip,
                             QVBoxLayout, QWidget)

from ..debrief import (DebriefView, FightCell, bar_fraction, circle_fraction, display_name, note_alpha, route_alpha,
                       ticker)
from . import theme
from .theme import tok

MINUS = "−"
NARROW = 1420        # the mock-up's breakpoint (window width): a smaller hero below it
HEAD_H = 71          # title, meta line and the gold rule under them
FIGHTS_W = 460       # the right-hand column
EDGE = 16            # the page's right margin, lent to the fights column for edge circles and the grid's scroll bar
LEFT_MIN = 480       # the left column never gets narrower (the page scrolls sideways instead)
ENTRANCE_MS = 900     # the one entrance: ticker, bars, circles, note; p runs 0..1, 1 is the settled page
PREVIEW = ("Rotation", "Pacing")   # measures still being worked out


# ---------------------------------------------------------------------------- painting helpers
def font(px: int, weight: int = 400, num: bool = False, spacing: float = 0) -> QFont:
    """Barlow (num: Barlow Condensed) at px pixels; spacing in em, like the mock-up's letter-spacing"""
    f = QFont(theme.NUM_FONT if num else theme.FONT)
    f.setPixelSize(px)
    f.setWeight(QFont.Weight(weight))
    if spacing:
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing * px)
    return f


def adv(f: QFont, s: str) -> float:
    return QFontMetricsF(f).horizontalAdvance(s)


def baseline(f: QFont, top: float, lh: float) -> float:
    """where a CSS line box of height lh starting at top puts the baseline"""
    fm = QFontMetricsF(f)
    return top + (lh + fm.ascent() - fm.descent()) / 2


def text_at(p: QPainter | None, f: QFont, color: QColor, x: float, base: float, s: str) -> float:
    """s on the baseline; returns its width"""
    if p:
        p.setFont(f)
        p.setPen(color)
        p.drawText(QPointF(x, base), s)
    return adv(f, s)


def line(p, f, color, x, top, lh, s) -> float:
    return text_at(p, f, color, x, baseline(f, top, lh), s)


def elide(f: QFont, s: str, width: float) -> str:
    return QFontMetricsF(f).elidedText(s, Qt.TextElideMode.ElideRight, width)


def wrapped(p, f, color, x, top, width, lh, s) -> float:
    """s word-wrapped to width, lines lh apart; returns its height"""
    tl = QTextLayout(s, f)
    tl.beginLayout()
    fm, n = QFontMetricsF(f), 0
    while (ln := tl.createLine()).isValid():
        ln.setLineWidth(width)
        ln.setPosition(QPointF(0, n * lh + (lh - fm.ascent() - fm.descent()) / 2))
        n += 1
    tl.endLayout()
    if p:
        p.setPen(color)
        tl.draw(p, QPointF(x, top))
    return n * lh


def flow(p, items, x, top, width, gap, row_gap) -> float:
    """(text, font, color) items on a shared baseline, wrapping like flex-wrap; returns the height"""
    rows, cur, used = [], [], 0.0
    for s, f, c in items:
        w = adv(f, s)
        if cur and used + gap + w > width:
            rows.append(cur)
            cur, used = [], 0.0
        used += (gap if cur else 0) + w
        cur.append((s, f, c, w))
    if cur:
        rows.append(cur)
    y = top
    for k, row in enumerate(rows):
        y += row_gap if k else 0
        asc = max(QFontMetricsF(f).ascent() for _, f, _, _ in row)
        desc = max(QFontMetricsF(f).descent() for _, f, _, _ in row)
        bx = x
        for s, f, c, w in row:
            text_at(p, f, c, bx, y + asc, s)
            bx += w + gap
        y += asc + desc
    return y - top


def rule(p, x, y, w, color, h=1):
    p.fillRect(QRectF(x, round(y), w, h), color)


def box(p, r: QRectF, edge: QColor, fill: QColor | None = None, width: int = 1):
    """a square frame, drawn as filled edges so it stays crisp"""
    r = QRectF(round(r.x()), round(r.y()), round(r.width()), round(r.height()))
    if fill is not None:
        p.fillRect(r, fill)
    for e in (QRectF(r.x(), r.y(), r.width(), width), QRectF(r.x(), r.bottom() - width, r.width(), width),
              QRectF(r.x(), r.y(), width, r.height()), QRectF(r.right() - width, r.y(), width, r.height())):
        p.fillRect(e, edge)


def label_tab(p, x, y, s) -> QRectF:
    """the boxed module label: Barlow Condensed 700 11px, .16em, capitals, a 1px ln frame on panel"""
    f, s = font(11, 700, num=True, spacing=0.16), s.upper()
    r = QRectF(x, y, adv(f, s) + 22, 25)
    if p:
        box(p, r, tok("ln"), tok("panel"))
        line(p, f, tok("tx"), x + 11, y + 7, 11, s)
    return r


def tag(p, x, mid, s):
    """the small gold-framed tag ("preview"), centred on mid"""
    f, s = font(11, 600, spacing=0.1), s.upper()
    h = 11 * 1.2 + 6
    r = QRectF(x, mid - h / 2, adv(f, s) + 14, h)
    box(p, r, tok("gold"))
    line(p, f, tok("gold"), x + 7, r.y() + 3, 11 * 1.2, s)


# ---------------------------------------------------------------------------- the parts
class _Part(QWidget):
    """a part of the debrief: draw(None, w) measures its height for a width, draw(p, w) paints it"""

    def __init__(self):
        super().__init__()
        self.view = DebriefView()
        self.narrow = False
        self.p = 1.0           # the entrance's progress; 1 draws the settled page
        sp = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sp.setHeightForWidth(True)
        self.setSizePolicy(sp)

    def set_view(self, view: DebriefView, narrow: bool):
        self.view, self.narrow = view, narrow
        self.updateGeometry()
        self.update()

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, w: int) -> int:
        return math.ceil(self.draw(None, w))

    def sizeHint(self) -> QSize:
        return QSize(300, self.heightForWidth(300))

    def paintEvent(self, _ev):
        self.draw(QPainter(self), self.width())

    def draw(self, p: QPainter | None, w: float) -> float:
        raise NotImplementedError


class Hero(_Part):
    """the score, its boxed grade and the verdict: the fixed-width column left of the plate"""

    def draw(self, p, w):
        v = self.view
        px = 126 if self.narrow else 150
        f = font(px, 700, num=True, spacing=-0.02)
        top, lh = 8, px * 0.8
        # "-": nothing judgeable, so no grade to box; the "–" placeholder is muted so it reads as a dash, not a block
        x = adv(f, v.total)      # the final width, so the grade's box doesn't move while the number ticks
        if p:
            text_at(p, f, tok("tx") if v.grade != "-" else tok("mu"), 0, baseline(f, top, lh), ticker(v.total, self.p))
        if v.grade != "-":
            gpx, pv, ph = (46, 4, 10) if self.narrow else (56, 5, 12)
            g = font(gpx, 700, num=True)
            r = QRectF(x + 10, top + 6, adv(g, v.grade) + 2 * ph + 4, gpx + 2 * pv + 4)
            if p:
                p.setOpacity(min(1.0, self.p / 0.78))      # the grade appears as the number lands
                box(p, r, tok("gold"), width=2)
            text_at(p, g, theme.grade_color(v.grade), r.x() + 2 + ph, baseline(g, r.y() + 2 + pv, gpx), v.grade)
            if p:
                p.setOpacity(1)
        y = top + lh + 16
        return y + wrapped(p, font(15), tok("tx2"), 0, y, w, 21, v.verdict or v.note)


class FixPlate(_Part):
    """the one solid plate: the fix worth the most points, its price, Show me, and the next two fixes"""

    def __init__(self):
        super().__init__()
        self.button = QPushButton("Show me on the timeline", self)
        self.button.setObjectName("showme")
        self.button.hide()
        self.can_show = False      # set by the page: a fix, and a fight to zoom to
        self.wrap = True           # the next fixes wrap; the page sets False when that wouldn't fit its height
        self.button_y = self.next_y = 0.0

    def set_view(self, view, narrow):
        super().set_view(view, narrow)
        self._place()

    def resizeEvent(self, ev):
        self._place()
        super().resizeEvent(ev)

    def _place(self):
        self.button.adjustSize()
        self.draw(None, self.width())       # finds button_y
        self.button.move(18, round(self.button_y))
        self.button.setVisible(self.can_show)

    def event(self, ev):
        """when the next fixes are cut to one line each, hovering them shows them whole"""
        if (ev.type() == QEvent.Type.ToolTip and not self.wrap and self.view.next_fixes
                and ev.pos().y() >= self.next_y):
            QToolTip.showText(ev.globalPos(), "\n".join(nx.title for nx in self.view.next_fixes), self)
            return True
        return super().event(ev)

    def paintEvent(self, _ev):
        p = QPainter(self)
        h = self.draw(None, self.width())
        p.fillRect(QRectF(0, 12, self.width(), h - 12), tok("plate"))
        self.draw(p, self.width())
        label_tab(p, 14, 0, "Fix this first")    # straddles the plate's top edge

    def draw(self, p, w, wrap: bool | None = None):
        v, fix, n = self.view, self.view.fix, self.narrow
        wrap = self.wrap if wrap is None else wrap
        x, cw = 18, w - 36
        y = 12 + 22
        tpx = 21 if n else 23
        y += wrapped(p, font(tpx, 600, num=True), tok("plate-tx"), x, y, cw, tpx * 1.15,
                     fix.title if fix else "Nothing to fix this run.") + 8
        if fix is None:
            return y + 14
        price = [(f"{MINUS}{fix.points:.1f} points", font(32, 700, num=True), tok("plate-ac")),
                 (display_name(fix.category), font(13), tok("plate-mu"))]
        if fix.damage:
            price.append((fix.damage, font(13), tok("plate-mu")))
        y += flow(p, price, x, y, cw, 12 if n else 18, 2)
        if self.can_show:
            self.button_y = y + 10
            y = self.button_y + self.button.sizeHint().height()
        if v.next_fixes:
            y += 10
            if p:
                rule(p, x, y, cw, tok("plate-ln"))
            y += 1 + 7
            self.next_y = y
            nf, bf, lh = font(12 if n else 13), font(14, 600, num=True), (12 if n else 13) * 1.4
            for k, nx in enumerate(v.next_fixes):
                y += 4 if k else 0
                cost = f"{MINUS}{nx.points:.1f} {display_name(nx.category)}"
                cost_w = adv(bf, cost)
                tw = max(0.0, cw - cost_w - 10)
                if p:
                    line(p, bf, tok("plate-ac"), x + cw - cost_w, y, lh, cost)
                if wrap:
                    y += wrapped(p, nf, tok("plate-tx"), x, y, tw, lh, nx.title)
                else:
                    if p:
                        line(p, nf, tok("plate-tx"), x, y, lh, elide(nf, nx.title, tw))
                    y += lh
        return y + 14


class MeasureBars(_Part):
    """Effectiveness: the main measures as bars, with the 90 target marked"""

    def draw(self, p, w):
        if p:
            rule(p, 0, 0, w, tok("ln"))
        y = 1 + 12
        label_tab(p, 0, y, "Effectiveness")
        y += 25 + 8
        bx, bw = 174, max(0, w - 298)   # columns: 160 name, 14 gap, the bar, 14 gap, 110 value
        nf, vf, rf, sf = font(14, 500), font(30, 700, num=True), font(11), font(11, 500)
        r1, r2 = 14 * 1.4, 11 * 1.4 - 2    # the name row; the reason row tucks up 2px
        for k, m in enumerate(self.view.measures):
            if k:
                if p:
                    rule(p, 0, y, w, tok("ln"))
                y += 1
            y += 5
            if p:
                nw = line(p, nf, tok("tx"), 0, y, r1, m.name)
                if m.name in PREVIEW:
                    tag(p, nw + 8, y + r1 / 2, "preview")
                by = y + (r1 - 10) / 2
                p.fillRect(QRectF(bx, by, bw, 10), tok("track"))
                p.fillRect(QRectF(bx, by, bw * max(0.0, min(100.0, m.score or 0)) / 100 * bar_fraction(self.p, k), 10),
                           tok(m.ink))
                p.fillRect(QRectF(bx + bw * 0.9, by - 4, 2, 18), tok("tx"))
                line(p, rf, tok("mu"), bx, y + r1 - 2, 11 * 1.4, elide(rf, m.reason, bw))
                score = "–" if m.score is None else f"{m.score:.0f}"
                base = baseline(vf, y + (r1 + r2 - 30) / 2, 30)
                sw = text_at(p, vf, tok("tx"), w - adv(vf, score), base, score)
                note = "on target" if m.on_target else "below 90"
                text_at(p, sf, tok("mu"), w - sw - 6 - adv(sf, note), base, note)
            y += r1 + r2 + 5
        return y + 12


class DrawerToggle(QWidget):
    """the All categories header: a drawn chevron and its label. Click it, or Tab to it and press Space or Enter"""
    toggled = pyqtSignal(bool)

    def __init__(self, parent):
        super().__init__(parent)
        self.open, self.label = False, ""
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)     # the focus ring is for the keyboard, like :focus-visible
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_label(self, s: str):
        self.label = s.upper()
        self.setAccessibleName(s)
        self.setFixedSize(math.ceil(adv(font(12, 600, num=True, spacing=0.08), self.label)) + 28, 25)
        self.update()

    def mousePressEvent(self, _ev):
        self.flip()

    def keyPressEvent(self, ev):
        if ev.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.flip()
        else:
            super().keyPressEvent(ev)

    def flip(self):
        self.open = not self.open
        self.update()
        self.toggled.emit(self.open)

    def paintEvent(self, _ev):
        p = QPainter(self)
        if self.hasFocus():
            box(p, QRectF(self.rect()), tok("hl"), width=2)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(tok("tx"), 1.6))
        c = QPointF(12, self.height() / 2)
        pts = ((-4, -2), (0, 2), (4, -2)) if self.open else ((-2, -4), (2, 0), (-2, 4))   # down, or right
        p.drawPolyline(QPolygonF([c + QPointF(dx, dy) for dx, dy in pts]))
        line(p, font(12, 600, num=True, spacing=0.08), tok("tx"), 22, 0, self.height(), self.label)


class Breakdown(_Part):
    """Where your points went: a bar per category, as long as the points it lost, then the points earned.
    Its All categories drawer (every category of the card, and the hybrid bonus) opens under Earned."""

    def __init__(self):
        super().__init__()
        self.whose = "your"
        self.open = False
        self.toggle = DrawerToggle(self)        # on the tab's line, so the shut drawer takes no height
        self.toggle.toggled.connect(self._open)

    def set_view(self, view, narrow):
        super().set_view(view, narrow)
        self.toggle.set_label(f"All categories ({len(view.categories)})")
        self.toggle.setVisible(bool(view.categories))
        self._place()

    def resizeEvent(self, ev):
        self._place()
        super().resizeEvent(ev)

    def _place(self):
        # right of the tab; alone (nothing judged), it is the section's header
        self.toggle.move(self.width() - self.toggle.width() if self.view.measures else 0, 13)

    def _open(self, open_: bool):
        self.open = open_
        self.updateGeometry()
        self.update()

    def draw(self, p, w, open_: bool | None = None):
        v = self.view
        open_ = self.open if open_ is None else open_
        if p:
            rule(p, 0, 0, w, tok("ln"))
        y = 1 + 12
        if not v.measures:       # nothing judged: only the drawer, so every category and why is still there
            y += 25
            return (self._drawer(p, w, y + 8) if open_ else y) + 12
        label_tab(p, 0, y, f"Where {self.whose} {100 - v.earned} points went")
        y += 25 + 8
        most = max((lost.points for lost in v.lost), default=0) or 1
        nf, vf = font(15), font(15, 700, num=True)
        for k, lost in enumerate(v.lost):
            if k:
                if p:
                    rule(p, 0, y, w, tok("ln"))
                y += 1
            if p:
                line(p, nf, tok("tx"), 0, y + 3, 18, display_name(lost.name))
                p.fillRect(QRectF(120, y + 3 + 4, 220 * lost.points / most * bar_fraction(self.p, k), 10), tok(lost.ink))
                s = f"{MINUS}{lost.points:.1f}"
                line(p, vf, tok("tx"), w - adv(vf, s), y + 3, 18, s)
            y += 3 + 18 + 3
        if v.bonus > 0:          # so the rows add up to Earned
            if v.lost:
                if p:
                    rule(p, 0, y, w, tok("ln"))
                y += 1
            if p:
                line(p, nf, tok("tx"), 0, y + 3, 18, "Hybrid bonus")
                s = f"+{v.bonus:.1f}"
                line(p, vf, tok("tx"), w - adv(vf, s), y + 3, 18, s)
            y += 3 + 18 + 3
        if p:
            rule(p, 0, y, w, tok("tx"), 2)
        y += 2 + 6
        if p:
            ef, sf = font(20, 700, num=True), font(14, 500, num=True, spacing=0.04)
            base = baseline(ef, y, 22)
            ew = text_at(p, ef, tok("tx"), 0, base, "Earned")
            text_at(p, sf, tok("mu"), ew + 6, base, f"· {v.earned} of 100")
            text_at(p, ef, tok("tx"), w - adv(ef, str(v.earned)), base, str(v.earned))
        y += 22 + 3
        if open_:
            y = self._drawer(p, w, y + 12)
        return y + 12

    def _drawer(self, p, w, y) -> float:
        """one ruled row per category in the card's order (name, score, weight or why it's info only), then
        the hybrid bonus"""
        v = self.view
        nf, vf, df = font(15), font(15, 700, num=True), font(13)
        rows = [(display_name(c.name), "–" if c.unavailable else f"{c.score:.0f}",
                 f"info only · {c.unavailable}" if c.unavailable else
                 f"{'info only' if c.info_only else f'weight {c.weight}'} · {c.summary}", c.info_only)
                for c in v.categories]
        if v.bonus > 0:
            rows.append(("Hybrid bonus", f"+{v.bonus:.1f}", v.bonus_note, False))
        for name, score, detail, dim in rows:
            if p:
                rule(p, 0, y, w, tok("ln"))
            y += 1 + 3
            ink = tok("mu") if dim else tok("tx")
            if p:
                line(p, nf, ink, 0, y, 18, elide(nf, name, 150))
                line(p, vf, ink, 200 - adv(vf, score), y, 18, score)
            y += max(18.0, wrapped(p, df, tok("mu"), 220, y, max(0, w - 220), 18, detail)) + 3
        return y


COLS, CELL_W, CELL_H = 8, 54, 75
NOTE_H = 34          # the band above the grid for the hand-written note
PAD = 6              # either side of the grid: room for the circles on its edge columns
GRID_VIEW = 608      # past 8 rows the grid scrolls, in a view this tall
RX, RY = 31, 26      # a circle's radii


def halo_text(p: QPainter, f: QFont, color: QColor, x: float, base: float, s: str) -> float:
    """s on the baseline with a 3px panel halo, so it reads through the highlighter; returns its width"""
    path = QPainterPath()
    path.addText(x, base, f, s)
    p.strokePath(path, QPen(tok("panel"), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                            Qt.PenJoinStyle.RoundJoin))
    p.fillPath(path, color)
    return adv(f, s)


class FightGrid(QWidget):
    """the run's fights, 8 to a row: number, time, score and grade, a square on bosses. The fights to review are
    circled in highlighter, joined by a route, with a hand-written note pointing at the first. Click a fight (or
    Tab to the grid, move with the arrows and press Space or Enter) to pick it."""
    picked = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.cells: list[FightCell] = []
        self.review: list[int] = []
        self.focus = 0                  # the cell the keyboard is on
        self.p = 1.0                    # the entrance's progress (circles, then the note)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_cells(self, cells: list[FightCell], review: list[int]) -> None:
        self.cells, self.review = cells, review
        self.focus = min(self.focus, max(0, len(cells) - 1))
        self.setFixedSize(2 * PAD + COLS * CELL_W, NOTE_H + math.ceil(len(cells) / COLS) * CELL_H)
        self.update()

    def cell_rect(self, k: int) -> QRectF:
        return QRectF(PAD + k % COLS * CELL_W, NOTE_H + k // COLS * CELL_H, CELL_W, CELL_H)

    def circle_at(self, k: int) -> QPointF:
        """the middle of cell k's score digits"""
        r, f = self.cell_rect(k), font(21, 700, num=True)
        return QPointF(r.center().x(), baseline(f, r.y() + 31, 24) - QFontMetricsF(f).capHeight() / 2)

    def cell_at(self, pos: QPointF) -> int | None:
        x, y = pos.x() - PAD, pos.y() - NOTE_H
        k = int(y // CELL_H) * COLS + int(x // CELL_W)
        return k if 0 <= x < COLS * CELL_W and y >= 0 and k < len(self.cells) else None

    def mousePressEvent(self, ev):
        k = self.cell_at(ev.position())
        if k is not None:
            self.focus = k
            self.update()
            self.picked.emit(self.cells[k].index)

    def keyPressEvent(self, ev):
        step = {Qt.Key.Key_Left: -1, Qt.Key.Key_Right: 1, Qt.Key.Key_Up: -COLS, Qt.Key.Key_Down: COLS}.get(ev.key())
        if step and 0 <= self.focus + step < len(self.cells):
            self.focus += step
            self.update()
            scroll = self.parentWidget() and self.parentWidget().parentWidget()    # the viewport's scroll area
            if isinstance(scroll, QScrollArea):
                c = self.cell_rect(self.focus).center()
                scroll.ensureVisible(round(c.x()), round(c.y()), 0, CELL_H // 2 + 2)
        elif ev.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.cells:
            self.picked.emit(self.cells[self.focus].index)
        else:
            super().keyPressEvent(ev)

    def focusInEvent(self, ev):
        self.update()
        super().focusInEvent(ev)

    def focusOutEvent(self, ev):
        self.update()
        super().focusOutEvent(ev)

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        grid = QRectF(PAD, NOTE_H, COLS * CELL_W, self.height() - NOTE_H)
        # 1. grounds and hairlines (right and bottom of each cell), in the gold frame
        p.fillRect(grid, tok("panel"))
        for k in range(len(self.cells)):
            r = self.cell_rect(k)
            p.fillRect(QRectF(r.right() - 1, r.y(), 1, CELL_H), tok("ln"))
            p.fillRect(QRectF(r.x(), r.bottom() - 1, CELL_W, 1), tok("ln"))
        box(p, grid, tok("gold"))
        # 2. the highlighter: circles, the route between them, a cross where you died; under the text
        hl = tok("hl")
        p.setBrush(Qt.BrushStyle.NoBrush)
        ks = [k for k, c in enumerate(self.cells) if c.index in self.review]
        cs = [self.circle_at(k) for k in ks]
        p.setOpacity(0.8)
        p.setPen(QPen(hl, 5, cap=Qt.PenCapStyle.RoundCap, join=Qt.PenJoinStyle.RoundJoin))
        for j, c in enumerate(cs):
            f = circle_fraction(self.p, j)
            if f <= 0:
                continue
            p.save()
            p.translate(c)
            p.rotate(-5 if j % 2 == 0 else 4)
            if f >= 1:
                p.drawEllipse(QPointF(0, 0), RX, RY)
            else:       # drawn on: the ellipse's outline up to f of its length
                ring = QPainterPath()
                ring.addEllipse(QPointF(0, 0), RX, RY)
                p.drawPolyline(QPolygonF([ring.pointAtPercent(f * i / 48) for i in range(49)]))
            p.restore()
        late = route_alpha(self.p)
        p.setOpacity(0.6 * late)
        p.setPen(QPen(hl, 1.6, cap=Qt.PenCapStyle.RoundCap))
        for j, (a, b) in enumerate(zip(cs, cs[1:])):
            d = b - a
            t = 1 / math.hypot(d.x() / RX, d.y() / RY)     # the share of a→b inside each circle
            if t > 0.45:            # neighbours: the circles touch, no room for a route
                continue
            s, e = a + d * t, b - d * t
            route = QPainterPath(s)
            route.quadTo((s + e) / 2 + QPointF(-d.y(), d.x()) * (0.18 if j % 2 else -0.18), e)   # bowed, alternately
            p.drawPath(route)
        p.setOpacity(late)
        p.setPen(QPen(hl, 2.4, cap=Qt.PenCapStyle.RoundCap))
        for k, c in zip(ks, cs):
            if self.cells[k].died:
                x, y = c.x() - 24, c.y() + 14
                p.drawLine(QPointF(x, y), QPointF(x + 8, y + 8))
                p.drawLine(QPointF(x + 8, y), QPointF(x, y + 8))
        p.setOpacity(1)
        self._note(p, cs[0] if cs else None)
        # 3. the cells' text, each run haloed in panel
        nf, sf, gf = font(11, 500, num=True), font(21, 700, num=True), font(14, 700, num=True)
        for k, c in enumerate(self.cells):
            r = self.cell_rect(k)
            x, y = r.x() + 5, r.y() + 4
            halo_text(p, nf, tok("mu"), x, baseline(nf, y, 12), str(c.index + 1))
            halo_text(p, nf, tok("mu"), x, baseline(nf, y + 12, 13), c.at)
            base = baseline(sf, y + 27, 24)
            if c.score is None:     # nothing judged in this fight
                halo_text(p, sf, tok("mu"), x, base, "–")
            else:
                ink = theme.grade_color(c.grade)
                w = halo_text(p, sf, ink, x, base, str(c.score))
                halo_text(p, gf, ink, x + w + 2, base, c.grade)
            if c.boss:
                p.fillRect(QRectF(r.right() - 11, r.y() + 5, 6, 6), tok("tx"))
        if self.hasFocus() and self.cells:
            box(p, self.cell_rect(self.focus), tok("hl"), width=2)

    def _note(self, p: QPainter, first: QPointF | None):
        """"review these 4" in Caveat above the grid, with an arrow to the first circle"""
        if self.review:
            s = f"review these {len(self.review)}"
        elif self.cells and all(c.score is not None for c in self.cells):
            s = "every fight 90+"
        else:
            return
        f = QFont(theme.HAND_FONT)
        f.setPixelSize(27)
        f.setWeight(QFont.Weight(600))
        tw, base = adv(f, s), NOTE_H - 12
        cx = first.x() if first else PAD + 297     # no circle: where the mock-up's first one is
        side = 1 if cx - 61 - tw >= PAD else -1     # the note left of the circle, or right of it near the left edge
        x = min(max(cx - 61 - tw if side > 0 else cx + 61, PAD), PAD + COLS * CELL_W - tw)
        p.save()
        p.setOpacity(note_alpha(self.p))
        p.translate(x, base)
        p.rotate(-3)
        text_at(p, f, tok("hl-note"), 0, 0, s)
        p.restore()
        if first is None:
            return
        p.setOpacity(note_alpha(self.p))
        start = QPointF(x + tw if side > 0 else x, base - 4)
        end = QPointF(first.x() - 7 * side, first.y() - RY - 6)
        ctrl = QPointF(end.x() - 18 * side, start.y() + 4)
        arrow = QPainterPath(start)
        arrow.quadTo(ctrl, end)
        u = (end - ctrl) / math.hypot((end - ctrl).x(), (end - ctrl).y())
        for a in (0.5, -0.5):       # the head: two barbs either side of the way in
            arrow.moveTo(end - QPointF(u.x() * math.cos(a) - u.y() * math.sin(a),
                                       u.x() * math.sin(a) + u.y() * math.cos(a)) * 9)
            arrow.lineTo(end)
        p.setPen(QPen(tok("hl"), 1.8, cap=Qt.PenCapStyle.RoundCap, join=Qt.PenJoinStyle.RoundJoin))
        p.drawPath(arrow)
        p.setOpacity(1)


class FightsColumn(QWidget):
    """the right-hand column: the header and grade key, then the FightGrid (in a scroll area past 8 rows)"""
    KEY = (("S", "S", 90), ("A", "A", 80), ("B", "B C", 60), ("D", "D", 45))

    def __init__(self):
        super().__init__()
        self.setFixedWidth(FIGHTS_W + EDGE)
        self.n = 0
        self.grid = FightGrid()
        self.scroll = QScrollArea()
        self.scroll.setWidget(self.grid)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28 - PAD, 61, 0, 0)      # under the header (12 + 26 + 6) and the key (17)
        lay.addWidget(self.scroll)
        lay.addStretch(1)
        self.set_cells([], [])

    def set_cells(self, cells: list[FightCell], review: list[int]):
        self.n = len(cells)
        self.grid.set_cells(cells, review)
        self.scroll.setFixedHeight(min(self.grid.height(), NOTE_H + GRID_VIEW))
        self.scroll.setVisible(bool(cells))
        self.update()

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.fillRect(QRectF(0, 0, 1, self.height()), tok("ln"))
        hf = font(22, 700, num=True, spacing=0.04)
        base = baseline(hf, 12, 22 * 1.2)
        x = 28 + text_at(p, hf, tok("tx"), 28, base, f"FIGHTS · {self.n} ")
        if not self.n:
            return
        text_at(p, font(15, 700, num=True, spacing=0.04), tok("mu"), x, base, "· CIRCLED = REVIEW FIRST")
        bf, kf = font(14, 700, num=True, spacing=0.04), font(12, 600, num=True, spacing=0.04)
        base, x = baseline(bf, 12 + 22 * 1.2 + 6, 17), 28
        for grade, letters, low in self.KEY:
            ink = theme.grade_color(grade)
            x += text_at(p, bf, ink, x, base, letters)
            x += text_at(p, kf, ink, x, base, f" ≥{low}") + 14
        p.fillRect(QRectF(x, base - 7, 7, 7), tok("tx"))
        text_at(p, kf, tok("mu"), x + 11, base, "boss")


class DebriefPage(QWidget):
    """the title and meta line, then the debrief on the left and the fights on the right"""
    zoom = pyqtSignal(float, float)
    picked = pyqtSignal(int)          # a fight's index, or -1 for the whole run

    def __init__(self):
        super().__init__()
        self.title = self.sub = ""
        self.show_me: tuple[float, float] | None = None
        self.narrow = None
        self.settings: dict = {}        # the app's (shared), for "motion"
        self.shown = None               # what the entrance last ran for
        self.entrance = QVariantAnimation(self, startValue=0.0, endValue=1.0, duration=ENTRANCE_MS,
                                          easingCurve=QEasingCurve.Type.OutQuart)
        self.entrance.valueChanged.connect(self.set_progress)
        self.hero, self.plate, self.measures, self.breakdown = Hero(), FixPlate(), MeasureBars(), Breakdown()
        self.plate.button.clicked.connect(lambda: self.show_me and self.zoom.emit(*self.show_me))
        self.top = QWidget()
        self.top.setFixedHeight(HEAD_H)
        self.top.setContentsMargins(0, 0, EDGE, 0)
        self.head = QHBoxLayout(self.top)      # right of the title: Whole run, and room for the player picker
        self.head.setContentsMargins(0, 0, 0, 0)
        self.head.addStretch(1)
        self.whole = QPushButton("Whole run")  # while one fight's debrief shows
        self.whole.hide()
        self.whole.clicked.connect(lambda: self.picked.emit(-1))
        self.head.addWidget(self.whole, 0, Qt.AlignmentFlag.AlignTop)
        self.hero_row = QHBoxLayout()
        self.hero_row.setContentsMargins(0, 14, 0, 16)
        self.hero_row.addWidget(self.hero, 0, Qt.AlignmentFlag.AlignTop)
        self.hero_row.addWidget(self.plate, 1, Qt.AlignmentFlag.AlignTop)
        self.hero_row.addStretch(0)   # the plate hidden: the hero keeps its width (and wraps at it) on the left
        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 28, 0)
        left.setSpacing(0)
        left.addLayout(self.hero_row)
        left.addWidget(self.measures)
        left.addWidget(self.breakdown)
        left.addItem(QSpacerItem(LEFT_MIN, 0, QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Expanding))
        self.fights = FightsColumn()
        self.fights.grid.picked.connect(self.picked)
        cols = QHBoxLayout()
        cols.setSpacing(0)
        cols.addLayout(left, 1)
        cols.addWidget(self.fights)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 4, 0, 0)     # the tab bar is the air above; EDGE on the right, inside the parts
        lay.setSpacing(0)
        lay.addWidget(self.top)
        lay.addLayout(cols, 1)
        self._fit()

    def show_view(self, view: DebriefView, title: str, sub: str, show_me: tuple[float, float] | None = None,
                  whose: str = "your", one_fight: bool = False):
        """show_me: the (start, end) "Show me on the timeline" zooms to; whose: "your", or "Anna's";
        one_fight: the view is one fight's, so offer the way back to the whole run"""
        self.title, self.sub = title, sub
        self.whole.setVisible(one_fight)
        self.show_me = show_me if view.fix else None
        self.plate.can_show = self.show_me is not None
        self.breakdown.whose = whose
        self.fights.set_cells(view.fights, view.review)
        for part in (self.hero, self.plate, self.measures, self.breakdown):
            part.set_view(view, self.narrow)
        self.plate.setVisible(view.grade != "-")          # nothing judged (or no run): nothing to fix either
        self.measures.setVisible(bool(view.measures))    # an empty or unjudgeable card: nothing to measure
        self.breakdown.setVisible(bool(view.categories))  # but its categories stay listed
        self._wrap_next()
        self.update()
        key = (title, sub, whose, one_fight)      # a new run, fight or player; not a redraw of the same one
        if key != self.shown:
            self.shown = key
            self.entrance.stop()
            motion = bool(self.settings.get("motion", True))
            self.set_progress(0.0 if motion else 1.0)
            if motion:
                self.entrance.start()

    def set_progress(self, p: float):
        """the entrance's p (1: settled) to the parts that animate"""
        for part in (self.hero, self.measures, self.breakdown, self.fights.grid):
            part.p = p
            part.update()

    def resizeEvent(self, ev):
        self._fit()
        self._wrap_next()
        super().resizeEvent(ev)

    def _wrap_next(self):
        """wrap the plate's next fixes, as the mock-up does, when the page (drawer shut) still fits its height;
        otherwise they stay one line each"""
        m = self.layout().contentsMargins()
        lw = self.measures.width()
        rest = ((self.measures.heightForWidth(lw) if self.measures.isVisibleTo(self) else 0)
                + (math.ceil(self.breakdown.draw(None, lw, open_=False)) if self.breakdown.isVisibleTo(self) else 0))
        plate = math.ceil(self.plate.draw(None, self.plate.width(), wrap=True)) if self.plate.isVisibleTo(self) else 0
        need = m.top() + HEAD_H + 14 + max(self.hero.heightForWidth(self.hero.width()), plate) + 16 + rest + m.bottom()
        wrap = need <= (self.parentWidget() or self).height()
        if wrap != self.plate.wrap:
            self.plate.wrap = wrap
            self.plate.set_view(self.plate.view, self.narrow)

    def _fit(self):
        """the mock-up's narrow hero below a 1420px window"""
        narrow = self.window().width() < NARROW
        if narrow == self.narrow:
            return
        self.narrow = narrow
        self.hero.setFixedWidth(214 if narrow else 260)
        self.hero_row.setSpacing(22 if narrow else 28)
        for part in (self.hero, self.plate, self.measures, self.breakdown):
            part.set_view(part.view, narrow)

    def paintEvent(self, _ev):
        p = QPainter(self)
        if not theme.TEXTURE:       # the page sits on bg, like the mock-up's main column
            p.fillRect(self.rect(), tok("bg"))
        m = self.layout().contentsMargins()
        x, top = m.left(), m.top()
        picker = self.top.childrenRect()
        right = self.top.x() + picker.left() - 16 if picker.isValid() else self.width() - EDGE
        tf = font(30, 700, num=True)
        line(p, tf, tok("tx"), x, top, 31.5, elide(tf, self.title, right - x))
        head, sep, rest = self.sub.partition(" · ")      # the date in tx, the rest in tx2
        mf, bf = font(13), font(13, 600)
        mt = top + 31.5 + 4
        hw = line(p, bf, tok("tx"), x, mt, 13 * 1.4, elide(bf, head, right - x))
        if sep:
            line(p, mf, tok("tx2"), x + hw, mt, 13 * 1.4, elide(mf, sep + rest, right - x - hw))
        rule(p, x, top + HEAD_H - 1, self.width() - m.left() - EDGE, tok("gold"))
