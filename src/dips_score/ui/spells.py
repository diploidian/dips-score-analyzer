"""The Spells tab's page, painted from a SpellsView (see dips_score/spells_view.py): your damage and where it came
from, the ability to fix on the plate (the cooldown that cost most, the abilities the game refused), the healing,
and every spell in the drawers. Pick a spell (a row, or one in a drawer) to light its casts up on the timeline.

Sizes follow docs/design/mockups/spells.html (CSS px). The shared parts come from kit.py.
"""
from dataclasses import dataclass

from PyQt6.QtCore import QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QScrollArea, QVBoxLayout, QWidget

from ..spells_view import REFUSED, SpellsView, build_spells
from . import assets
from .debrief import NARROW
from .kit import (HEAD_H, Drawer, Hero, Part, Plate, Sheet, adv, baseline, draw_hand_circle, draw_label_tab, elide,
                  font, line, rule, text_at)
from .pages import dim_label, fmt_num, item, run_meta, table
from .theme import tok

HERO_W = (290, 250)      # the hero's column (narrow)
SIDE_W = (380, 360)      # the right-hand column (narrow), after its 28px gutter
BAR_CELL = 254           # the damage bars' column; the longest bar is 14px short of it
NA = "–"
# a cell's run styles: px, weight, condensed, ink, line height
STYLE = {"s": (18, 700, True, "tx", 18.0), "v": (13, 400, False, "mu", 13 * 1.4),
         "bad": (13, 600, False, "gD", 13 * 1.4)}


def _font(style: str):
    px, weight, num, _, _ = STYLE[style]
    return font(px, weight, num=num)


def _width(runs) -> float:
    return sum(adv(_font(st), s) for s, st in runs)


@dataclass
class Row:
    name: str
    cells: list[list[tuple[str, str]]]     # each column's runs of (text, style)
    fraction: float = 0.0                  # the bar, of the longest (bar tables)
    note: str | None = None                # muted, under the bar


