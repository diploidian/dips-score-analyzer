"""The Profile page: who you are as a player over the last 15 days, painted from a ProfileView (see
dips_score/profile_view.py): the crest, the title's trait as the one big figure, the plate, Signature and the Hands drawer
on the left; Role mix, Where you fight and How you fight on the right, under the left when both do not fit; where your
time goes under them (timepart.py), also with too few fights for the rest; Trade (tradepart.py); every trait, then the Character sheet drawer (sheetpart.py); the finished 15-day slices in the Earlier drawer.

Sizes follow docs/design/mockups/profile.html (CSS px). The shared parts come from kit.py.
"""
from __future__ import annotations

import html
import math
import re
from dataclasses import replace

from PyQt6.QtCore import QEasingCurve, QPointF, QRectF, Qt, QVariantAnimation, pyqtSignal
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import QBoxLayout, QFrame, QHBoxLayout, QScrollArea, QVBoxLayout, QWidget

from ..live.traits import TIERS, written
from ..profile_view import NA, Crest, EarlierRow, ProfileView, Row, TraitRow
from ..trait_words import NOTE
from . import theme
from .debrief import FIGHTS_W, NARROW
from .kit import (HEAD_H, Drawer, Fold, Hero, Part, Plate, Sheet, Side, Tips, adv, baseline, box, draw_hand_circle,
                  draw_hand_note, draw_label_tab, elide, flow, font, hand_font, line, rule, text_at, wrapped)
from .sheetpart import CharacterSheet
from .theme import tok
from .timepart import TimeSection
from .tradepart import TradeSection

HERO_W = (260, 214)         # the hero's column (narrow)
LEFT_MIN = 450              # the left column's width, at least, with the right one beside it
STACK = LEFT_MIN + 28 + FIGHTS_W + 2 * 16       # the page's width both columns need
TIGHT = 400                 # a part narrower than this puts in two lines what it has in one
NO_MAX = 16777215           # Qt's QWIDGETSIZE_MAX
TITLE_PX, TITLE_SHARE, WORTH_A_LINE = (74, 44, 16), 0.14, 1.15     # the crest's title, see fit_title
NOTE_PX = 24                # the hand notes: large text, so hl-note needs 3:1
TIP_W = 360                 # a trait's hover, px
TWO_COLS = 700              # All traits in two columns from this width
ENTRANCE_MS = 1760          # the one entrance, until the note has faded in; a part's p runs 0..1 over it
COUNT_MS = GROW_MS = 700
GROW_AT, STAGGER, STAGGERED = 150, 60, 8        # bars: when the first starts, each after it, how many do
DRAW_AT, DRAW_MS = 900, 550                     # the highlighter's ring
NOTE_AT, NOTE_MS = 1360, 400                    # its note
OUT, IN_OUT = QEasingCurve.Type.OutQuart, QEasingCurve.Type.InOutCubic
GROW = QEasingCurve(QEasingCurve.Type.BezierSpline)     # DESIGN.md's cubic-bezier(.16,1,.3,1)
GROW.addCubicBezierSegment(QPointF(0.16, 1), QPointF(0.3, 1), QPointF(1, 1))


def phase(p: float, start: float, ms: float, curve=OUT) -> float:
    """how far (0..1) a step of the entrance is at progress p, when it starts at `start` ms and lasts ms"""
    return QEasingCurve(curve).valueForProgress(min(1.0, max(0.0, (p * ENTRANCE_MS - start) / ms)))


def grow(p: float, i: int) -> float:
    """how much of the page's bar i is drawn"""
    return phase(p, GROW_AT + STAGGER * min(i, STAGGERED - 1), GROW_MS, GROW)


def upper(s: str) -> str:
    return s[:1].upper() + s[1:]


def broken(words: list[str], f, w: float) -> list[str]:
    """words on as few lines as fit w"""
    lines: list[str] = []
    for word in words:
        if lines and adv(f, f"{lines[-1]} {word}") <= w:
            lines[-1] += f" {word}"
        else:
            lines.append(word)
    return lines


def fit_title(s: str, w: float) -> tuple[int, list[str]]:
    """the crest's title for a width: its px and its lines, never cut. At most TITLE_SHARE of the width, from 44 to 74 px;
    two lines, three or four when each line more makes it WORTH_A_LINE bigger. "of" and "the" stay with their word"""
    words = re.findall(r"(?:(?:of|the) )*\S+", s, re.I)
    big, floor, small = TITLE_PX
    big = int(min(big, max(floor, w * TITLE_SHARE)))
    best = None
    for most in (2, 3, 4, len(words)):
        for px in range(big, small - 1, -1):
            f = font(px, 700, num=True)
            lines = broken(words, f, w)
            if len(lines) <= most and max(adv(f, x) for x in lines) <= w:
                break
        else:
            continue
        if best is None or most <= 4 and px >= best[0] * WORTH_A_LINE ** (most - best[2]):
            best = px, lines, most
    if best:
        px, lines, _ = best
    if len(lines) == 2:         # after a comma, else evenly
        f = font(px, 700, num=True)
        ways = [(" ".join(words[:k]), " ".join(words[k:])) for k in range(1, len(words))]
        lines = list(min((x for x in ways if max(adv(f, y) for y in x) <= w),
                         key=lambda x: (x[0][-1] != ",", max(adv(f, y) for y in x)), default=lines))
    return px, lines


def figure_ink(row: Row):
    return tok("mu" if row.value == NA else row.ink)


def right_text(p, f, color, right, base, s):
    text_at(p, f, color, right - adv(f, s), base, s)


