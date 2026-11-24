"""The painted parts every page is built from, so they all draw the same way: the page's head, the boxed label tab,
the hero figure, the one solid plate, ruled bar rows, key figures, the "All … (n)" drawer and its fold, a section's
head, the side column, kind and preview tags and the highlighter's hand marks.

Sizes follow docs/design/mockups/*.html (CSS px). A Part paints itself, and the same pass measures its height for a
width, so text wraps the way it is drawn. Colours come from theme.tok() when painting, so a theme switch needs
nothing more than a repaint.
"""
import math
from dataclasses import dataclass
from itertools import groupby

from PyQt6.QtCore import QEvent, QPointF, QRect, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPen, QPolygonF, QTextLayout
from PyQt6.QtWidgets import QHBoxLayout, QPushButton, QSizePolicy, QToolTip, QVBoxLayout, QWidget

from ..debrief import bar_fraction, ticker
from . import theme
from .theme import tok

MINUS = "−"
GRADES = ("S", "A", "B", "C", "D", "F")
HEAD_H = 71          # a page's head: the title, the meta line and the gold rule under them
SECTION_H = 1 + 12 + 25 + 6     # a section's head (SectionHead): its rule, padding and label tab


# ---------------------------------------------------------------------------- painting helpers
def font(px: int, weight: int = 400, num: bool = False, spacing: float = 0) -> QFont:
    """Barlow (num: Barlow Condensed) at px pixels; spacing in em, like the mock-up's letter-spacing"""
    f = QFont(theme.NUM_FONT if num else theme.FONT)
    f.setPixelSize(px)
    f.setWeight(QFont.Weight(weight))
    if spacing:
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing * px)
    return f


def hand_font(px: int = 27) -> QFont:
    """Caveat 600, 27px unless told: the highlighter's handwriting"""
    f = QFont(theme.HAND_FONT)
    f.setPixelSize(px)
    f.setWeight(QFont.Weight(600))
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


def draw_label_tab(p, x, y, text) -> QRectF:
    """the boxed section label: Barlow Condensed 700 11px, .16em, capitals, a 1px ln frame on panel"""
    f, s = font(11, 700, num=True, spacing=0.16), text.upper()
    r = QRectF(x, y, adv(f, s) + 22, 25)
    if p:
        box(p, r, tok("ln"), tok("panel"))
        line(p, f, tok("tx"), x + 11, y + 7, 11, s)
    return r


def draw_page_head(p, x, top, right, title, sub, text_right=None):
    """a page's head: the title, then the meta line (its part before the first " · " in tx, the rest in tx2), cut
    short of text_right (default right), over the gold rule from x to right"""
    text_right = right if text_right is None else text_right
    tf = font(30, 700, num=True)
    line(p, tf, tok("tx"), x, top, 31.5, elide(tf, title, text_right - x))
    head, sep, rest = sub.partition(" · ")
    mf, bf = font(13), font(13, 600)
    mt = top + 31.5 + 4
    hw = line(p, bf, tok("tx"), x, mt, 13 * 1.4, elide(bf, head, text_right - x))
    if sep:
        line(p, mf, tok("tx2"), x + hw, mt, 13 * 1.4, elide(mf, sep + rest, text_right - x - hw))
    rule(p, x, top + HEAD_H - 1, right - x, tok("gold"))


def halo_text(p: QPainter, f: QFont, color: QColor, x: float, base: float, s: str) -> float:
    """s on the baseline with a 3px panel halo, so it reads through the highlighter; returns its width"""
    path = QPainterPath()
    path.addText(x, base, f, s)
    p.strokePath(path, QPen(tok("panel"), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                            Qt.PenJoinStyle.RoundJoin))
    p.fillPath(path, color)
    return adv(f, s)


# ---------------------------------------------------------------------------- the highlighter
def draw_hand_circle(p: QPainter, rect: QRectF, ink: QColor, rotation: float, frac: float = 1.0):
    """a highlighter ring around rect, turned by rotation degrees; frac < 1 draws it on, up to frac of its length"""
    if frac <= 0:
        return
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setOpacity(0.8 * p.opacity())
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(ink, 5, cap=Qt.PenCapStyle.RoundCap, join=Qt.PenJoinStyle.RoundJoin))
    p.translate(rect.center())
    p.rotate(rotation)
    rx, ry = rect.width() / 2, rect.height() / 2
    if frac >= 1:
        p.drawEllipse(QPointF(0, 0), rx, ry)
    else:
        ring = QPainterPath()
        ring.addEllipse(QPointF(0, 0), rx, ry)
        p.drawPolyline(QPolygonF([ring.pointAtPercent(frac * i / 48) for i in range(49)]))
    p.restore()