class Ruled(Part):
    """a section: its label tab, a head of tracked capitals, then ruled rows (the name; in a bar table, the bar and a
    note under it; right-aligned columns) and an optional muted line under them. ring: the (row, column) the
    highlighter circles. Click a row to pick its spell (clicked; the picked row again: None)."""
    clicked = pyqtSignal(object)

    def __init__(self, title: str, heads: list[str], bar: bool = False, top_rule: bool = False):
        super().__init__()
        self.title, self.heads, self.bar, self.top_rule = title, heads, bar, top_rule
        self.rows: list[Row] = []
        self.ring: tuple[int, int] | None = None
        self.foot: str | None = None
        self.sel: str | None = None                     # the picked spell, its row lifted
        self.hits: list[tuple[float, float, str]] = []  # each row's top, bottom and name, as last laid out
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set(self, rows: list[Row], ring: tuple[int, int] | None = None, foot: str | None = None):
        self.rows, self.ring, self.foot = rows, ring, foot
        self.changed()

    def mousePressEvent(self, ev):
        y = ev.position().y()
        name = next((n for top, bottom, n in self.hits if top <= y < bottom), None)
        if name:
            self.clicked.emit(None if name == self.sel else name)

    def draw(self, p, w):
        y = 0.0
        if self.top_rule:
            if p:
                rule(p, 0, 0, w, tok("ln"))
            y = 1.0
        y += 14
        draw_label_tab(p, 0, y, self.title)
        y += 25 + 10
        hf = font(11, 600, num=True, spacing=0.12)
        cols = [max([adv(hf, h.upper())] + [_width(r.cells[k]) for r in self.rows]) + 14
                + (14 if self.ring and self.ring[1] == k else 0)        # room for the ring's overhang
                for k, h in enumerate(self.heads)]
        rights = [w - sum(cols[k + 1:]) for k in range(len(cols))]
        nf, notef = font(15, 500), font(12)
        names = max((adv(nf, r.name) for r in self.rows), default=0.0)
        bar_cell = min(BAR_CELL, max(80.0, w - sum(cols) - names)) if self.bar else 0.0
        name_w = w - sum(cols) - bar_cell
        bx, bar_w = name_w + 14, bar_cell - 14
        if p:
            for k, h in enumerate(self.heads):
                s = h.upper()
                text_at(p, hf, tok("mu"), rights[k] - adv(hf, s), baseline(hf, y, 11), s)
        y += 11 + 6
        self.hits, ring = [], None
        for i, r in enumerate(self.rows):
            if p:
                rule(p, 0, y, w, tok("ln"))
            y += 1
            ch = 10 + 3 + 12 * 1.4 if self.bar and r.note else 21.0     # the bar and its note, or a line
            top = y + 5
            if p:
                if r.name == self.sel:
                    p.fillRect(QRectF(0, y, w, ch + 10), tok("panel"))
                line(p, nf, tok("tx"), 0, top + (ch - 21) / 2, 21, elide(nf, r.name, name_w))
                if self.bar:
                    bt = top if r.note else top + (ch - 10) / 2
                    p.fillRect(QRectF(bx, bt, bar_w * r.fraction, 10), tok("m-dmg"))
                    if r.note:
                        line(p, notef, tok("mu"), bx, bt + 13, 12 * 1.4, elide(notef, r.note, bar_w))
                for k, runs in enumerate(r.cells):
                    x0 = x = rights[k] - _width(runs)
                    for s, st in runs:
                        lh = STYLE[st][4]
                        x += line(p, _font(st), tok(STYLE[st][3]), x, top + (ch - lh) / 2, lh, s)
                    if self.ring == (i, k):     # as the mock-up's ring: 14px out either side, 9 above and below
                        ring = QRectF(x0 - 14, top + (ch - 13 * 1.4) / 2 - 9, x - x0 + 28, 13 * 1.4 + 18)
            self.hits.append((top - 6, top + ch + 5, r.name))
            y = top + ch + 5
        if self.rows:
            if p:
                rule(p, 0, y, w, tok("ln"))
            y += 1
        if p and ring is not None:      # over the rules, as the mock-up's overflowing ring is
            draw_hand_circle(p, ring, tok("hl"), -3)
        if self.foot:
            y += 8
            if p:
                line(p, font(13), tok("mu"), 0, y, 13 * 1.4, self.foot)
            y += 13 * 1.4
        return y + 6


class Fold(QWidget):
    """a drawer: its header between rules, its body under it; the last closes with a rule under it all"""

    def __init__(self, drawer: Drawer, last: bool = False):
        super().__init__()
        self.last = last
        head = QHBoxLayout()
        head.setContentsMargins(0, 8, 0, 8)
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
    """the right-hand column, ruled off from the left"""

    def paintEvent(self, _ev):
        QPainter(self).fillRect(QRectF(0, 0, 1, self.height()), tok("ln"))


def _body(t) -> QWidget:
    """a drawer's table, with the mock-up's 12px under it"""
    t.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 12)
    lay.addWidget(t)
    return w