def draw_bar(p, x, y, w, row: Row, prog: float, i: int):
    """a row's 10px bar on its track"""
    p.fillRect(QRectF(x, y, w, 10), tok("track"))
    if row.bar:
        p.fillRect(QRectF(x, y, w * min(1.0, row.bar) * grow(prog, i), 10), tok(row.ink))


def draw_under(p, x, y, w, row: Row, prog: float, nf, ink: str, chip_first: bool) -> float:
    """the line under a row: its note (font nf, ink) and its chip (boxed in the row's ink) side by side, the second
    under the first when they don't fit, with the page's one highlighter mark round a marked chip; returns its height"""
    lh = nf.pixelSize() * 1.4
    note_h = wrapped(None, nf, tok(ink), x, 0, w, lh, row.note) if row.note else 0.0
    if not row.chip:
        if row.note:
            wrapped(p, nf, tok(ink), x, y, w, lh, row.note)
        return note_h
    cf = font(14 if chip_first else 13, 600, num=True)
    cw, ch = adv(cf, row.chip) + 18, cf.pixelSize() * 1.25 + 6
    pad = 10 if row.mark else 0         # room for the ring, which overhangs the chip
    nw, gap = adv(nf, row.note), 8 + pad
    note_x, note_y, cx, cy = x, y, x, y + pad
    h = ch + 2 * pad
    if row.note and nw + gap + cw <= w:
        note_x, cx = (x + cw + gap, x) if chip_first else (x, x + nw + gap)
        note_y = cy + (ch - lh) / 2
    elif row.note:
        note_y, cy = (y + h + 2, cy) if chip_first else (y, cy + note_h + 4)
        h += note_h + (2 if chip_first else 4)
    if row.mark:                        # the hand note: right of the ring, or under it all when that doesn't fit
        hf = hand_font(NOTE_PX)
        mx, my, mw = cx + cw + 14, cy + ch - 4, adv(hf, row.mark)
        if mx + mw > x + w or (note_x > cx and note_y > cy - lh):
            mx, my = max(x, min(cx + 8, x + w - mw)), y + h + 18
            h += 26
    if p:
        if row.mark:
            draw_hand_circle(p, QRectF(cx - 9, cy - 6, cw + 18, ch + 12), tok("hl"), -2,
                             phase(prog, DRAW_AT, DRAW_MS, IN_OUT))
        box(p, QRectF(cx, cy, cw, ch), tok("ln" if row.ink == "tx" else row.ink))
        line(p, cf, tok("tx"), cx + 9, cy + 3, cf.pixelSize() * 1.25, row.chip)
        if row.note:
            wrapped(p, nf, tok(ink), note_x, note_y, w - (note_x - x), lh, row.note)
        if row.mark:
            p.setOpacity(phase(prog, NOTE_AT, NOTE_MS))
            draw_hand_note(p, row.mark, QPointF(mx, my), None, NOTE_PX)
            p.setOpacity(1)
    return h


def spoken(title: str, rows: list[Row]) -> str:
    """what a screen reader says for a section"""
    return f"{title}: " + "; ".join(", ".join(filter(None, (
        f"{r.name} {written(r.value, r.unit)}", spoken_casts(r.casts), f"grade {r.grade} {r.letter}" if r.letter else "",
        r.note, r.chip, r.mark))) for r in rows)


def spoken_casts(casts: str) -> str:
    return "" if casts in ("", NA) else casts if casts.endswith("swings") else f"{casts} casts"


class ProfileHero(Hero):
    """the hero, its label in the verdict's place and who you were before under it"""

    def __init__(self):
        super().__init__()
        self.before = ""
        self.verdict_look = (14, 400, "tx2")

    def draw(self, p, w):
        y = super().draw(p, w)
        return y + 4 + wrapped(p, font(13), tok("mu"), 0, y + 4, w, 13 * 1.4, self.before) if self.before else y


class CrestBox(Part):
    """the crest: in a double gold rule (2px, then 1px) who you are, the title as big as its lines allow, the second line
    and the deeds. note: a new tier's hand note, in the second line's free end; not drawn when it doesn't fit there"""

    def __init__(self):
        super().__init__()
        self.crest, self.note = Crest("", ""), ""

    def set(self, c: Crest, note: str):
        self.crest, self.note = c, note
        self.setAccessibleName("Crest: " + ". ".join(x.rstrip(".") for x in filter(None, (
            c.who, upper(c.title), c.second, note, *map(upper, c.deeds)))))
        self.changed()

    def draw(self, p, w):
        c, x, pad = self.crest, 24 if w >= TIGHT else 16, 26
        if p:
            h = self.height()
            box(p, QRectF(0, 0, w, h), tok("gold"), tok("panel"), 2)
            box(p, QRectF(5, 5, w - 10, h - 10), tok("gold"))
        iw, y = w - 2 * x, float(pad)
        y += wrapped(p, font(15, 600), tok("tx2"), x, y, iw, 20, c.who) + 8 if c.who else 0
        px, lines = fit_title(upper(c.title), iw) if c.title else (1, [])
        f, sf, hf = font(px, 700, num=True), font(16, 500), hand_font(NOTE_PX)
        for s in lines:
            line(p, f, tok("tx"), x, y, px, s)
            y += px
        if c.second:
            y += 14
            if p and self.note and adv(sf, c.second) + 20 + adv(hf, self.note) <= iw:
                p.setOpacity(phase(self.p, NOTE_AT, NOTE_MS))
                draw_hand_note(p, self.note, QPointF(x + iw - adv(hf, self.note), y + 19), None, NOTE_PX)
                p.setOpacity(1)
            y += wrapped(p, sf, tok("tx"), x, y, iw, 16 * 1.4, c.second)
        if c.deeds:
            y += 14
            if p:
                rule(p, x, y, iw, tok("gold"))
            y += 1 + 10
            for k, d in enumerate(c.deeds):
                y += 4 if k else 0
                y += wrapped(p, font(18, 600, num=True), tok("tx2"), x, y, iw, 18 * 1.2, upper(d))
        return y + pad


