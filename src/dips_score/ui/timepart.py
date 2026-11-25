"""Where your time goes, on the Profile page: the Player Type, one bar of your hours, and its parts named and timed under
it, painted from a TimeBar (time_view.py). Sizes follow #time of docs/design/mockups/profile.html (CSS px)."""
from __future__ import annotations

from PyQt6.QtCore import QRectF

from ..time_view import TimeBar, TimePart
from .kit import Part, adv, baseline, box, draw_label_tab, font, line, rule, wrapped
from .sheetpart import right_text
from .theme import tok

TITLE = "Where your time goes"
COLS = ((1000, 3), (620, 2))        # columns of parts from a width
GAP, BAR_H, BAR_GAP, LEAST = 40, 22, 2, 3


class TimeSection(Part):
    def __init__(self):
        super().__init__()
        self.view = TimeBar()
        self.grow = lambda p, i: 1.0        # how much of bar i is drawn at the entrance's p, the page's

    def set(self, v: TimeBar):
        self.view = v
        self.setAccessibleName(f"{TITLE}: " + (v.need or " ".join((
            f"{v.type}.", v.meta, "; ".join(", ".join(filter(None, (f"{t.name} {t.share}", t.time, t.chip))) for t in v.parts) + ".", v.note))).strip())
        self.changed()

    def draw(self, p, w):
        v = self.view
        if p:
            rule(p, 0, 0, w, tok("ln"))
        y = 1 + 16 + draw_label_tab(p, 0, 17, TITLE).height() + 12
        if v.need:
            return y + wrapped(p, font(23, 600, num=True), tok("tx"), 0, y, w, 23 * 1.2, v.need) + 18
        cf = font(13)
        y += wrapped(p, font(34, 700, num=True), tok("tx"), 0, y, w, 34 * 1.1, v.type) + 4
        y += wrapped(p, cf, tok("tx2"), 0, y, w, 13 * 1.4, v.meta) + 14
        if p:
            self.bar(p, y, w)
        y += BAR_H + 4
        n = next((n for least, n in COLS if w >= least), 1)
        cw = (w - GAP * (n - 1)) / n
        for k in range(0, len(v.parts), n):
            row = v.parts[k:k + n]
            h = max(self.part(None, 0, 0, cw, t) for t in row)
            for c, t in enumerate(row):
                self.part(p, c * (cw + GAP), y, cw, t)
                if p:
                    rule(p, c * (cw + GAP), y + h, cw, tok("ln"))
            y += h + 1
        if v.note:
            y += 10 + wrapped(p, cf, tok("tx2"), 0, y + 10, w, 13 * 1.4, v.note)
        return y + 18

    def bar(self, p, y, w):
        """every part at least LEAST wide, the rest as long as its share"""
        parts = self.view.parts
        free = w - BAR_GAP * (len(parts) - 1)
        small = [t for t in parts if t.width * free < LEAST]
        big = sum(t.width for t in parts if t not in small) or 1
        x = 0.0
        for i, t in enumerate(parts):
            size = LEAST if t in small else (free - LEAST * len(small)) * t.width / big
            p.fillRect(QRectF(x, round(y), size * self.grow(self.p, i), BAR_H), tok(t.ink))
            x += size + BAR_GAP

    @staticmethod
    def part(p, x, y, w, t: TimePart) -> float:
        nf, vf, tf, chf = font(14, 500), font(20, 700, num=True), font(13), font(14, 600, num=True)
        y += 6
        base, at = baseline(vf, y, 22), x + w - 92 - 10
        room = at - adv(vf, t.share) - 10 - (x + 20)
        if p:
            p.fillRect(QRectF(x, round(y + 8), 10, 10), tok(t.ink))
            right_text(p, vf, tok("tx"), at, base, t.share)
            right_text(p, tf, tok("tx2"), x + w, base, t.time)
        top = base - baseline(nf, 0, 20)        # a long name wraps: its first line shares the figures' baseline
        h = max(22.0, top - y + wrapped(p, nf, tok("tx"), x + 20, top, room, 20, t.name))
        if t.chip:
            ch = 14 * 1.25 + 6
            if p:
                box(p, QRectF(x + 20, y + h + 4, adv(chf, t.chip) + 18, ch), tok("ln"))
                line(p, chf, tok("tx"), x + 29, y + h + 7, 14 * 1.25, t.chip)
            h += 4 + ch
        return 6 + h + 7
