"""The Debrief tab's page, painted from a DebriefView (see dips_score/debrief.py): the score and verdict, the one
fix on the plate, the main measures and where the points went; the fights column on the right.

Sizes follow docs/design/mockups/debrief.html (CSS px). Each part paints itself, and the same pass measures its
height for a width, so text wraps the way it is drawn.
"""
import math

from PyQt6.QtCore import QEvent, QPointF, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QTextLayout
from PyQt6.QtWidgets import QHBoxLayout, QPushButton, QSizePolicy, QToolTip, QVBoxLayout, QWidget

from ..debrief import DebriefView, display_name
from . import theme
from .theme import tok

MINUS = "−"
NARROW = 1420        # the mock-up's breakpoint (window width): a smaller hero below it
HEAD_H = 71          # title, meta line and the gold rule under them
FIGHTS_W = 460       # the right-hand column
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
        x = text_at(p, f, tok("tx"), 0, baseline(f, top, lh), v.total)
        if v.grade != "-":   # "-": nothing judgeable, so no grade to box
            gpx, pv, ph = (46, 4, 10) if self.narrow else (56, 5, 12)
            g = font(gpx, 700, num=True)
            r = QRectF(x + 10, top + 6, adv(g, v.grade) + 2 * ph + 4, gpx + 2 * pv + 4)
            if p:
                box(p, r, tok("gold"), width=2)
            text_at(p, g, theme.grade_color(v.grade), r.x() + 2 + ph, baseline(g, r.y() + 2 + pv, gpx), v.grade)
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
        """the next fixes are cut to one line each: hovering them shows them whole"""
        if ev.type() == QEvent.Type.ToolTip and self.view.next_fixes and ev.pos().y() >= self.next_y:
            QToolTip.showText(ev.globalPos(), "\n".join(nx.title for nx in self.view.next_fixes), self)
            return True
        return super().event(ev)

    def paintEvent(self, _ev):
        p = QPainter(self)
        h = self.draw(None, self.width())
        p.fillRect(QRectF(0, 12, self.width(), h - 12), tok("plate"))
        self.draw(p, self.width())
        label_tab(p, 14, 0, "Fix this first")    # straddles the plate's top edge

    def draw(self, p, w):
        v, fix, n = self.view, self.view.fix, self.narrow
        x, cw = 18, w - 36
        y = 12 + 22
        tpx = 21 if n else 23
        y += wrapped(p, font(tpx, 600, num=True), tok("plate-tx"), x, y, cw, tpx * 1.15,
                     fix.title if fix else "Nothing stands out — nice run.") + 8
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
                if p:
                    line(p, bf, tok("plate-ac"), x + cw - cost_w, y, lh, cost)
                    line(p, nf, tok("plate-tx"), x, y, lh, elide(nf, nx.title, cw - cost_w - 10))
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
        bx, bw = 174, w - 298           # columns: 160 name, 14 gap, the bar, 14 gap, 110 value
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
                p.fillRect(QRectF(bx, by, bw * max(0.0, min(100.0, m.score or 0)) / 100, 10), tok(m.ink))
                p.fillRect(QRectF(bx + bw * 0.9, by - 4, 2, 18), tok("tx"))
                line(p, rf, tok("mu"), bx, y + r1 - 2, 11 * 1.4, elide(rf, m.reason, bw))
                score = f"{m.score:.0f}"
                base = baseline(vf, y + (r1 + r2 - 30) / 2, 30)
                sw = text_at(p, vf, tok("tx"), w - adv(vf, score), base, score)
                note = "on target" if m.on_target else "below 90"
                text_at(p, sf, tok("mu"), w - sw - 6 - adv(sf, note), base, note)
            y += r1 + r2 + 5
        return y + 12


class Breakdown(_Part):
    """Where your points went: a bar per category, as long as the points it lost, then the points earned"""

    def draw(self, p, w):
        v = self.view
        if p:
            rule(p, 0, 0, w, tok("ln"))
        y = 1 + 12
        label_tab(p, 0, y, f"Where your {100 - v.earned} points went")
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
                p.fillRect(QRectF(120, y + 3 + 4, 220 * lost.points / most, 10), tok(lost.ink))
                s = f"{MINUS}{lost.points:.1f}"
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
        return y + 22 + 3 + 12