class Quiet(Part):
    """one quiet line under the crest"""
    text = ""

    def draw(self, p, w):
        return 8 + wrapped(p, font(13), tok("mu"), 0, 8, w, 13 * 1.4, self.text)


class Need(Part):
    """under 10 fights: what the profile needs, in the page's place"""
    head = text = ""

    def draw(self, p, w):
        hf, tf = font(23, 600, num=True), font(14)
        y = 18.0
        y += wrapped(p, hf, tok("tx"), 0, y, min(w, 30 * adv(hf, "0")), 23 * 1.2, self.head) + 8
        return y + wrapped(p, tf, tok("tx2"), 0, y, min(w, 62 * adv(tf, "0")), 14 * 1.4, self.text) + 18


class Signature(Part):
    """Signature: your top spells (name, casts, a bar as long as its share, the share), and your usual opening"""

    def __init__(self):
        super().__init__()
        self.view = ProfileView()

    def set_view(self, v: ProfileView):
        self.view = v
        self.setAccessibleName(spoken("Signature", v.signature))
        self.changed()

    def draw(self, p, w):
        v = self.view
        if p:
            rule(p, 0, 0, w, tok("ln"))
        draw_label_tab(p, 0, 1 + 14, "Signature")
        y = 1 + 14 + 25 + 8
        tight = w < TIGHT               # the name and the share, then the bar and the casts under them
        name_w, cast_w, share_w = (172, 82, 40) if self.narrow else (170, 92, 44)
        nf = font(14, 500)      # the names get the room they need, down to a 100px bar
        longest = math.ceil(max((adv(nf, r.name) for r in v.signature), default=0)) + 1
        name_w = max(name_w, min(longest, w - 3 * 12 - cast_w - share_w - 100))
        cast_r = name_w + 12 + cast_w
        bx = cast_r + 12
        bw = max(0.0, w - bx - 12 - share_w)
        if tight:
            name_w, cast_r, bx, bw = w - share_w - 12, w, 0, w - cast_w - 12
        hf = font(11, 600, num=True, spacing=0.12)
        if p:
            right_text(p, hf, tok("mu"), cast_r, baseline(hf, y, 12), "CASTS")
            line(p, hf, tok("mu"), bx, y, 12, elide(hf, v.sig_header.upper(), w - bx - (60 if tight else 0)))
        y += 12 + 4
        cf, vf, tf = font(14, num=True), font(20, 700, num=True), font(12)
        for k, row in enumerate(v.signature):
            if p:
                rule(p, 0, y, w, tok("ln"))
                base = baseline(nf, y + 6, 20)
                text_at(p, nf, tok("tx"), 0, base, elide(nf, row.name, name_w))
                low = 22 if tight else 0
                right_text(p, cf, tok("mu" if row.casts == NA else "tx"), cast_r, base + low, row.casts)
                draw_bar(p, bx, y + 11 + low, bw, row, self.p, k)
                right_text(p, vf, figure_ink(row), w, baseline(vf, y + 6, 20), row.value + row.unit)
            y += 1 + 5 + 20 + (22 if tight else 0)
            if row.note:
                y += wrapped(p, tf, tok("mu"), bx, y, w - bx, 12 * 1.4, row.note)
            y += 5
        y += 10
        if p:
            rule(p, 0, y, w, tok("tx"))
        y += 1 + 8
        of, ink = font(17, 600, num=True), tok("mu" if v.opener == NA else "tx")
        if max(adv(of, v.opener), adv(tf, v.opener_note)) > w:
            y += wrapped(p, of, ink, 0, y, w, 21, v.opener) + 2
            return y + wrapped(p, tf, tok("mu"), 0, y, w, 12 * 1.4, v.opener_note) + 10
        return y + flow(p, [(v.opener, of, ink), (v.opener_note, tf, tok("mu"))], 0, y, w, 14, 2) + 10


class SpellTable(Part):
    """the All spells drawer's table: every spell, its casts and its share, closed by a total of 100%"""

    def __init__(self):
        super().__init__()
        self.rows, self.header, self.total = [], "", ""

    def set_view(self, v: ProfileView):
        self.rows, self.header = v.spells, v.spells_header
        self.total = v.spells_header.replace("share of ", "All your ")
        self.setAccessibleName("All spells: " + "; ".join(
            ", ".join(filter(None, (name, spoken_casts(casts), share))) for name, casts, share in v.spells))
        self.changed()

    def draw(self, p, w):
        hf, f, bf = font(11, 600, num=True, spacing=0.12), font(14, 500), font(14)
        tight = w < TIGHT           # the casts under the share
        cast_r = w if tight else w - 170
        name_w = w - 104 if tight else cast_r - 94
        y = 0.0
        if p:
            line(p, hf, tok("mu"), 0, y, 12, "SPELL")
            if not tight:
                right_text(p, hf, tok("mu"), cast_r, baseline(hf, y, 12), "CASTS")
            right_text(p, hf, tok("mu"), w, baseline(hf, y, 12), self.header.upper())
        y += 12 + 6
        for name, casts, share in self.rows:
            if p:
                rule(p, 0, y, w, tok("ln"))
                base = baseline(f, y + 5, 19.6)
                right_text(p, bf, tok("mu" if share == NA else "tx"), w, base, share)
                if tight:
                    right_text(p, font(12), tok("mu"), w, base + 18, spoken_casts(casts))
                else:
                    right_text(p, bf, tok("mu" if casts == NA else "tx"), cast_r, base, casts)
            h = wrapped(p, f, tok("tx"), 0, y + 5, name_w, 19.6, name)
            y += 1 + 4 + (max(h, 19.6 + 18) if tight and casts != NA else h) + 4
        if any(share != NA for _, _, share in self.rows):
            if p:
                rule(p, 0, y, w, tok("tx"), 2)
                tf = font(14, 600)
                base = baseline(tf, y + 6, 19.6)
                text_at(p, tf, tok("tx"), 0, base, self.total)
                right_text(p, tf, tok("tx"), w, base, "100%")
            y += 2 + 4 + 19.6 + 4
        return y + 10