def draw_hand_note(p: QPainter, text: str, anchor: QPointF, target: QPointF | None, px: int = 27):
    """text in the highlighter's hand (px tall), its baseline starting at anchor and tilted 3° up, with an arrow
    from its nearer end to target (None: no arrow). Fade it with the painter's opacity."""
    f = hand_font(px)
    p.save()
    p.translate(anchor)
    p.rotate(-3)
    text_at(p, f, tok("hl-note"), 0, 0, text)
    p.restore()
    if target is None:
        return
    tw = adv(f, text)
    side = 1 if target.x() >= anchor.x() + tw / 2 else -1      # the target right of the note, or left of it
    start = QPointF(anchor.x() + tw if side > 0 else anchor.x(), anchor.y() - 4)
    ctrl = QPointF(target.x() - 18 * side, start.y() + 4)
    arrow = QPainterPath(start)
    arrow.quadTo(ctrl, target)
    u = (target - ctrl) / math.hypot((target - ctrl).x(), (target - ctrl).y())
    for a in (0.5, -0.5):       # the head: two barbs either side of the way in
        arrow.moveTo(target - QPointF(u.x() * math.cos(a) - u.y() * math.sin(a),
                                      u.x() * math.sin(a) + u.y() * math.cos(a)) * 9)
        arrow.lineTo(target)
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(tok("hl"), 1.8, cap=Qt.PenCapStyle.RoundCap, join=Qt.PenJoinStyle.RoundJoin))
    p.drawPath(arrow)
    p.restore()


# ---------------------------------------------------------------------------- the parts
class Sheet(QWidget):
    """a page under its parts: the ground, and its head (draw_page_head) at the layout's margins. head: the widget
    across the top holding the page's picks, which the title stops short of (None: no picks)"""

    def __init__(self, head: QWidget | None = None):
        super().__init__()
        self.title = self.sub = ""
        self.head = head

    def paintEvent(self, _ev):
        p = QPainter(self)
        if not theme.TEXTURE:
            p.fillRect(self.rect(), tok("bg"))
        m = self.layout().contentsMargins()
        right = self.width() - m.right()
        picks = self.head.childrenRect() if self.head else QRect()
        draw_page_head(p, m.left(), m.top(), right, self.title, self.sub,
                       self.head.x() + picks.left() - 16 if picks.isValid() else right)


class Part(QWidget):
    """a painted part: draw(None, w) measures its height for a width, draw(p, w) paints it. narrow: the
    mock-ups' smaller sizes (below a 1420px window); p: the entrance's progress, 1 draws it settled"""

    def __init__(self):
        super().__init__()
        self.narrow = False
        self.p = 1.0
        sp = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sp.setHeightForWidth(True)
        self.setSizePolicy(sp)

    def changed(self):
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