class FightsColumn(QWidget):
    """the right-hand column: its header; Task 7 adds the FightGrid to self.layout(), under it"""

    def __init__(self):
        super().__init__()
        self.setFixedWidth(FIGHTS_W)
        self.n = 0
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 12 + 31 + 6, 0, 0)
        lay.addStretch(1)

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.fillRect(QRectF(0, 0, 1, self.height()), tok("ln"))
        line(p, font(22, 700, num=True, spacing=0.04), tok("tx"), 28, 12, 22 * 1.4, f"FIGHTS · {self.n}")


class DebriefPage(QWidget):
    """the title and meta line, then the debrief on the left and the fights on the right"""
    zoom = pyqtSignal(float, float)
    picked = pyqtSignal(int)          # a fight's index, or -1 for the whole run

    def __init__(self):
        super().__init__()
        self.title = self.sub = ""
        self.show_me: tuple[float, float] | None = None
        self.narrow = None
        self.hero, self.plate, self.measures, self.breakdown = Hero(), FixPlate(), MeasureBars(), Breakdown()
        self.plate.button.clicked.connect(lambda: self.show_me and self.zoom.emit(*self.show_me))
        self.top = QWidget()
        self.top.setFixedHeight(HEAD_H)
        self.head = QHBoxLayout(self.top)      # right of the title: room for the player picker
        self.head.setContentsMargins(0, 0, 0, 0)
        self.head.addStretch(1)
        self.hero_row = QHBoxLayout()
        self.hero_row.setContentsMargins(0, 14, 0, 16)
        self.hero_row.addWidget(self.hero, 0, Qt.AlignmentFlag.AlignTop)
        self.hero_row.addWidget(self.plate, 1, Qt.AlignmentFlag.AlignTop)
        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 28, 0)
        left.setSpacing(0)
        left.addLayout(self.hero_row)
        left.addWidget(self.measures)
        left.addWidget(self.breakdown)
        left.addStretch(1)
        self.fights = FightsColumn()
        cols = QHBoxLayout()
        cols.setSpacing(0)
        cols.addLayout(left, 1)
        cols.addWidget(self.fights)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 4, 16, 0)    # the tab bar is the air above
        lay.setSpacing(0)
        lay.addWidget(self.top)
        lay.addLayout(cols, 1)
        self._fit()

    def show_view(self, view: DebriefView, title: str, sub: str, show_me: tuple[float, float] | None = None):
        """show_me: the (start, end) "Show me on the timeline" zooms to"""
        self.title, self.sub = title, sub
        self.show_me = show_me if view.fix else None
        self.plate.can_show = self.show_me is not None
        self.fights.n = len(view.fights)
        self.fights.update()
        for part in (self.hero, self.plate, self.measures, self.breakdown):
            part.set_view(view, self.narrow)
        for part in (self.measures, self.breakdown):     # an empty card: nothing to measure
            part.setVisible(bool(view.measures))
        self.update()

    def resizeEvent(self, ev):
        self._fit()
        super().resizeEvent(ev)

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
        right = self.top.x() + picker.left() - 16 if picker.isValid() else self.width() - m.right()
        tf = font(30, 700, num=True)
        line(p, tf, tok("tx"), x, top, 31.5, elide(tf, self.title, right - x))
        head, sep, rest = self.sub.partition(" · ")      # the date in tx, the rest in tx2
        mf, bf = font(13), font(13, 600)
        mt = top + 31.5 + 4
        hw = line(p, bf, tok("tx"), x, mt, 13 * 1.4, elide(bf, head, right - x))
        if sep:
            line(p, mf, tok("tx2"), x + hw, mt, 13 * 1.4, elide(mf, sep + rest, right - x - hw))
        rule(p, x, top + HEAD_H - 1, self.width() - m.left() - m.right(), tok("gold"))