class ShareRows(Part):
    """Role mix or Where you fight: a ruled row each, name, a bar as long as its share, the share (and the average
    grade of its runs), then its note and chip. first: the number of its first bar in the entrance's order"""

    def __init__(self, title: str, first: int, graded: bool = False):
        super().__init__()
        self.title, self.first, self.graded = title, first, graded
        self.rows: list[Row] = []

    def set(self, rows: list[Row]):
        self.rows = rows
        self.setAccessibleName(spoken(self.title, rows))
        self.changed()

    def draw(self, p, w):
        draw_label_tab(p, 0, 14, self.title)
        y = 14 + 25 + 8
        tight = w < TIGHT           # the bar on a line of its own
        bx, right = 0 if tight else 122, w - (58 + 12 if self.graded else 0)
        bar_w = w if tight else right - 46 - 12 - bx
        nf, vf, gf, lf = font(14, 500), font(22, 700, num=True), font(20, 700, num=True), font(13, 700, num=True)
        for k, row in enumerate(self.rows):
            if k:
                if p:
                    rule(p, 0, y, w, tok("ln"))
                y += 1
            y += 5
            if p:
                line(p, nf, tok("tx"), 0, y, 22, row.name)
                draw_bar(p, bx, y + (28 if tight else 6), bar_w, row, self.p, self.first + k)
                base = baseline(vf, y, 22)
                right_text(p, vf, figure_ink(row), right, base, row.value + row.unit)
                if self.graded:
                    ink = theme.grade_color(row.letter) if row.letter else tok("mu")
                    lw = adv(lf, row.letter) + 3 if row.letter else 0
                    text_at(p, lf, ink, w - lw + 3, base, row.letter)
                    right_text(p, gf, ink, w - lw, base, row.grade)
            y += 22 + 18 if tight else 22
            ux = 12 if tight and row.mark else bx         # the ring overhangs its chip
            h = draw_under(p, ux, y + 4, w - ux, row, self.p, font(12), "mu", True)
            y += (4 + h if h else 0) + 5
        if p:
            rule(p, 0, y + 12, w, tok("ln"))
        return y + 12 + 1


class TraitCard(Part):
    """How you fight: a framed card like the Habits ones, its 8px square and name, then a ruled list of figures, each
    over its note and chip. A marked row's ring goes round its figure (ring: where it was last drawn, figure: what it
    goes round); marks False draws none"""

    def __init__(self, name: str, square: str):
        super().__init__()
        self.name, self.square = name, square
        self.rows: list[Row] = []
        self.marks = True
        self.ring = self.figure = QRectF()

    def set(self, rows: list[Row]):
        self.rows = rows
        self.setAccessibleName(spoken(self.name, rows))
        self.changed()

    def draw(self, p, w):
        if p:
            box(p, QRectF(0, 0, w, self.height()), tok("ln"), tok("panel"))
            p.save()
            p.translate(17, 13)
        w -= 2 * 17
        if p:
            p.fillRect(QRectF(0, 2, 8, 8), tok(self.square))
            line(p, font(12, 700, num=True, spacing=0.14), tok("tx"), 16, 0, 12, self.name.upper())
        y = 12 + 8.0
        nf, vf, uf = font(15, 500), font(26, 700, num=True), font(17, 600, num=True)
        for row in self.rows:
            if p:
                rule(p, 0, y, w, tok("ln"))
            big = row.value + "%" * row.unit.startswith("%")
            unit = written(row.value, row.unit)[len(big):]
            bw, note_w = adv(vf, big), adv(hand_font(NOTE_PX), row.mark or "")
            uw = adv(uf, unit) + 1 if unit else 0
            low = uw >= 20 and adv(nf, row.name) + 16 + uw + bw > w      # words that don't fit go under the figure
            uw, unit_w = (0, uw) if low else (uw, uw)
            ring = row.mark and self.marks
            y += 1 + 7
            base, name_w = baseline(vf, y, 26), adv(nf, row.name)
            room = w - uw - bw - 16
            name_h = wrapped(p, nf, tok("tx"), 0, base - baseline(nf, 0, 20), room, 20, row.name) if name_w > room else 0
            if p and not name_h:
                text_at(p, nf, tok("tx"), 0, base, row.name)
            mx = w - uw - bw - 26 - note_w      # the note, left of the ring, or on a line under it
            beside = not name_h and mx >= name_w + 12
            if p and ring:
                inw = bw + (uw if uw < 20 else 0)       # with a short unit ("s")
                self.figure = QRectF(w - uw - bw, base - 20, inw, 22)
                self.ring = QRectF(w - uw - bw - 12, base - 28, inw + 24, 38)
                draw_hand_circle(p, self.ring, tok("hl"), -2, phase(self.p, DRAW_AT, DRAW_MS, IN_OUT))
                p.setOpacity(phase(self.p, NOTE_AT, NOTE_MS))
                at = QPointF(mx, base) if beside else QPointF(max(0.0, w - note_w), base + max(34, name_h + 20))
                draw_hand_note(p, row.mark, at, None, NOTE_PX)
                p.setOpacity(1)
            if p:
                text_at(p, uf, tok("tx2"), w - unit_w, base + (20 if low else 0), unit)       # quiet, as the hero's
                right_text(p, vf, figure_ink(row), w - uw, base, big)
            y += max(26 + 2 + (22 if low else 0), base - y + name_h - 14) + (36 if ring and not beside else 0)
            y += 5 if row.chip and not row.note else 0              # the chip 8px under the name
            y += draw_under(p, 0, y, w, replace(row, mark=None), self.p, font(13), "tx2", False) + 8
        if p:
            p.restore()
        return y + 13 + 5