class Hero(Part):
    """the page's one big figure: the number (ticking up in the entrance), a grade boxed in gold or a unit beside
    it, then an optional caption and chip, and the verdict. A "–" number (nothing to show) is muted."""

    def __init__(self):
        super().__init__()
        self.big, self.suffix, self.caption, self.chip, self.verdict = "–", None, None, None, ""
        self.unit = (64, 54, 700, 6, 2)     # a unit's px (narrow px), weight, and dx, dy from the number's top right
        self.bar: tuple[float, str] | None = None     # a bullet bar under the caption: its share (0..1) and ink
        self.ink = "tx"                     # the number's
        self.chip_ink: str | None = None    # the chip's box, its text then in tx (None: both in gD or gS by its sign)
        self.verdict_look = (15, 400, "tx2")     # the verdict's px, weight and ink

    def set(self, big: str, suffix: str | None, caption: str | None, chip: str | None, verdict: str):
        """suffix: a grade letter (boxed) or a unit ("%", "K", "pulls"); chip: a change, "−…" in gD, else gS"""
        self.big, self.suffix, self.caption, self.chip, self.verdict = big, suffix, caption, chip, verdict
        self.changed()

    def draw(self, p, w):
        px = 126 if self.narrow else 150
        f = font(px, 700, num=True, spacing=-0.02)
        top, lh = 8, px * 0.8
        x = adv(f, self.big)      # the final width, so what's beside it doesn't move while the number ticks
        if p:
            ink = tok("mu") if self.big == "–" else tok(self.ink)   # "–": nothing to show, so it reads as a dash
            text_at(p, f, ink, 0, baseline(f, top, lh), ticker(self.big, self.p))
        if self.suffix in GRADES:
            gpx, pv, ph = (46, 4, 10) if self.narrow else (56, 5, 12)
            g = font(gpx, 700, num=True)
            r = QRectF(x + 10, top + 6, adv(g, self.suffix) + 2 * ph + 4, gpx + 2 * pv + 4)
            if p:
                p.setOpacity(min(1.0, self.p / 0.78))      # the grade appears as the number lands
                box(p, r, tok("gold"), width=2)
            text_at(p, g, theme.grade_color(self.suffix), r.x() + 2 + ph, baseline(g, r.y() + 2 + pv, gpx), self.suffix)
            if p:
                p.setOpacity(1)
        elif self.suffix and p:
            px, npx, weight, dx, dy = self.unit
            u = font(npx if self.narrow else px, weight, num=True)
            line(p, u, tok("tx2"), x + dx, top + dy, u.pixelSize(), self.suffix)
        y = top + lh + 16
        if self.caption:
            y += wrapped(p, font(14), tok("mu"), 0, y, w, 14 * 1.4, self.caption) + 8
        if self.bar is not None:
            y = self._bar(p, w, y + 4)
        if self.chip:
            cf, ch = font(14, 600, num=True), 14 * 1.2 + 6
            if p:
                ink = tok(self.chip_ink or ("gD" if self.chip.startswith((MINUS, "-")) else "gS"))
                box(p, QRectF(0, y, adv(cf, self.chip) + 18, ch), ink)
                line(p, cf, tok("tx") if self.chip_ink else ink, 9, y + 3, 14 * 1.2, self.chip)
            y += ch + 8
        px, weight, ink = self.verdict_look
        return y + wrapped(p, font(px, weight), tok(ink), 0, y, w, px * 1.4, self.verdict)

    def _bar(self, p, w, y) -> float:
        """the bullet bar from y: 10px on track, filled to its share, the 2px tx tick at 90% overhanging 4px with
        CLEAN under it; returns where the verdict starts"""
        if p:
            share, ink = self.bar
            p.fillRect(QRectF(0, y, w, 10), tok("track"))
            p.fillRect(QRectF(0, y, w * min(1.0, share) * bar_fraction(self.p, 0), 10), tok(ink))
            p.fillRect(QRectF(round(w * 0.9), y - 4, 2, 18), tok("tx"))
            f = font(11, 600, num=True, spacing=0.12)
            line(p, f, tok("mu"), w * 0.9 - adv(f, "CLEAN") / 2, y + 10 + 6, 12, "CLEAN")
        return y + 10 + 6 + 12 + 10


