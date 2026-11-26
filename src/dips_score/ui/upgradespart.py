"""The Upgrades drawer's body on the Profile page, painted from an UpgradesView (upgrades_view.py): the two guardrails, a
sentence and when the scan was, then one ruled row per piece of gear (its name in its rarity's ink, its price, what it adds,
where its price is from). Hovering a row shows its tooltip as the game writes it. Rows are drawn as Trade's are (tradepart.py)."""
from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtWidgets import QBoxLayout, QHBoxLayout, QLabel, QSpinBox, QVBoxLayout, QWidget

from ..upgrades_view import UpgradeRow, UpgradesView, build_upgrades
from .kit import Tips, adv, baseline, font, rule, wrapped
from .sheetpart import NARROW, lead, right_text
from .theme import tok


class UpgradeList(Tips):
    def __init__(self):
        super().__init__()
        self.view = UpgradesView()

    def set(self, v: UpgradesView):
        self.view = v
        said = lambda r: ", ".join(filter(None, (r.name, r.slot, r.price, r.gain, r.points, r.per_gold, r.source)))  # noqa: E731
        self.setAccessibleName("Upgrades: " + (v.need or " ".join(filter(None, (v.say, v.cap, *map(said, v.rows), v.hidden, v.web)))))
        self.changed()

    def draw(self, p, w):
        v = self.view
        y = 2 + lead(p, w, 2, v.need or v.say)
        if v.need:
            return y + 18
        y += 4 + wrapped(p, font(13), tok("tx2"), 0, y + 4, w, 13 * 1.4, v.cap) + 14
        if p:
            self.tips = []
        for r in v.rows:
            h = self.row(p, y, w, r)
            if p:
                self.tips.append((QRectF(0, y, w, h), r.tip or "Its tooltip was not read."))
            y += h
        if v.hidden:
            if p:
                rule(p, 0, y, w, tok("ln"))
            y += 8 + wrapped(p, font(13), tok("tx2"), 0, y + 8, w, 13 * 1.4, v.hidden)
        if v.web:
            y += 8 + wrapped(p, font(12), tok("mu"), 0, y + 8, w, 12 * 1.4, v.web)
        return y + 18

    @staticmethod
    def row(p, y, w, r: UpgradeRow) -> float:
        nf, vf, tf = font(15, 600), font(22, 700, num=True), font(13)
        vw = adv(vf, r.price)
        y1 = y + 8
        base = baseline(vf, y1, 24)
        if p:
            rule(p, 0, y, w, tok("ln"))
            right_text(p, vf, tok("tx"), w, base, r.price)
        # the name wraps beside the price, its first line on the price's baseline
        top = base - baseline(nf, 0, 20)
        h = max(24.0, top - y1 + wrapped(p, nf, tok(r.ink), 0, top, w - vw - 12, 20, r.name))
        gain = " · ".join(filter(None, (r.slot, r.gain, r.points, r.per_gold)))
        h += 2 + wrapped(p, tf, tok("tx" if r.compared else "tx2"), 0, y1 + h + 2, w, 13 * 1.4, gain)
        h += wrapped(p, font(12), tok("mu"), 0, y1 + h, w, 12 * 1.4, r.source)
        return y1 - y + h + 8


class UpgradesSection(QWidget):
    """the drawer's body: the guardrails over the list, which is picked again when one moves"""

    def __init__(self):
        super().__init__()
        self.view = UpgradesView()
        self.list = UpgradeList()
        self.gold, self.times = QSpinBox(), QSpinBox()
        self.gold.setAccessibleName("At most this many gold")
        self.times.setAccessibleName("Hide anything over this many times its usual price")
        self.times.setRange(1, 10)
        self.bar = QWidget()
        self.bar.setMinimumWidth(1)         # the page never scrolls sideways: narrow, the guardrails stack (resizeEvent)
        self.row = QBoxLayout(QBoxLayout.Direction.LeftToRight, self.bar)
        self.row.setContentsMargins(0, 2, 0, 12)
        self.row.setSpacing(16)
        for parts in ((QLabel("At most"), self.gold, QLabel("gold,")), (QLabel("nothing over"), self.times, QLabel("times its usual price"))):
            row = QHBoxLayout()
            row.setSpacing(8)
            row.setAlignment(Qt.AlignmentFlag.AlignLeft)        # as wide as its words, side by side or stacked
            for part in parts:
                row.addWidget(part)
            self.row.addLayout(row)
        self.row.addStretch(1)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self.bar)
        lay.addWidget(self.list)
        self.gold.valueChanged.connect(self._pick)
        self.times.valueChanged.connect(self._pick)

    def resizeEvent(self, ev):
        """in a narrow page the second guardrail goes under the first"""
        across = QBoxLayout.Direction.LeftToRight if self.width() >= NARROW else QBoxLayout.Direction.TopToBottom
        if self.row.direction() != across:
            self.row.setDirection(across)
        super().resizeEvent(ev)

    def set(self, v: UpgradesView):
        new = (v.data or {}).get("taken") != (self.view.data or {}).get("taken")
        self.view = v
        self.bar.setVisible(not v.need)
        if new:         # a new scan starts at its own guardrails; the same one keeps what you set
            for box, top, value in ((self.gold, v.most, v.gold), (self.times, 10, v.times)):
                box.blockSignals(True)
                box.setRange(1, top)
                box.setValue(value)
                box.blockSignals(False)
        self._pick()

    def _pick(self):
        self.list.set(build_upgrades(self.view.data, self.gold.value(), self.times.value()) if self.view.data else self.view)