class TraitTable(Tips):
    """the All traits drawer: a note on how to read it, then by family, in two columns when wide, a ruled row each, the
    name, its tier in a gold frame, the figure, the score's bar with a tick where each tier begins and the figures it
    begins and ends at under it, and what it is over the bar. How it is worked out is in the hover. new: the trait whose tier is new, its tier ringed (ring, tier: where the two were last drawn)"""

    def __init__(self):
        super().__init__()
        self.families: list[tuple[str, list[TraitRow]]] = []
        self.new: str | None = None
        self.ring = self.tier = QRectF()
        self.setCursor(Qt.CursorShape.WhatsThisCursor)

    def set(self, families: list[tuple[str, list[TraitRow]]], new: str | None):
        self.families, self.new = families, new
        self.setAccessibleName("All traits: " + NOTE + " " + " ".join(f"{fam}: " + "; ".join(", ".join(filter(None, (
            f"{r.name} {written(r.value, r.unit)}", r.tier and f"new: {r.tier}" if r.key == new else r.tier, r.line,
            r.ends[0] and f"bar from {r.ends[0]} to {r.ends[1]}", r.tip.replace("\n", " ").rstrip("."))))
            for r in rows) + "." for fam, rows in families))
        self.changed()

    def columns(self, w) -> list[list[tuple[str, list[TraitRow]]]]:
        """the families in one column, or in two about as high as each other"""
        fams = self.families
        if w < TWO_COLS or len(fams) < 2:
            return [fams]
        cw = (w - 56) / 2
        tall = [self.family(None, 0, 0, cw, *f) + 14 for f in fams]
        k = min(range(1, len(fams)), key=lambda k: max(sum(tall[:k]), sum(tall[k:])))
        return [fams[:k], fams[k:]]

    def draw(self, p, w):
        cols = self.columns(w)
        cw = (w - 56) / 2 if len(cols) == 2 else w
        if p:
            self.tips = []
        top = 2.0 + wrapped(p, font(12), tok("tx2"), 0, 2, w, 12 * 1.4, NOTE) + 12
        h = 0.0
        for k, fams in enumerate(cols):
            y = top
            for j, fam in enumerate(fams):
                y += 14 if j else 0
                y += self.family(p, k * (cw + 56), y, cw, *fam)
            h = max(h, y)
        if p and len(cols) == 2:
            p.fillRect(QRectF(round(cw + 28), top, 1, h - top), tok("ln"))
        return h + 12

    def family(self, p, x, y0, w, fam, rows) -> float:
        hf, nf, vf, tf, sf = (font(11, 600, num=True, spacing=0.12), font(14, 500), font(20, 700, num=True), font(12, 500),
                              font(12))
        ef = font(11)
        y = y0
        if p:
            line(p, hf, tok("mu"), x, y, 12, fam.upper())
        y += 12 + 5
        for row in rows:
            if p:
                rule(p, x, y, w, tok("ln"))
            new, y1 = row.key == self.new and bool(row.tier), y
            y += 1 + (10 if new else 5)
            value = written(row.value, row.unit)
            room, name_w, tag_w = w - adv(vf, value) - 12, adv(nf, row.name), adv(tf, row.tier) + 14
            pad = 12 if new else 0          # the ring overhangs its tier
            if p:
                right_text(p, vf, tok(row.ink), x + w, baseline(vf, y, 20), value)
            name_h = wrapped(p, nf, tok("tx"), x, y, room, 20, row.name)
            if row.tier:
                inline = name_w + 10 + 2 * pad + tag_w <= room
                tx, top = (x + name_w + 10 + pad, y) if inline else (x + pad, y + name_h + 2 + pad / 2)
                if p:
                    tier = QRectF(tx, top + 1, tag_w, 19)
                    if new:
                        self.tier, self.ring = tier, tier.adjusted(-10, -6, 10, 6)
                        draw_hand_circle(p, self.ring, tok("hl"), -2, phase(self.p, DRAW_AT, DRAW_MS, IN_OUT))
                        if tx + tag_w + 14 + adv(hand_font(NOTE_PX), "new") <= x + (room if inline else w):
                            p.setOpacity(phase(self.p, NOTE_AT, NOTE_MS))
                            draw_hand_note(p, "new", QPointF(tx + tag_w + 14, top + 18), None, NOTE_PX)
                            p.setOpacity(1)
                    box(p, tier, tok("gold"))
                    line(p, tf, tok("tx2"), tx + 7, top + 1, 19, row.tier)
                name_h = max(name_h, top + 20 - y)
            y += name_h + (10 if new else 1)
            y += wrapped(p, sf, tok("tx2"), x, y, w, 12 * 1.4, row.line) + 5
            if p:
                top, fill = round(y), w * row.bar
                p.fillRect(QRectF(x, top, w, 6), tok("track"))
                p.fillRect(QRectF(x, top, fill, 6), tok(row.ink))
                for t in (round(w * t) for t in TIERS):     # in the fill, or standing over the track
                    p.fillRect(QRectF(x + t, top, 1, 6) if t < fill else QRectF(x + t, top - 2, 1, 10),
                               tok("panel" if t < fill else "tx"))
            y += 6 + 5
            if p:       # alone on their line: beside the words the first end reads as your figure
                line(p, ef, tok("mu"), x, y - 2, 14, row.ends[0])
                right_text(p, ef, tok("mu"), x + w, baseline(ef, y - 2, 14), row.ends[1])
            y += 14 + 4
            if p and row.tip:       # rich text: long lines wrap
                self.tips.append((QRectF(x, y1, w, y - y1), "<table width=%d><tr><td>" % TIP_W + "".join(
                    f"<p style='margin: 0 0 6px 0'>{html.escape(x)}</p>" for x in row.tip.split("\n")) + "</td></tr></table>"))
        return y - y0