class Plate(Part):
    """the one solid plate, the thing to act on: its label tab straddling the top edge, a title, an optional
    paragraph, the price and its caption, an optional button (clicked), then ruled rows of (text, cost) for what
    comes next"""
    clicked = pyqtSignal()

    def __init__(self, label: str):
        super().__init__()
        self.label = label
        self.title, self.price, self.caption, self.rows, self.body = "", None, None, [], None
        self.button = QPushButton(self)
        self.button.setObjectName("showme")
        self.button.hide()
        self.button.clicked.connect(self.clicked)
        self.has_button = False
        self.wrap = True           # the rows wrap; the page sets False when that wouldn't fit its height
        self.price_px = 32         # the price's size (the fight page's is 46)
        self.title_px = None       # the title's size (None: 23, narrow 21; the history plate's is 34)
        self.body_last = False     # True: the body under the price, not under the title
        self.price_words = False   # True: only the price's figure big, its words muted, the caption on its own line
        self.button_y = self.next_y = 0.0

    def set(self, title: str, price: str | None, caption: str | None, button: str | None,
            rows: list[tuple[str, str]], body: str | None = None):
        """caption: muted words after the price, " · " between parts that wrap apart; button: its text, None for
        none; body: a muted paragraph under the title, wrapped"""
        self.title, self.price, self.caption, self.rows, self.body = title, price, caption, rows, body
        self.has_button = button is not None
        if button is not None:
            self.button.setText(button)
        self.changed()
        self._place()

    def resizeEvent(self, ev):
        self._place()
        super().resizeEvent(ev)

    def _place(self):
        self.button.adjustSize()
        self.draw(None, self.width())       # finds button_y
        self.button.move(18, round(self.button_y))
        self.button.setVisible(self.has_button)

    def event(self, ev):
        """when the rows are cut to one line each, hovering them shows them whole"""
        if ev.type() == QEvent.Type.ToolTip and not self.wrap and self.rows and ev.pos().y() >= self.next_y:
            QToolTip.showText(ev.globalPos(), "\n".join(text for text, _ in self.rows), self)
            return True
        return super().event(ev)

    def paintEvent(self, _ev):
        p = QPainter(self)
        h = self.draw(None, self.width())
        p.fillRect(QRectF(0, 12, self.width(), h - 12), tok("plate"))
        self.draw(p, self.width())
        draw_label_tab(p, 14, 0, self.label)    # straddles the plate's top edge

    def draw(self, p, w, wrap: bool | None = None):
        n = self.narrow
        wrap = self.wrap if wrap is None else wrap
        x, cw = 18, w - 36
        y = 12 + 22
        tpx = self.title_px or (21 if n else 23)
        y += wrapped(p, font(tpx, 600, num=True), tok("plate-tx"), x, y, cw, tpx * 1.15, self.title) + 8
        if self.body and not self.body_last:
            y += wrapped(p, font(14), tok("plate-mu"), x, y, cw, 14 * 1.45, self.body) + 4
        price = [(self.price, font(self.price_px, 700, num=True), tok("plate-ac"))] if self.price else []
        gap = 12 if n else 18
        if self.price_words and self.price:     # "about 7,298 damage", 7px apart
            words = [(" ".join(ws), *((font(self.price_px, 700, num=True), tok("plate-ac")) if big else
                                      (font(13), tok("plate-mu"))))
                     for big, ws in groupby(self.price.split(), lambda s: any(c.isdigit() for c in s))]
            y += flow(p, words, x, y, cw, 7, 2) + 2
            price, gap = [], 7
        words = [(s, font(13), tok("plate-mu")) for s in (self.caption or "").split(" · ") if s]
        if not price and len(words) == 1 and adv(font(13), words[0][0]) > cw:       # a caption alone, longer than its line
            y += wrapped(p, font(13), tok("plate-mu"), x, y, cw, 13 * 1.4, words[0][0])
        elif price + words:
            y += flow(p, price + words, x, y, cw, gap, 2)
        if self.body and self.body_last:
            y += 6 + wrapped(p, font(13), tok("plate-mu"), x, y + 6, cw, 13 * 1.4, self.body)
        if self.has_button:
            self.button_y = y + 10
            y = self.button_y + self.button.sizeHint().height()
        if self.rows:
            y += 10
            if p:
                rule(p, x, y, cw, tok("plate-ln"))
            y += 1 + 7
            self.next_y = y
            nf, bf, lh = font(12 if n else 13), font(14, 600, num=True), (12 if n else 13) * 1.4
            for k, (text, cost) in enumerate(self.rows):
                y += 4 if k else 0
                cost_w = adv(bf, cost)
                tw = max(0.0, cw - cost_w - 10)
                if p:
                    line(p, bf, tok("plate-ac"), x + cw - cost_w, y, lh, cost)
                if wrap:
                    y += wrapped(p, nf, tok("plate-tx"), x, y, tw, lh, text)
                else:
                    if p:
                        line(p, nf, tok("plate-tx"), x, y, lh, elide(nf, text, tw))
                    y += lh
        return y + 14


