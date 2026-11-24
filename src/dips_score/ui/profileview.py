"""The Profile page: who you are as a player over the last 15 days, painted from a ProfileView (see
dips_score/profile_view.py): your main role's share of the fight time and the label, the plate, Signature and Hands
on the left; Role mix, Where you fight and Temperament on the right; the finished 15-day slices in the Earlier drawer.

Sizes follow docs/design/mockups/profile.html (CSS px). The shared parts come from kit.py.
"""
from __future__ import annotations

from PyQt6.QtCore import QEasingCurve, QPointF, QRectF, Qt, QVariantAnimation, pyqtSignal
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QScrollArea, QVBoxLayout, QWidget

from ..profile_view import NA, EarlierRow, ProfileView, Row
from . import theme
from .debrief import FIGHTS_W, NARROW
from .kit import (HEAD_H, Drawer, Fold, Hero, Part, Plate, Sheet, Side, adv, baseline, box, draw_hand_circle,
                  draw_hand_note, draw_label_tab, elide, flow, font, hand_font, line, rule, text_at, wrapped)
from .theme import tok

HERO_W = (260, 214)         # the hero's column (narrow)
LEFT_MIN = 450              # the left column never gets narrower (the page scrolls sideways instead)
ENTRANCE_MS = 1760          # the one entrance, until the note has faded in; a part's p runs 0..1 over it
COUNT_MS = GROW_MS = 700
GROW_AT, STAGGER, STAGGERED = 150, 60, 8        # bars: when the first starts, each after it, how many do
DRAW_AT, DRAW_MS = 900, 550                     # the highlighter's ring
NOTE_AT, NOTE_MS = 1360, 400                    # its note
OUT, IN_OUT = QEasingCurve.Type.OutQuart, QEasingCurve.Type.InOutCubic


def phase(p: float, start: float, ms: float, curve=OUT) -> float:
    """how far (0..1) a step of the entrance is at progress p, when it starts at `start` ms and lasts ms"""
    return QEasingCurve(curve).valueForProgress(min(1.0, max(0.0, (p * ENTRANCE_MS - start) / ms)))


def grow(p: float, i: int) -> float:
    """how much of the page's bar i is drawn"""
    return phase(p, GROW_AT + STAGGER * min(i, STAGGERED - 1), GROW_MS)


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
        hf = hand_font(23)
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
            draw_hand_note(p, row.mark, QPointF(mx, my), None, 23)
            p.setOpacity(1)
    return h


def spoken(title: str, rows: list[Row]) -> str:
    return f"{title}: " + ", ".join(f"{r.name} {r.value}{r.unit}" for r in rows)


class ProfileHero(Hero):
    """the hero, its label in the verdict's place and who you were before under it"""

    def __init__(self):
        super().__init__()
        self.before = ""
        self.verdict_look = (17, 600, "tx")

    def draw(self, p, w):
        y = super().draw(p, w)
        return y + 4 + wrapped(p, font(14), tok("tx2"), 0, y + 4, w, 14 * 1.4, self.before) if self.before else y


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
        name_w, cast_w, share_w = (172, 82, 40) if self.narrow else (170, 92, 44)
        cast_r = name_w + 12 + cast_w
        bx = cast_r + 12
        bw = max(0.0, w - bx - 12 - share_w)
        hf = font(11, 600, num=True, spacing=0.12)
        if p:
            right_text(p, hf, tok("mu"), cast_r, baseline(hf, y, 12), "CASTS")
            line(p, hf, tok("mu"), bx, y, 12, elide(hf, v.sig_header.upper(), w - bx))
        y += 12 + 4
        nf, cf, vf, tf = font(14, 500), font(14, num=True), font(20, 700, num=True), font(12)
        for k, row in enumerate(v.signature):
            if p:
                rule(p, 0, y, w, tok("ln"))
                base = baseline(nf, y + 6, 20)
                text_at(p, nf, tok("tx"), 0, base, elide(nf, row.name, name_w))
                right_text(p, cf, tok("mu" if row.casts == NA else "tx"), cast_r, base, row.casts)
                draw_bar(p, bx, y + 11, bw, row, self.p, k)
                right_text(p, vf, figure_ink(row), w, baseline(vf, y + 6, 20), row.value + row.unit)
            y += 1 + 5 + 20
            if row.note:
                y += wrapped(p, tf, tok("mu"), bx, y, w - bx, 12 * 1.4, row.note)
            y += 5
        y += 10
        if p:
            rule(p, 0, y, w, tok("tx"))
        y += 1 + 8
        return y + flow(p, [(v.opener, font(17, 600, num=True), tok("mu" if v.opener == NA else "tx")),
                            (v.opener_note, tf, tok("mu"))], 0, y, w, 14, 2) + 10