class HandsList(Part):
    """the Hands drawer: the player's hands, not the character's play, so plain rows: no ink, no chip, no mark"""

    def __init__(self):
        super().__init__()
        self.rows: list[Row] = []

    def set(self, rows: list[Row]):
        self.rows = rows
        self.setAccessibleName(spoken("Hands", rows))
        self.changed()

    def draw(self, p, w):
        nf, vf, tf, y = font(14), font(16, 600, num=True), font(12), 0.0
        for row in self.rows:
            if p:
                rule(p, 0, y, w, tok("ln"))
                base = baseline(nf, y + 6, 20)
                text_at(p, nf, tok("tx2"), 0, base, row.name)
                right_text(p, vf, tok("mu" if row.value == NA else "tx2"), w, base, written(row.value, row.unit))
            y += 1 + 5 + 20
            y += wrapped(p, tf, tok("mu"), 0, y, w, 12 * 1.4, row.note) + 6
        return y + 6


class EarlierTable(Part):
    """the Earlier drawer's rows, newest first: the dates, who you were, the main role, deaths an hour, cooldowns"""

    def __init__(self):
        super().__init__()
        self.rows: list[EarlierRow] = []

    def set(self, rows: list[EarlierRow]):
        self.rows = rows
        self.setAccessibleName("Earlier: " + "; ".join(
            f"{r.dates}, {r.label}, {r.role}, {r.deaths} deaths an hour, {r.cooldowns} cooldowns used, {r.stats}" for r in rows))
        self.changed()

    def stacked(self, p, w) -> float:
        """too narrow for the columns: each row's dates, title and figures under each other"""
        df, lf, vf, y = font(16, 600, num=True), font(14), font(16, 700, num=True), 0.0
        for row in self.rows:
            if p:
                rule(p, 0, y, w, tok("ln"))
                line(p, df, tok("tx"), 0, y + 7, 20, row.dates)
            y += 1 + 6 + 20
            y += wrapped(p, lf, tok("tx2"), 0, y, w, 20, upper(row.label)) + 2
            role, _, share = row.role.rpartition(" ")
            for value, what in ((share, role or "main role"), (row.deaths, "deaths an hour"), (row.cooldowns, "cooldowns used")):
                if p:
                    base = baseline(vf, y, 20)
                    text_at(p, vf, tok("mu" if value == NA else "tx"), 0, base, value)
                    text_at(p, lf, tok("tx2"), 48, base, what)
                y += 20
            y += wrapped(p, font(12), tok("tx2"), 0, y + 2, w, 12 * 1.4, row.stats) + 2 + 6
        return y + 10

    def draw(self, p, w):
        if w < 560:
            return self.stacked(p, w)
        first, *rest = (140, 120, 96, 96) if self.narrow else (150, 130, 110, 110)
        rights = [w - sum(rest[k + 1:]) - 14 * (2 - k) for k in range(3)]
        lx = first + 14
        hf, df, lf, vf, sf = (font(11, 600, num=True, spacing=0.12), font(16, 600, num=True), font(14),
                              font(18, 700, num=True), font(14, 500))
        if p:
            line(p, hf, tok("mu"), 0, 0, 12, "15 DAYS")
            line(p, hf, tok("mu"), lx, 0, 12, "WHO YOU WERE")
            for s, right in zip(("MAIN ROLE", "DEATHS / HOUR", "COOLDOWNS USED"), rights):
                right_text(p, hf, tok("mu"), right, baseline(hf, 0, 12), s)
        y = 12 + 6.0
        for row in self.rows:
            if p:
                rule(p, 0, y, w, tok("ln"))
                base = baseline(vf, y + 7, 20)
                text_at(p, df, tok("tx"), 0, base, row.dates)
                text_at(p, lf, tok("tx2"), lx, base, elide(lf, upper(row.label), rights[0] - rest[0] - 14 - lx))
                name, _, share = row.role.rpartition(" ")
                right_text(p, vf, tok("mu" if share == NA else "tx"), rights[0], base, share)
                right_text(p, sf, tok("tx2"), rights[0] - adv(vf, share) - 5, base, name)
                for s, right in zip((row.deaths, row.cooldowns), rights[1:]):
                    right_text(p, vf, tok("mu" if s == NA else "tx"), right, base, s)
            y += 1 + 6 + 20
            y += wrapped(p, font(12), tok("tx2"), lx, y + 2, w - lx, 12 * 1.4, row.stats) + 2 + 6
        return y + 10