@dataclass
class BarRow:
    name: str
    value_text: str
    fraction: float              # the bar's share of the longest, 0..1; 0 draws none
    ink: str                     # the bar's token
    note: str | None = None      # muted, after the name ("×12")


class BarRows(Part):
    """a section of ranked rows: a rule, its label tab, then a ruled row each (name, a bar sized by impact in
    the row's ink, the value on the right), and an optional total under a heavy rule. lead: a line of words over the
    rows, no bar ("Melee 46% of your damage", 0.46): a bar there would read as a loss"""
    name_w, bar_w = 120, 220     # where the bars start, and the longest one
    top_rule = True              # the rule above the tab (off under a part that ends on one)
    lead: tuple[str, float] | None = None

    def __init__(self, title: str = ""):
        super().__init__()
        self.title = title
        self.rows: list[BarRow] = []
        self.total: tuple[str, str] | None = None

    def set(self, rows: list[BarRow], total: tuple[str, str] | None):
        """total: (label, value); the label's part after " · " is muted ("Earned · 75 of 100")"""
        self.rows, self.total = rows, total
        self.changed()

    def draw(self, p, w):
        if p and self.top_rule:
            rule(p, 0, 0, w, tok("ln"))
        y = 1 + 12
        draw_label_tab(p, 0, y, self.title)
        y += 25 + 8
        nf, vf = font(15), font(15, 700, num=True)
        if self.lead:
            if p:
                lf = font(13)
                line(p, lf, tok("tx2"), 0, y + 3, 18, elide(lf, self.lead[0], w))
            y += 3 + 18 + 3
            if self.rows:
                if p:
                    rule(p, 0, y, w, tok("ln"))
                y += 1
        for k, row in enumerate(self.rows):
            if k:
                if p:
                    rule(p, 0, y, w, tok("ln"))
                y += 1
            if p:
                nw = line(p, nf, tok("tx"), 0, y + 3, 18, row.name)
                if row.note:
                    line(p, font(13), tok("mu"), nw + 6, y + 3, 18, row.note)
                if row.fraction > 0:
                    p.fillRect(QRectF(self.name_w, y + 3 + 4, self.bar_w * row.fraction * bar_fraction(self.p, k), 10),
                               tok(row.ink))
                line(p, vf, tok("tx"), w - adv(vf, row.value_text), y + 3, 18, row.value_text)
            y += 3 + 18 + 3
        if self.total:
            if p:
                rule(p, 0, y, w, tok("tx"), 2)
            y += 2 + 6
            if p:
                label, value = self.total
                head, sep, rest = label.partition(" · ")
                ef, sf = font(20, 700, num=True), font(14, 500, num=True, spacing=0.04)
                base = baseline(ef, y, 22)
                ew = text_at(p, ef, tok("tx"), 0, base, head)
                if sep:
                    text_at(p, sf, tok("mu"), ew + 6, base, f"· {rest}")
                text_at(p, ef, tok("tx"), w - adv(ef, value), base, value)
            y += 22 + 3
        return y + 12


class KeyFigures(Part):
    """the key figures in equal columns, no boxes: one ruled row of number and caption, or stacked cells (number,
    caption, a muted line under it) divided by 1px rules"""

    def __init__(self):
        super().__init__()
        self.items: list[tuple[str, ...]] = []

    def set(self, items: list[tuple[str, ...]]):
        """(number, caption) pairs, or (number, caption, sub) triples for stacked cells"""
        self.items = items
        self.changed()

    def draw(self, p, w):
        if not self.items:
            return 0
        if len(self.items[0]) == 3:
            return self._stacked(p, w)
        if p:
            bf, cf = font(30, 700, num=True), font(13)
            base, cw = baseline(bf, 1 + 10, 30), w / len(self.items)
            rule(p, 0, 0, w, tok("ln"))
            for k, (num, cap) in enumerate(self.items):
                nw = text_at(p, bf, tok("tx"), k * cw, base, num)
                text_at(p, cf, tok("mu"), k * cw + nw + 7, base, elide(cf, cap, max(0.0, cw - nw - 14)))
            rule(p, 0, 1 + 10 + 30 + 9, w, tok("ln"))
        return 1 + 10 + 30 + 9 + 1

    def _stacked(self, p, w):
        """a cell each: the number (40px), its caption (14px tx2), the sub-caption (12px mu); 18px (narrow 14) in from
        the rule between cells, the first flush left"""
        pad, cw = (14 if self.narrow else 18), w / len(self.items)
        bf, cf, sf = font(40, 700, num=True), font(14), font(12)
        h = 0.0
        for k, (num, cap, sub) in enumerate(self.items):
            x = k * cw + (pad if k else 0)
            iw = max(0.0, cw - pad - (pad if k else 0))
            line(p, bf, tok("tx"), x, 2, 40, num)
            y = 2 + 40 + 2 + wrapped(p, cf, tok("tx2"), x, 2 + 40 + 2, iw, 14 * 1.4, cap) + 1
            y += wrapped(p, sf, tok("mu"), x, y, iw, 12 * 1.4, sub) if sub else 0
            h = max(h, y + 4)
        if p:
            for k in range(1, len(self.items)):
                p.fillRect(QRectF(round(k * cw), 0, 1, h), tok("ln"))
        return h