class SpellTable(Part):
    """the All spells drawer's table: every spell, its casts and its share, closed by a total of 100%"""

    def __init__(self):
        super().__init__()
        self.rows, self.header, self.total = [], "", ""

    def set_view(self, v: ProfileView):
        self.rows, self.header = v.spells, v.spells_header
        self.total = v.spells_header.replace("share of ", "All your ")
        self.changed()

    def draw(self, p, w):
        hf, f, bf = font(11, 600, num=True, spacing=0.12), font(14, 500), font(14)
        cast_r = w - 170
        y = 0.0
        if p:
            line(p, hf, tok("mu"), 0, y, 12, "SPELL")
            right_text(p, hf, tok("mu"), cast_r, baseline(hf, y, 12), "CASTS")
            right_text(p, hf, tok("mu"), w, baseline(hf, y, 12), self.header.upper())
        y += 12 + 6
        for name, casts, share in self.rows:
            if p:
                rule(p, 0, y, w, tok("ln"))
                base = baseline(f, y + 5, 19.6)
                text_at(p, f, tok("tx"), 0, base, elide(f, name, cast_r - 100))
                for s, right in ((casts, cast_r), (share, w)):
                    right_text(p, bf, tok("mu" if s == NA else "tx"), right, base, s)
            y += 1 + 4 + 19.6 + 4
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

    def __init__(self, title: str, first: int, top_rule: bool, graded: bool = False):
        super().__init__()
        self.title, self.first, self.top_rule, self.graded = title, first, top_rule, graded
        self.rows: list[Row] = []

    def set(self, rows: list[Row]):
        self.rows = rows
        self.setAccessibleName(spoken(self.title, rows))
        self.changed()

    def draw(self, p, w):
        if p and self.top_rule:
            rule(p, 0, 0, w, tok("ln"))
        draw_label_tab(p, 0, 1 + 14, self.title)
        y = 1 + 14 + 25 + 8
        bx, right = 122, w - (58 + 12 if self.graded else 0)
        nf, vf, gf, lf = font(14, 500), font(22, 700, num=True), font(20, 700, num=True), font(13, 700, num=True)
        for k, row in enumerate(self.rows):
            if k:
                if p:
                    rule(p, 0, y, w, tok("ln"))
                y += 1
            y += 5
            if p:
                line(p, nf, tok("tx"), 0, y, 22, row.name)
                draw_bar(p, bx, y + 6, right - 46 - 12 - bx, row, self.p, self.first + k)
                base = baseline(vf, y, 22)
                right_text(p, vf, figure_ink(row), right, base, row.value + row.unit)
                if self.graded:
                    ink = theme.grade_color(row.letter) if row.letter else tok("mu")
                    lw = adv(lf, row.letter) + 3 if row.letter else 0
                    text_at(p, lf, ink, w - lw + 3, base, row.letter)
                    right_text(p, gf, ink, w - lw, base, row.grade)
            y += 22
            h = draw_under(p, bx, y + 4, w - bx, row, self.p, font(12), "mu", True)
            y += (4 + h if h else 0) + 5
        return y + 12


class TraitCard(Part):
    """Hands or Temperament: a framed card like the Habits ones, its 8px square and name, then a ruled list of
    figures, each over its note and chip"""

    def __init__(self, name: str, square: str):
        super().__init__()
        self.name, self.square = name, square
        self.rows: list[Row] = []

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
                base = baseline(vf, y + 8, 26)
                text_at(p, nf, tok("tx"), 0, base, row.name)
                unit = row.unit if row.unit[:1] in ("", "%") else f" {row.unit}"
                uw = adv(uf, unit) + 1 if unit else 0
                right_text(p, uf, tok("tx2"), w, base, unit)       # quiet, as the hero's: some inks miss 4.5:1 at 17px
                right_text(p, vf, figure_ink(row), w - uw, base, row.value)
            y += 1 + 7 + 26 + 2
            y += draw_under(p, 0, y, w, row, self.p, font(13), "tx2", False) + 8
        if p:
            p.restore()
        return y + 13 + 5


class EarlierTable(Part):
    """the Earlier drawer's rows, newest first: the dates, who you were, the main role, deaths an hour, cooldowns"""

    def __init__(self):
        super().__init__()
        self.rows: list[EarlierRow] = []

    def set(self, rows: list[EarlierRow]):
        self.rows = rows
        self.changed()

    def draw(self, p, w):
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
                text_at(p, lf, tok("tx2"), lx, base, elide(lf, row.label, rights[0] - rest[0] - 14 - lx))
                name, _, share = row.role.rpartition(" ")
                right_text(p, vf, tok("mu" if share == NA else "tx"), rights[0], base, share)
                right_text(p, sf, tok("tx2"), rights[0] - adv(vf, share) - 5, base, name)
                for s, right in zip((row.deaths, row.cooldowns), rights[1:]):
                    right_text(p, vf, tok("mu" if s == NA else "tx"), right, base, s)
            y += 1 + 6 + 20 + 6
        return y + 10


class Foot(Fold):
    """the page's foot: the Earlier drawer under a strong rule"""

    def paintEvent(self, _ev):
        rule(QPainter(self), 0, 0, self.width(), tok("tx"))