class SpellsTab(QScrollArea):
    """the Spells tab: the page, scrolling when the window is small or a drawer is open"""
    highlight = pyqtSignal(object, object)               # a spell picked: guid, spell (None, None: clear); tab stays
    show_me = pyqtSignal(float, float, object, object)   # "Show on the timeline": start, end, guid, spell

    def __init__(self):
        super().__init__()
        self.a = None
        self.view = SpellsView()
        self.narrow = None
        top = QWidget()
        top.setFixedHeight(HEAD_H)
        head = QHBoxLayout(top)          # right of the title: the player and the fights
        head.setContentsMargins(0, 0, 0, 0)
        head.addStretch(1)
        self.who, self.scope = QComboBox(), QComboBox()
        self.who.setMinimumWidth(200)
        for label, key in (("Whole run", "all"), ("Bosses", "boss"), ("Trash", "trash")):
            self.scope.addItem(label, key)
        for text, box in (("Player", self.who), ("Fights", self.scope)):
            head.addWidget(dim_label(text), 0, Qt.AlignmentFlag.AlignTop)
            head.addWidget(box, 0, Qt.AlignmentFlag.AlignTop)
            box.currentIndexChanged.connect(self._fill)
        self.page = Sheet(top)
        self.hero, self.plate = Hero(), Plate("Ability to fix")
        self.plate.clicked.connect(self._show)
        self.damage = Ruled("Where your damage came from", ["share", "casts", "refused", "per min", "crit"], bar=True,
                            top_rule=True)
        self.healing = Ruled("Healing", ["healed", "overheal"])
        for part in (self.damage, self.healing):
            part.clicked.connect(self._pick)
        self.buffs = table(["Spell", "Casts", "Refused"], stretch=0)
        self.every = table(["Spell", "Casts", "Refused", "Damage", "Healing"], stretch=0)
        self.buffs_drawer = Drawer("Buffs, seals and blessings", _body(self.buffs))
        self.all_drawer = Drawer("All spells", _body(self.every))
        for t in (self.buffs, self.every):
            t.itemSelectionChanged.connect(lambda t=t: self._picked_in(t))

        self.hero_row = QHBoxLayout()
        self.hero_row.setContentsMargins(0, 14, 0, 18)
        self.hero_row.addWidget(self.hero, 0, Qt.AlignmentFlag.AlignTop)
        self.hero_row.addWidget(self.plate, 1, Qt.AlignmentFlag.AlignTop)
        self.hero_row.addStretch(0)      # the plate hidden: the hero keeps its column on the left
        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 28, 0)
        left.setSpacing(0)
        left.addLayout(self.hero_row)
        left.addWidget(self.damage)
        left.addStretch(1)
        self.side = Side()
        sl = QVBoxLayout(self.side)
        sl.setContentsMargins(28, 0, 0, 0)
        sl.setSpacing(0)
        sl.addWidget(self.healing)
        sl.addSpacing(22)
        sl.addWidget(Fold(self.buffs_drawer))
        sl.addWidget(Fold(self.all_drawer, last=True))
        sl.addStretch(1)
        cols = QHBoxLayout()
        cols.setSpacing(0)
        cols.addLayout(left, 1)
        cols.addWidget(self.side)
        lay = QVBoxLayout(self.page)
        lay.setContentsMargins(16, 4, 16, 16)
        lay.setSpacing(0)
        lay.addWidget(top)
        lay.addLayout(cols, 1)
        self.setWidget(self.page)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._fit()

    def set_analysis(self, a):
        self.a = a
        self.who.blockSignals(True)
        self.who.clear()
        if a:
            for pl in sorted(a.roster.values(), key=lambda pl: (not pl.is_me, pl.name)):
                self.who.addItem(pl.name + (" (you)" if pl.is_me else ""), pl.guid)
                if (ic := assets.icon(assets.class_icon_name(pl.cls) or "")) is not None:
                    self.who.setItemIcon(self.who.count() - 1, ic)
        self.who.blockSignals(False)
        self._fill()

    def _fill(self):
        a, guid = self.a, self.who.currentData()
        if not a or not guid:
            self.show_view(SpellsView(), "No run selected", "")
            return
        me, name = guid == a.data.player_guid, a.roster[guid].name
        self.show_view(build_spells(a, guid, self.scope.currentData()),
                       a.data.run.zone if me else f"{name} - {a.data.run.zone}", run_meta(a),
                       "your" if me else f"{name}'s")

    def show_view(self, view: SpellsView, title: str, sub: str, whose: str = "your"):
        """whose: "your", or "Anna's"; a refill clears the timeline's highlight"""
        self.view = view
        self.page.title, self.page.sub = title, sub
        if view.total_damage:
            s = fmt_num(view.total_damage)
            big = s.rstrip("KM")
            self.hero.set(big, s[len(big):] or None, f"{view.total_damage:,} damage · {view.dps:.0f}/s in combat",
                          None, view.verdict)
        else:
            self.hero.set("–", None, "no damage logged", None, view.verdict)
        if view.fix:
            title, price, caption = view.fix
            self.plate.set(title, price, caption, "Show on the timeline" if view.show else None, view.next_rows)
        self.plate.setVisible(bool(view.fix))      # cooldowns are measured for you only
        most = max((r.damage for r in view.damage_rows), default=0) or 1
        ring = next(((k, 2) for k, r in enumerate(view.damage_rows) if r.name == view.refused_most), None)
        self.damage.title = f"Where {whose} damage came from"
        self.damage.set([Row(r.name, [[(f"{r.share:.0%}", "s")], [(_casts(r), "v")],
                                      _refused(r), [(NA if r.per_min is None else f"{r.per_min:.1f}", "v")],
                                      [(NA if r.crit is None else f"{r.crit:.0%}", "v")]], r.damage / most, r.note)
                         for r in view.damage_rows], ring)
        heal = view.healing_rows
        self.healing.set([Row(r.name, [[(f"{r.healing:,}", "s")], [(f"{r.overheal_share:.0%}", "v")]]) for r in heal],
                         None, f"{sum(r.healing for r in heal):,} healed in all")
        self.damage.setVisible(bool(view.damage_rows))
        self.healing.setVisible(bool(heal))
        self.buffs_drawer.set_count(len(view.buff_rows))
        self.all_drawer.set_count(len(view.all_rows))
        _fill_table(self.buffs, [(r.name, _casts(r), _refusals(r)) for r in view.buff_rows])
        _fill_table(self.every, [(r.name, _casts(r), _refusals(r),
                                  f"{r.damage:,}" if r.damage else NA, f"{r.healing:,}" if r.healing else NA)
                                 for r in view.all_rows])
        for part in (self.damage, self.healing):
            part.sel = None
        self.page.update()
        self.highlight.emit(None, None)

    def _show(self):
        if self.view.show:
            start, end, spell = self.view.show
            self.show_me.emit(start, end, self.who.currentData(), spell)

    def _pick(self, spell: str | None):
        """a spell picked (None: unpicked): lit up on the timeline, which readies in the background"""
        for part in (self.damage, self.healing):
            part.sel = spell
            part.update()
        self.highlight.emit(self.who.currentData() if spell else None, spell)

    def _picked_in(self, t):
        rows = t.selectionModel().selectedRows()
        if rows:
            self._pick(t.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole))

    def resizeEvent(self, ev):
        self._fit()
        super().resizeEvent(ev)

    def _fit(self):
        """the mock-up's narrow hero and columns below a 1420px window"""
        narrow = self.window().width() < NARROW
        if narrow == self.narrow:
            return
        self.narrow, k = narrow, int(narrow)
        self.hero.setFixedWidth(HERO_W[k])
        self.hero_row.setSpacing(22 if narrow else 28)
        self.side.setFixedWidth(SIDE_W[k] + 28)
        for part in (self.hero, self.plate):
            part.narrow = narrow
            part.changed()