class Drawer(QWidget):
    """an "All … (n)" drawer's header: a drawn chevron and its title. Click it, or Tab to it and press Space or
    Enter, to show or hide its body (laid out by the page; None: the page listens to toggled instead)"""
    toggled = pyqtSignal(bool)

    def __init__(self, title: str, body: QWidget | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.title, self.body, self.open, self.label = title, body, False, ""
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)     # the focus ring is for the keyboard, like :focus-visible
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if body is not None:
            body.hide()
        self.set_count(0)

    def set_count(self, n: int):
        s = f"{self.title} ({n})"
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
        if self.body is not None:
            self.body.setVisible(self.open)
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


class Fold(QWidget):
    """a drawer: its header between rules, pad above and below it, its body under it; the last closes with a rule
    under it all"""

    def __init__(self, drawer: Drawer, last: bool = False, pad: int = 8):
        super().__init__()
        self.last = last
        head = QHBoxLayout()
        head.setContentsMargins(0, pad, 0, pad)
        head.addWidget(drawer)
        head.addStretch(1)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 1, 0, 1 if last else 0)
        lay.setSpacing(0)
        lay.addLayout(head)
        lay.addWidget(drawer.body)

    def paintEvent(self, _ev):
        p = QPainter(self)
        rule(p, 0, 0, self.width(), tok("ln"))
        if self.last:
            rule(p, 0, self.height() - 1, self.width(), tok("ln"))


class Side(QWidget):
    """the right-hand column, ruled off from the left (stacked: under it, ruled off at its top)"""
    stacked = False

    def paintEvent(self, _ev):
        QPainter(self).fillRect(QRectF(0, 0, *((self.width(), 1) if self.stacked else (1, self.height()))), tok("ln"))


class SectionHead(Part):
    """a section's rule and label tab, with an optional preview tag beside it"""

    def __init__(self, title: str, tag: str | None = None):
        super().__init__()
        self.title, self.tag = title, tag

    def draw(self, p, w):
        if p:
            rule(p, 0, 0, w, tok("ln"))
            r = draw_label_tab(p, 0, 13, self.title)
            if self.tag:
                preview_tag(p, r.right() + 8, r.center().y(), self.tag)
        return SECTION_H


def preview_tag(p, x, mid, s):
    """the small gold-framed tag ("preview"), centred on mid"""
    f, s = font(11, 600, spacing=0.1), s.upper()
    h = 11 * 1.2 + 6
    r = QRectF(x, mid - h / 2, adv(f, s) + 14, h)
    box(p, r, tok("gold"))
    line(p, f, tok("gold"), x + 7, r.y() + 3, 11 * 1.2, s)


def draw_tag(p, x: float, mid: float, text: str, ink: QColor | None = None, edge: QColor | None = None) -> float:
    """a kind tag (Boss, Dungeon, PvP, Trash): tracked capitals, 18px tall, centred on mid (ink: its text's, default
    mu; edge: its 1px frame's, default ln); returns its width"""
    f, s = font(11, 600, num=True, spacing=0.14), text.upper()
    w = adv(f, s) + 14
    if p:
        box(p, QRectF(x, mid - 9, w, 18), edge or tok("ln"))
        line(p, f, ink or tok("mu"), x + 7, mid - 5, 11, s)
    return w
