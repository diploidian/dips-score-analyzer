"""The Trade drawer's body on the Profile page, painted from a TradeView (trade_view.py): a sentence and when it is from,
then three figures on ruled rows, each in its own ink, and beside them (under them when narrow) the two sums the profit
comes from, as bars. Sizes follow #trade of docs/design/mockups/profile.html (CSS px)."""
from __future__ import annotations

from PyQt6.QtCore import QRectF

from ..trade_view import NA, TradeRow, TradeView
from .kit import Part, adv, baseline, font, rule, text_at, wrapped
from .sheetpart import GAP, TWO_COLS, heading, lead, right_text
from .theme import tok

NAME_W, BAR_H, NOTE_W = 110, 10, 560        # NOTE_W: about 68 characters


class TradeSection(Part):
    def __init__(self):
        super().__init__()
        self.view = TradeView()

    def set(self, v: TradeView):
        self.view = v
        self.setAccessibleName("Trade: " + (v.need or " ".join((
            v.say, v.cap, " ".join(f"{r.name}: {r.value}{' ' + r.unit if r.unit else ''}. {r.note}" for r in v.rows),
            "What it comes from: " + "; ".join(f"{x.name} {x.value}" for x in v.ledger) + ".", v.note))))
        self.changed()

    def draw(self, p, w):
        v = self.view
        y = 2 + lead(p, w, 2, v.need or v.say)
        if v.need:
            return y + 18
        y += 4 + wrapped(p, font(13), tok("tx2"), 0, y + 4, w, 13 * 1.4, v.cap) + 14
        two = w >= TWO_COLS
        cw = (w - GAP) / 2 if two else w
        left = y
        for r in v.rows:
            left += self.row(p, 0, left, cw, r)
        x, top = (cw + GAP, y) if two else (0, left + 18)
        if not v.ledger:
            return left + 18
        return max(left, self.sums(p, x, top, cw)) + 18

    @staticmethod
    def row(p, x, y, w, r: TradeRow) -> float:
        nf, vf, uf, tf = font(15, 500), font(26, 700, num=True), font(17, 600, num=True), font(13)
        uw = adv(uf, r.unit) + 6 if r.unit else 0
        vw = adv(vf, r.value)
        y1 = y + 8
        base = baseline(vf, y1, 26)
        if p:
            rule(p, x, y, w, tok("ln"))
            right_text(p, vf, tok("mu" if r.value == NA else r.ink), x + w - uw, base, r.value)
            if r.unit:
                text_at(p, uf, tok("tx2"), x + w - uw + 6, base, r.unit)
        # a long name wraps: its first line shares the figure's baseline
        h = max(26.0, base - y1 - baseline(nf, 0, 20) + wrapped(p, nf, tok("tx"), x, base - baseline(nf, 0, 20), w - vw - uw - 12, 20, r.name))
        if r.note:
            h += 2 + wrapped(p, tf, tok("tx2"), x, y1 + h + 2, w, 13 * 1.4, r.note)
        return y1 - y + h + 8

    def sums(self, p, x, y0, w) -> float:
        nf, vf = font(14, 500), font(20, 700, num=True)
        y = y0 + heading(p, x, y0, "What it comes from")
        vw = max(adv(vf, s.value) for s in self.view.ledger)
        bx, bw = x + NAME_W + 12, max(0.0, w - NAME_W - vw - 24)
        for s in self.view.ledger:
            if p:
                rule(p, x, y, w, tok("ln"))
                text_at(p, nf, tok("tx"), x, baseline(nf, y + 6, 20), s.name)
                p.fillRect(QRectF(bx, y + 11, bw, BAR_H), tok("track"))
                p.fillRect(QRectF(bx, y + 11, bw * s.width, BAR_H), tok(s.ink))
                right_text(p, vf, tok(s.ink), x + w, baseline(vf, y + 6, 20), s.value)
            y += 1 + 5 + 20 + 6
        if p:
            rule(p, x, y, w, tok("ln"))
        return y + 1 + 8 + wrapped(p, font(13), tok("tx2"), x, y + 9, min(w, NOTE_W), 13 * 1.4, self.view.note)