def _refused(r) -> list[tuple[str, str]]:
    """"32 · 12%", the share in gD past REFUSED; "–" with no presses, or another player's (not in the log)"""
    if r.refused_share is None:
        return [(NA, "v")]
    if r.refused_share > REFUSED:
        return [(f"{r.refused} · ", "v"), (f"{r.refused_share:.0%}", "bad")]
    return [(f"{r.refused} · {r.refused_share:.0%}", "v")]


def _casts(r) -> str:
    """"–" when it was never pressed (melee, procs)"""
    return str(r.casts) if r.casts + r.refused else NA


def _refusals(r) -> str:
    """"–" when it was never pressed, or for another player (only yours are in the log)"""
    return NA if r.refused_share is None else str(r.refused)


def _fill_table(t, rows: list[tuple]):
    """the drawer's table, as tall as its rows (the page scrolls, not the table)"""
    t.blockSignals(True)
    t.setRowCount(0)
    for k, cells in enumerate(rows):
        t.insertRow(k)
        for col, text in enumerate(cells):
            it = item(text, align_right=col > 0, data=text if col == 0 else None)
            if col == 0:
                it.setToolTip(text)     # the column is narrow: a long name is cut short
            t.setItem(k, col, it)
    t.blockSignals(False)
    t.setFixedHeight(t.horizontalHeader().sizeHint().height() + t.verticalHeader().length() + 2 * t.frameWidth())