class Foot(Fold):
    """the page's foot: the Earlier drawer under a strong rule"""

    def paintEvent(self, _ev):
        rule(QPainter(self), 0, 0, self.width(), tok("tx"))


class ProfilePage(QScrollArea):
    """the Profile page, scrolling when the window is small (never sideways, see _fit): the crest, the hero and the plate,
    Signature and Hands on the left, the shares and How you fight on the right, All traits under both, Earlier at the
    foot. The page's one ring: a new tier's chip in All traits while that is open, else its How you fight figure"""
    open_habits = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.fit = self.narrow = None
        self.thin = False
        self.view = ProfileView()
        self.traits_picked = False      # you opened or shut All traits yourself: it stays as you left it
        self.settings: dict = {}        # the app's (shared), for "motion"
        self.entrance = QVariantAnimation(self, startValue=0.0, endValue=1.0, duration=ENTRANCE_MS)
        self.entrance.valueChanged.connect(self.set_progress)
        self.page = Sheet()
        self.hero, self.plate = ProfileHero(), Plate("Worth changing")
        self.plate.price_px, self.plate.body_last, self.plate.price_words = 34, True, True
        self.plate.clicked.connect(self.open_habits)
        self.crest, self.outdated = CrestBox(), Quiet()
        self.need, self.signature, self.table = Need(), Signature(), SpellTable()
        self.spells_drawer = Drawer("All spells", self.table)
        self.card = TraitCard("How you fight", "tx2")
        self.hands = HandsList()
        self.hands_drawer = Drawer("Hands", self.hands)
        self.roles = ShareRows("Role mix", 5, graded=True)
        self.places = ShareRows("Where you fight", 7)
        self.time = TimeSection()
        self.time.grow = grow
        self.trade = TradeSection()
        self.trade_drawer = Drawer("Trade", self.trade)
        self.trade_drawer.set_count(None)
        self.trade_fold = Fold(self.trade_drawer)
        self.traits = TraitTable()
        self.traits_drawer = Drawer("All traits", self.traits)
        self.traits_fold, self.hands_fold = Fold(self.traits_drawer), Fold(self.hands_drawer)
        self.traits_drawer.toggled.connect(self._traits_toggled)
        self.sheet = CharacterSheet()
        self.sheet_drawer = Drawer("Character sheet", self.sheet)
        self.sheet_drawer.set_count(None)
        self.sheet_fold = Fold(self.sheet_drawer)
        self.earlier = EarlierTable()
        self.earlier_drawer = Drawer("Earlier", self.earlier)
        self.foot = Foot(self.earlier_drawer)

        self.hero_row = QHBoxLayout()
        self.hero_row.setContentsMargins(0, 14, 0, 18)
        self.hero_row.addWidget(self.hero, 0, Qt.AlignmentFlag.AlignTop)
        self.hero_row.addWidget(self.plate, 1, Qt.AlignmentFlag.AlignTop)
        self.left = left = QVBoxLayout()
        left.setSpacing(0)
        left.addSpacing(14)
        left.addWidget(self.crest)
        left.addWidget(self.outdated)
        left.addLayout(self.hero_row)
        left.addWidget(self.signature)
        left.addWidget(Fold(self.spells_drawer))
        left.addWidget(self.hands_fold)
        left.addStretch(1)
        self.side = Side()
        self.right = right = QVBoxLayout(self.side)
        right.setSpacing(0)
        right.addWidget(self.roles)
        right.addWidget(self.places)
        right.addSpacing(16)
        right.addWidget(self.card)
        right.addStretch(1)
        self.body = QWidget()
        self.stack = stack = QVBoxLayout(self.body)
        stack.setContentsMargins(0, 0, 0, 0)
        stack.setSpacing(0)
        self.cols = cols = QHBoxLayout()
        cols.setSpacing(0)
        cols.addLayout(left, 1)
        cols.addWidget(self.side)
        stack.addLayout(cols, 1)
        stack.addWidget(self.time)
        stack.addWidget(self.trade_fold)
        stack.addWidget(self.traits_fold)
        stack.addWidget(self.sheet_fold)
        self.lay = lay = QVBoxLayout(self.page)
        lay.setContentsMargins(16, 4, 16, 16)
        lay.setSpacing(0)
        lay.addSpacing(HEAD_H)
        lay.addWidget(self.need)
        lay.addWidget(self.body, 1)     # the divider runs down to Earlier, at the window's foot
        lay.addWidget(self.foot)
        lay.addStretch(0)
        self.setWidget(self.page)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._fit()
        self.show_view(ProfileView())

    def show_view(self, v: ProfileView):
        self.view = v
        self.page.title, self.page.sub = v.title, v.meta
        thin = v.need is not None
        if thin and not self.thin and not self.earlier_drawer.open:     # all there is to see: open
            self.earlier_drawer.flip()
        self.thin = thin
        self.need.setVisible(thin)
        self.body.setVisible(not thin)
        if thin:        # its hours are days', not fights'
            self.stack.removeWidget(self.time)
            self.lay.insertWidget(self.lay.indexOf(self.need) + 1, self.time)
        else:
            self.lay.removeWidget(self.time)
            self.stack.removeWidget(self.time)
            self.stack.insertWidget(self.stack.indexOf(self.trade_fold), self.time)
        self.time.setVisible(not (thin and v.time.need))        # one thing to wait for is enough
        self.time.set(v.time)
        self.trade.set(v.trade)
        self.need.head, self.need.text = v.need or "", v.need_line
        self.need.setAccessibleName(f"{self.need.head} {self.need.text}")
        self.need.changed()
        self.crest.setVisible(v.crest is not None)
        self.outdated.text = v.outdated
        self.outdated.setAccessibleName(v.outdated)
        self.outdated.setVisible(bool(v.outdated))
        self.outdated.changed()
        self.hero.before, self.hero.chip_ink, self.hero.ink = v.before or "", v.chip_ink, v.hero_ink
        self.hero.set(v.hero, v.hero_unit or None, v.caption, v.chip, v.label or "")
        self.hero.setAccessibleName(", ".join(filter(None, (f"{written(v.hero, v.hero_unit)} {v.caption}", v.chip, v.label,
                                                            v.before))))
        self.plate.setVisible(v.plate is not None)
        if v.plate:
            self.plate.label = v.plate.tab
            self.plate.set(v.plate.title, v.plate.figure, v.plate.caption, v.plate.button, v.plate.next, v.plate.why)
            self.plate.setAccessibleName(f"{v.plate.tab}: " + ". ".join(filter(None, (
                v.plate.title, v.plate.figure, v.plate.caption, v.plate.why.rstrip("."),
                v.plate.next and "Next: " + ", ".join(f"{n} {d}" for n, d in v.plate.next)))))
        self.signature.set_view(v)
        self.table.set_view(v)
        self.spells_drawer.set_count(len(v.spells))
        self.card.set(v.card)
        self.card.setVisible(bool(v.card))
        self.hands.set(v.hands)
        self.hands_drawer.set_count(len(v.hands))
        self.hands_fold.setVisible(bool(v.hands))
        self.roles.set(v.roles)
        self.places.set(v.places)
        self.traits_drawer.set_count(sum(len(rows) for _, rows in v.traits))
        self.traits_fold.setVisible(bool(v.traits))
        self.sheet.set(v.sheet)
        self._ring()
        self._fit(True)
        self.earlier.set(v.earlier)
        self.earlier_drawer.set_count(len(v.earlier))
        self.foot.setVisible(bool(v.earlier))
        self.page.update()

    def _ring(self):
        """where a new tier shows: its chip while All traits is open, else its figure in How you fight, else the crest's
        second line has the note"""
        v, shown = self.view, self.traits_drawer.open
        self.card.marks = not (v.ring and shown)
        self.card.update()
        self.traits.set(v.traits, v.ring_key if shown else None)
        if v.crest:
            self.crest.set(v.crest, v.ring or "" if v.ring and not shown and not any(r.mark for r in v.card) else "")

    def _traits_toggled(self, _open: bool):
        self.traits_picked = True
        self._ring()

    def enter(self):
        """the entrance, once a visit to the page; settled with motion off"""
        self.entrance.stop()
        motion = bool(self.settings.get("motion", True))
        self.set_progress(0.0 if motion else 1.0)
        if motion:
            self.entrance.start()

    def set_progress(self, p: float):
        """the entrance's p (1: settled) to the parts that animate"""
        self.hero.p = 0.78 * phase(p, 0, COUNT_MS)      # kit's ticker lands at 0.78
        for part, moves in ((self.hero, True), (self.signature, True), (self.card, True), (self.roles, True),
                            (self.places, True), (self.time, True), (self.crest, bool(self.crest.note)), (self.traits, bool(self.traits.new))):
            if part is not self.hero:
                part.p = p
            if moves:
                part.update()

    def resizeEvent(self, ev):
        self._fit()
        super().resizeEvent(ev)

    def _fit(self, force: bool = False):
        """the mock-up's narrow hero and columns below a 1420px window; in a page too narrow for both columns the right
        one goes under the left and All traits shuts, then the plate goes under the hero"""
        narrow = self.window().width() < NARROW
        wide = self.width() - self.verticalScrollBar().sizeHint().width()
        stacked, tight = wide < STACK, wide - 2 * 16 < LEFT_MIN
        if (narrow, stacked, tight) == self.fit and not force:
            return
        self.fit, self.narrow = (narrow, stacked, tight), narrow
        if not self.traits_picked and self.traits_drawer.open == stacked:
            self.traits_drawer.flip()
            self.traits_picked = False
        hero_w = HERO_W[int(narrow)]
        free = tight or self.view.plate is None
        self.hero.setMinimumWidth(0 if free else hero_w)
        self.hero.setMaximumWidth(NO_MAX if free else hero_w)
        down, across = QBoxLayout.Direction.TopToBottom, QBoxLayout.Direction.LeftToRight
        self.hero_row.setDirection(down if tight else across)
        self.hero_row.setSpacing(22 if narrow else 28)
        self.cols.setDirection(down if stacked else across)
        self.left.setContentsMargins(0, 0, 0 if stacked else 28, 16)
        self.right.setContentsMargins(0 if stacked else 28, 4, 0, 16)
        self.side.stacked = stacked
        self.side.setMinimumWidth(0 if stacked else FIGHTS_W)
        self.side.setMaximumWidth(NO_MAX if stacked else FIGHTS_W)
        for part in (self.hero, self.plate, self.signature, self.earlier):
            part.narrow = narrow
            part.changed()