class ProfilePage(QScrollArea):
    """the Profile page, scrolling when the window is small: the hero and the plate, Signature and Hands on the left,
    the shares and Temperament on the right, Earlier at the foot"""
    open_habits = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.narrow = None
        self.thin = False
        self.settings: dict = {}        # the app's (shared), for "motion"
        self.entrance = QVariantAnimation(self, startValue=0.0, endValue=1.0, duration=ENTRANCE_MS)
        self.entrance.valueChanged.connect(self.set_progress)
        self.page = Sheet()
        self.hero, self.plate = ProfileHero(), Plate("Worth changing")
        self.plate.price_px, self.plate.body_last = 34, True
        self.plate.clicked.connect(self.open_habits)
        self.need, self.signature, self.table = Need(), Signature(), SpellTable()
        self.spells_drawer = Drawer("All spells", self.table)
        self.hands = TraitCard("Hands", "m-act")
        self.roles = ShareRows("Role mix", 5, top_rule=False, graded=True)
        self.places = ShareRows("Where you fight", 7, top_rule=True)
        self.temperament = TraitCard("Temperament", "m-surv")
        self.earlier = EarlierTable()
        self.earlier_drawer = Drawer("Earlier", self.earlier)
        self.foot = Foot(self.earlier_drawer)

        self.hero_row = QHBoxLayout()
        self.hero_row.setContentsMargins(0, 14, 0, 18)
        self.hero_row.addWidget(self.hero, 0, Qt.AlignmentFlag.AlignTop)
        self.hero_row.addWidget(self.plate, 1, Qt.AlignmentFlag.AlignTop)
        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 28, 16)
        left.setSpacing(0)
        left.addLayout(self.hero_row)
        left.addWidget(self.signature)
        left.addWidget(Fold(self.spells_drawer, last=True))
        left.addSpacing(16)
        left.addWidget(self.hands)
        left.addStretch(1)
        self.signature.setMinimumWidth(LEFT_MIN)
        side = Side()
        side.setFixedWidth(FIGHTS_W)
        right = QVBoxLayout(side)
        right.setContentsMargins(28, 4, 0, 16)
        right.setSpacing(0)
        right.addWidget(self.roles)
        right.addWidget(self.places)
        right.addWidget(self.temperament)
        right.addStretch(1)
        self.body = QWidget()
        cols = QHBoxLayout(self.body)
        cols.setContentsMargins(0, 0, 0, 0)
        cols.setSpacing(0)
        cols.addLayout(left, 1)
        cols.addWidget(side)
        lay = QVBoxLayout(self.page)
        lay.setContentsMargins(16, 4, 16, 16)
        lay.setSpacing(0)
        lay.addSpacing(HEAD_H)
        lay.addWidget(self.need)
        lay.addWidget(self.body)
        lay.addWidget(self.foot)
        lay.addStretch(1)
        self.setWidget(self.page)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._fit()
        self.show_view(ProfileView())

    def show_view(self, v: ProfileView):
        self.page.title, self.page.sub = v.title, v.meta
        thin = v.need is not None
        if thin and not self.thin and not self.earlier_drawer.open:     # all there is to see: open
            self.earlier_drawer.flip()
        self.thin = thin
        self.need.setVisible(thin)
        self.body.setVisible(not thin)
        self.need.head, self.need.text = v.need or "", v.need_line
        self.need.changed()
        self.hero.before, self.hero.chip_ink = v.before or "", v.chip_ink
        self.hero.set(v.hero, v.hero_unit or None, v.caption, v.chip, v.label or "")
        self.plate.setVisible(v.plate is not None)
        if v.plate:
            self.plate.set(v.plate.title, v.plate.figure, v.plate.caption, v.plate.button, [], v.plate.why)
        self.signature.set_view(v)
        self.table.set_view(v)
        self.spells_drawer.set_count(len(v.spells))
        self.hands.set(v.hands)
        self.roles.set(v.roles)
        self.places.set(v.places)
        self.temperament.set(v.temperament)
        self.earlier.set(v.earlier)
        self.earlier_drawer.set_count(len(v.earlier))
        self.foot.setVisible(bool(v.earlier))
        self.page.update()

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
        for part in (self.signature, self.hands, self.roles, self.places, self.temperament):
            part.p = p
        for part in (self.hero, self.signature, self.hands, self.roles, self.places, self.temperament):
            part.update()

    def resizeEvent(self, ev):
        self._fit()
        super().resizeEvent(ev)

    def _fit(self):
        """the mock-up's narrow hero and columns below a 1420px window"""
        narrow = self.window().width() < NARROW
        if narrow == self.narrow:
            return
        self.narrow = narrow
        self.hero.setFixedWidth(HERO_W[int(narrow)])
        self.hero_row.setSpacing(22 if narrow else 28)
        for part in (self.hero, self.plate, self.signature, self.earlier):
            part.narrow = narrow
            part.changed()
