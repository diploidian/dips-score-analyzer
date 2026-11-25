"""The Fights page: every fight summed up after it ended (open world and dungeons), newest first in the rail, and one
fight on its page, painted from a FightView (see dips_score/fight_view.py): how much of the damage you could have done
you did, the biggest gap on the plate, the key figures, where the rest went, what went well, the pull, the danger and
the group; and the fight's whole detail (abilities, cooldowns, auto attacks, buffs, failed casts, idle time, resource)
in the All the details drawer.

Sizes follow docs/design/mockups/fight.html (CSS px). The shared parts come from kit.py.
"""
from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QFontMetricsF, QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import (QAbstractItemView, QApplication, QFrame, QHBoxLayout, QLabel, QListWidget,
                             QListWidgetItem, QPushButton, QScrollArea, QStyle, QStyledItemDelegate, QStyleOptionViewItem,
                             QVBoxLayout, QWidget)

from .. import names
from ..fight_view import Presses, _foes, build_fight, list_row
from . import theme
from .debrief import NARROW
from .kit import (HEAD_H, BarRow, BarRows, Drawer, Fold, Hero, KeyFigures, Part, Plate, SectionHead, Sheet, Side, adv,
                  baseline, draw_label_tab, draw_tag, elide, flow, font, line, rule, text_at)
from .pages import dim_label, item, table
from .theme import tok

HERO_W = (330, 290)      # the hero's column (narrow)
SIDE_W = (420, 380)      # the right-hand column (narrow), after its 28px gutter
NAME_W = (260, 240)      # Where the damage went: the names' column, then the values' (narrow)
VALUE_W = (84, 80)
PRICE_PX = (46, 40)      # the plate's price
GROUP_COLS = ((140, 54), (128, 50))     # Group: the names' widest, and the damage and healing columns (narrow)
FACT_W = 136             # The pull and Danger: the labels' column, its widest ("SINCE THE LAST FIGHT") ~117
ROW = Qt.ItemDataRole.UserRole + 1
LEFT = "Left on the table · estimate — only time you were free to act"
NO_FIGHTS = ("No fights yet. Turn on the combat log in game (/combatlog) and fight something: each fight shows up here "
             "(and on the overlay) a few seconds after it ends.")
COUNTED = ("Cooldowns that sat ready while you were free (not moving for cast-time spells, not out of mana, not "
           "stunned, the target not nearly dead, nobody low while you heal), melee swings lost while not casting or moving, and "
           "idle time while standing with resource to spare (half counted).")


def _n(v) -> str:
    return f"{v:,.0f}"


def _words(text: str, f, bf, ink, bink) -> list:
    """text as flow() items, word by word: the words with a figure in them in bf and bink"""
    return [(s, bf, bink) if any(ch.isdigit() for ch in s) else (s, f, ink) for s in text.split()]


# ---------------------------------------------------------------------------- the rail's list
class FightRows(QStyledItemDelegate):
    """a fight's row on the rail: its name, then its muted line (DPS · efficiency · length, "died"), its kind tag on
    the right; the grade inks lifted toward rail-tx where they'd read under 4.5:1 on the rail (fight.html)"""

    def paint(self, p, opt, idx):
        o = QStyleOptionViewItem(opt)
        self.initStyleOption(o, idx)
        o.text = ""
        (o.widget.style() if o.widget else QApplication.style()).drawControl(
            QStyle.ControlElement.CE_ItemViewItem, o, p, o.widget)
        name, runs, kind = idx.data(ROW)
        r = QRectF(opt.rect).adjusted(10, 5, -10, -6)
        picked = bool(opt.state & QStyle.StateFlag.State_Selected)

        def ink(key: str):
            return tok("rail-mu") if key in ("mu", "tx2") else theme.on_rail(tok(key))
        edge = tok("rail-mu")
        edge.setAlpha(115)          # the mock-up's rail-ln: rail-mu at 45%
        p.save()
        nf = font(13, 600 if picked else 400)
        line(p, nf, tok("rail-tx"), r.x(), r.y(), 17, elide(nf, name, r.width()))
        x = r.x()
        for s, key in runs:
            x += line(p, font(12, 400 if key == "mu" else 600), ink(key), x, r.y() + 17, 16, s)
        draw_tag(p, r.right() - draw_tag(None, 0, 0, kind), r.y() + 17 + 8, kind, ink("mu"), edge)
        p.restore()

    def sizeHint(self, opt, idx):
        return QSize(super().sizeHint(opt, idx).width(), 5 + 17 + 16 + 6)


class FightList(QListWidget):
    """the rail's fights, newest first; picking one shows it (picked)"""
    picked = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.fights: list[dict] = []
        self.setItemDelegate(FightRows(self))
        self.currentRowChanged.connect(self._row)

    def set_fights(self, fights: list[dict]):
        keep = self.currentRow()
        self.fights = list(reversed(fights))            # newest first
        self.blockSignals(True)
        self.clear()
        for f in self.fights:
            self._add(f)
        self.blockSignals(False)
        if self.fights:
            self.setCurrentRow(max(0, keep))
            self._row(self.currentRow())

    def add_fight(self, f: dict):
        """a new fight on top (or an updated one in place); follows it if you were looking at the newest, else keeps
        the one you were reading (Qt moves the current row down itself when a row goes in above it)"""
        for i, old in enumerate(self.fights):
            if old.get("id") == f.get("id"):
                was = self.currentRow()
                self.fights[i] = f
                self.takeItem(i)
                self._add(f, i)
                self.setCurrentRow(was)
                if was == i:
                    self._row(i)        # the one you read changed: show it again
                return
        at_top = self.currentRow() <= 0
        self.fights.insert(0, f)
        self._add(f, 0)
        if at_top:
            self.setCurrentRow(0)

    def _add(self, f: dict, row: int | None = None):
        it = QListWidgetItem()
        row_data = list_row(f)
        row_data = (names.get(f.get("id", "")) or row_data[0], *row_data[1:])     # your name for it over the target
        it.setText(row_data[0])          # read out and searched by; painted by FightRows
        it.setData(ROW, row_data)
        it.setToolTip(_foes(f))
        if row is None:
            self.addItem(it)
        else:
            self.insertItem(row, it)

    def _row(self, row: int):
        if 0 <= row < len(self.fights):
            self.picked.emit(self.fights[row])


# ---------------------------------------------------------------------------- the page's parts
class FightHero(Hero):
    """the hero, then the fight's kind tag and "1:52 long · they got away" under the verdict"""

    def __init__(self):
        super().__init__()
        self.kind, self.status = "", ""

    def draw(self, p, w):
        y = super().draw(p, w) + 12
        x = draw_tag(p, 0, y + 9, self.kind) + 10 if self.kind else 0
        f = font(14)
        line(p, f, tok("tx2"), x, y, 18, elide(f, self.status, max(0.0, w - x)))
        return y + 18


class Losses(BarRows):
    """Where the damage went: the kit's bar rows under the key figures' rule, the bars as long as the column lets
    them"""
    top_rule = False
    value_w = VALUE_W[0]

    def draw(self, p, w):
        self.bar_w = max(0.0, w - self.name_w - self.value_w - 18)
        return super().draw(p, w)


def _check(p, x, y):
    """the drawn check in a 16px box at x, y"""
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(tok("m-dmg"), 2.2, cap=Qt.PenCapStyle.RoundCap, join=Qt.PenJoinStyle.RoundJoin))
    p.drawPolyline(QPolygonF([QPointF(x + 2.5, y + 8.5), QPointF(x + 6.5, y + 12.5), QPointF(x + 13.5, y + 3.5)]))
    p.restore()


class WentWell(Part):
    """Went well: a check before each, its figures bold; then what else to improve, under "Also", in tx2"""

    def __init__(self):
        super().__init__()
        self.good: list[str] = []
        self.also: list[str] = []

    def set(self, good: list[str], also: list[str]):
        self.good, self.also = good, also
        self.changed()

    def draw(self, p, w):
        y = 14
        draw_label_tab(p, 0, y, "Went well")
        y += 25 + 8
        f, bf, ef = font(15), font(19, 700, num=True), font(11, 600, num=True, spacing=0.14)
        lines = [(True, s) for s in self.good] + [(False, s) for s in self.also]
        for k, (good, s) in enumerate(lines):
            if k:
                if p:
                    rule(p, 0, y, w, tok("ln"))
                y += 1
            x = 26 if good else 44
            items = _words(s, f, bf, tok("tx"), tok("tx")) if good else [(word, f, tok("tx2")) for word in s.split()]
            h = flow(p, items, x, y + 7, w - x, adv(f, " "), 2)
            if p and good:
                _check(p, 0, y + 7 + (min(h, 23) - 16) / 2)
            elif p and k == len(self.good):     # the first of the rest
                text_at(p, ef, tok("mu"), 0, y + 7 + QFontMetricsF(f).ascent(), "ALSO")     # on flow's baseline
            y += 7 + h + 7
        y += 14
        if p:
            rule(p, 0, y, w, tok("ln"))
        return y + 1


class Facts(Part):
    """a section of facts (The pull, Danger): each row's label in small capitals on the left, its text beside it, the
    figures bold; a row with no label carries on the one above"""

    def __init__(self):
        super().__init__()
        self.title = ""
        self.rows: list[tuple[str, str]] = []

    def set(self, title: str, rows: list[tuple[str, str]]):
        self.title, self.rows = title, rows
        self.changed()

    def draw(self, p, w):
        y = 14
        draw_label_tab(p, 0, y, self.title)
        y += 25 + 8
        f, bf, lf = font(15), font(15, 600), font(11, 600, num=True, spacing=0.14)
        x = FACT_W
        for k, (label, s) in enumerate(self.rows):
            if k:
                if p:
                    rule(p, 0 if label else x, y, w - (0 if label else x), tok("ln"))   # under one label: its column
                y += 1
            h = flow(p, _words(s, f, bf, tok("tx"), tok("tx")), x, y + 7, w - x, adv(f, " "), 2)
            if p and label:
                text_at(p, lf, tok("mu"), 0, y + 7 + QFontMetricsF(f).ascent(), label.upper())     # on flow's baseline
            y += 7 + h + 7
        y += 14
        if p:
            rule(p, 0, y, w, tok("ln"))
        return y + 1


class PressTable(Part):
    """What you pressed: its line (the figures bold), then a row per spell: name and its muted note, the spell ID, by
    key, by click, and an Unknown column only when some presses didn't say how; or only the line, saying why not"""

    def __init__(self):
        super().__init__()
        self.view = Presses()

    def set(self, view: Presses):
        self.view = view
        self.setAccessibleName("What you pressed: " + view.line + " " + "; ".join(
            f"{n} {sid}: {k} by key, {c} by click" + (f", {o} not said" if o else "") for n, _, sid, k, c, o in view.rows))
        self.changed()

    def draw(self, p, w):
        y = 14
        draw_label_tab(p, 0, y, "What you pressed")
        y += 25 + 8
        f = font(15)
        y += flow(p, _words(self.view.line, f, font(15, 600), tok("tx2"), tok("tx")), 0, y, w, adv(f, " "), 6) + 8
        rows = self.view.rows
        if not rows:
            return y + 6
        other = any(r[5] for r in rows)
        cols = [(46, "KEY"), (46, "CLICK")] + ([(62, "UNKNOWN")] if other else [])
        idw = 76
        hf, nf, mf = font(11, 600, num=True, spacing=0.12), font(14), font(12)
        idf, vf, zf = font(14, 500, num=True), font(17, 700, num=True), font(17, 600, num=True)
        rights, x = [], w
        for cw, _ in reversed(cols):
            rights.insert(0, x)
            x -= cw
        id_right = x - 10
        if p:
            text_at(p, hf, tok("mu"), id_right - adv(hf, "SPELL ID"), baseline(hf, y, 11), "SPELL ID")
            for right, (_, s) in zip(rights, cols):
                text_at(p, hf, tok("mu"), right - adv(hf, s), baseline(hf, y, 11), s)
        y += 11 + 4
        for name, note, sid, *counts in rows:
            if p:
                rule(p, 0, y, w, tok("ln"))
                top = y + 1 + 6
                nw = line(p, nf, tok("tx"), 0, top, 20, elide(nf, name, id_right - idw - 8))
                if note:
                    line(p, mf, tok("mu"), nw + 6, top + 1, 18, elide(mf, note, max(0.0, id_right - idw - nw - 14)))
                line(p, idf, tok("mu"), id_right - adv(idf, sid), top, 20, sid)
                for right, n in zip(rights, counts[:len(cols)]):
                    s, cf = str(n), (vf if n else zf)
                    line(p, cf, tok("tx" if n else "mu"), right - adv(cf, s), top, 20, s)
            y += 1 + 6 + 20 + 6
        return y + 4


class GroupShare(Part):
    """Group: your shares in a sentence, then everyone, most damage first, with a bar for their damage (yours in m-dmg)
    and their healing muted beside it"""

    def __init__(self):
        super().__init__()
        self.rows: list[tuple[str, int, int, bool]] = []
        self.line = ""

    def set(self, rows: list[tuple[str, int, int, bool]], line_: str):
        self.rows, self.line = rows, line_
        self.changed()

    def draw(self, p, w):
        y = 14
        draw_label_tab(p, 0, y, "Group")
        y += 25 + 8
        f = font(15)
        y += flow(p, _words(self.line, f, font(15, 600), tok("tx2"), tok("tx")), 0, y, w, adv(f, " "), 6) + 8
        name_max, col = GROUP_COLS[int(self.narrow)]
        hf, rf, df = font(11, 600, num=True, spacing=0.12), font(14, 600, num=True), font(17, 700, num=True)
        hhf = font(17, 600, num=True)
        if p:
            for s, right in (("DAMAGE", w - col), ("HEALING", w)):
                text_at(p, hf, tok("mu"), right - adv(hf, s), baseline(hf, y, 11), s)
        y += 11 + 4
        nf, mf = font(14), font(14, 600)
        bx = 20 + name_max
        bar_w = max(0.0, w - 2 * col - bx - 12)
        most = max((dmg for _, dmg, _, _ in self.rows), default=0) or 1
        for k, (name, dmg, heal, you) in enumerate(self.rows):
            if p:
                rule(p, 0, y, w, tok("ln"))
                top = y + 1 + 6
                line(p, rf, tok("mu"), 0, top, 20, str(k + 1))
                line(p, mf if you else nf, tok("tx"), 20, top, 20, elide(mf if you else nf, name, name_max - 8))
                if dmg:
                    p.fillRect(QRectF(bx, top + 6, bar_w * dmg / most, 8), tok("m-dmg" if you else "mu"))
                d = _n(dmg)
                line(p, df, tok("tx" if dmg else "mu"), w - col - adv(df, d), top, 20, d)
                h = _n(heal)
                line(p, hhf, tok("mu"), w - adv(hhf, h), top, 20, h)
            y += 1 + 6 + 20 + 6
        return y + 14


# ---------------------------------------------------------------------------- the drawer
def _table(headers: list[str], rows: list[list], right_from: int = 1, stretch: int = 0):
    """a drawer table, as tall as its rows: the page scrolls, not the table; the stretch column takes what width is
    left, its text cut short there and whole on hover"""
    t = table(headers, stretch=stretch)
    t.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
    t.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    t.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    for r in rows:
        i = t.rowCount()
        t.insertRow(i)
        for c, v in enumerate(r):
            it = item(v, align_right=c >= right_from)
            if c == stretch:
                it.setToolTip(str(v))
            t.setItem(i, c, it)
    t.resizeRowsToContents()
    t.setFixedHeight(t.horizontalHeader().sizeHint().height() + t.verticalHeader().length() + 2 * t.frameWidth())
    return t


def _text(s: str) -> QLabel:
    lbl = QLabel(s)
    lbl.setWordWrap(True)
    return lbl


def _details(f: dict) -> list[tuple[str, list[QWidget]]]:
    """the drawer's sections, (title, widgets): everything the fight's old page listed but the pull, the enemies and
    the danger, which are in the right-hand column"""
    out = []
    if f.get("abilities"):
        out.append(("Abilities", [_table(["Ability", "Casts", "Hits", "Crits", "Miss", "Damage", "Avg", "Share"],
                                         [[a["name"], a["casts"], a["hits"], a["crits"], a["miss"], _n(a["damage"]),
                                           _n(a["avg"]), f"{a['share']:.0%}"] for a in f["abilities"]])]))
    if f.get("cooldowns"):
        rows = []
        for c in f["cooldowns"]:
            lost = "held" if c.get("held") else _n(c["lost"])
            missed = c.get("missed", "-")
            if "counted" in c and c["missed"] > c["counted"]:
                missed = f"{c['missed']} ({c['missed'] - c['counted']} excused)"
            if "free" in c:
                why = ", ".join(f"{k} {v:.1f}s" for k, v in c.get("excused", {}).items()) or "-"
                rows.append([c["name"], f"{c['cd']:.1f} s", c["used"], c.get("possible", "-"), missed, why,
                             f"{c['free']:.1f} s", lost])
            else:      # saved before ready time was measured
                rows.append([c["name"], f"{c['cd']:.1f} s", c["used"], "-", "-", "-", "-", lost])
        out.append(("Cooldowns", [
            _table(["Spell", "CD", "Used", "Possible", "Missed", "Excused", "Free", "Lost"], rows, stretch=5),
            dim_label("Possible: the casts that would have fit if you cast it each time it came up. Missed: the ones "
                      "you didn't make (those that sat ready under 2 s with no excuse are marked excused). Excused: "
                      "ready time with a good reason. Free: the rest, when you could have cast it - only that counts "
                      "as lost damage. Cooldowns of a minute or more only count on bosses (held: saved for one). "
                      "Cooldowns are learned from your casts and get more exact the more you play.")]))
    if f.get("auto"):
        a = f["auto"]
        out.append(("Auto attacks", [_text(f"{a['swings']} swings every {a['speed']:.1f} s; {a['lost']} lost "
                                           f"({a['lost_casting']} while casting, {a['lost_other']} other), about "
                                           f"{_n(a['damage_lost'])} damage.")]))
    r = f.get("ranged") or {}
    if r.get("shots"):        # saved before shots were measured: no line
        out.append(("Auto shots", [_text(f"{r['shots']} shots every {r['speed']:.1f} s; {r['shots_lost']} lost while "
                                         f"not shooting, about {_n(r['damage_lost'])} damage; {r['clipped']} clipped "
                                         f"by casts.")]))
    if f.get("buffs"):
        out.append(("Your buffs", [_table(["Name", "Uptime"],
                                          [[b["name"], f"{b['uptime']:.0%}"] for b in f["buffs"]])]))
    if f.get("failed"):
        out.append(("Failed casts", [_table(["Spell", "Reason", "Count"],
                                            [[x["spell"], x["reason"], x["count"]] for x in f["failed"]], 2)]))
    idle = f.get("idle") or {}
    out.append(("Idle time", [_text(
        f"{idle.get('total', 0):.1f} s idle (gaps of 2.5 s or more with nothing cast): "
        f"{idle.get('with_resource', 0):.1f} s free, {idle.get('moving', 0):.1f} s moving, stunned or with nothing to "
        f"hit, {idle.get('out_of_resource', 0):.1f} s out of resource. "
        + (f"Of it, {idle['swinging']:.1f} s with no ability used while "
           f"{'shooting' if idle.get('shooting') else 'swinging'} (the rest idle). " if idle.get("swinging") else "")
        + ("You have no filler spell to press between cooldowns, so idle time isn't counted."
           if idle.get("filler") is False else "Only the free part counts."))]))
    res = f.get("resource") or {}
    parts = ([f"Started {res['start']:.0%}"] if res.get("start") is not None else []) + \
        ([f"ended {res['end']:.0%}"] if res.get("end") is not None else []) + \
        ([f"started at {res['start_hp']:.0%} health"] if res.get("start_hp") is not None else [])
    out.append(("Resource", [_text(", ".join(parts) + "." if parts else
                                   "Not known (needs Advanced Combat Logging).")]))
    if f.get("best_before"):
        out.append(("Your best on this target", [_text(f"{f['best_before']:.0f} DPS before "
                                                       f"({f['dps'] - f['best_before']:+.0f} now)")]))
    return out


# ---------------------------------------------------------------------------- the page
class FightDetail(QScrollArea):
    """the Fights page: one fight, scrolling when the window is small or the drawer is open"""
    show_me = pyqtSignal(float, float)    # "Show on the timeline": the fight's run's Timeline tab, zoomed to the fight

    def __init__(self):
        super().__init__()
        self.span: tuple[float, float] | None = None
        self.narrow = None
        self.page = Sheet()
        self.hero, self.plate = FightHero(), Plate("Biggest gap")
        self.plate.clicked.connect(lambda: self.span and self.show_me.emit(*self.span))
        self.figures, self.where = KeyFigures(), Losses("Where the damage went")
        self.where.setToolTip(COUNTED)
        self.details = QWidget()
        self.details_lay = QVBoxLayout(self.details)
        self.details_lay.setContentsMargins(0, 0, 0, 12)
        self.details_lay.setSpacing(0)
        self.drawer = Drawer("All the details", self.details)
        self.fold = Fold(self.drawer, last=True)
        self.well, self.pull, self.danger, self.share = WentWell(), Facts(), Facts(), GroupShare()
        self.pressed = PressTable()
        self.in_order = QPushButton("See them in order on the timeline")
        self.in_order.clicked.connect(lambda: self.span and self.show_me.emit(*self.span))
        self.empty = dim_label(NO_FIGHTS)
        self.empty.setContentsMargins(0, 14, 0, 0)

        self.hero_row = QHBoxLayout()
        self.hero_row.setContentsMargins(0, 14, 0, 18)
        self.hero_row.addWidget(self.hero, 0, Qt.AlignmentFlag.AlignTop)
        self.hero_row.addWidget(self.plate, 1, Qt.AlignmentFlag.AlignTop)
        self.hero_row.addStretch(0)      # the plate hidden: the hero keeps its column on the left
        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 28, 0)
        left.setSpacing(0)
        left.addWidget(self.empty)
        left.addLayout(self.hero_row)
        for wd in (self.figures, self.where, self.fold):
            left.addWidget(wd)
        left.addStretch(1)
        self.side = Side()
        sl = QVBoxLayout(self.side)
        sl.setContentsMargins(28, 4, 0, 0)
        sl.setSpacing(0)
        for wd in (self.well, self.pull, self.danger, self.share, self.pressed):
            sl.addWidget(wd)
        sl.addWidget(self.in_order, 0, Qt.AlignmentFlag.AlignLeft)
        sl.addStretch(1)
        cols = QHBoxLayout()
        cols.setSpacing(0)
        cols.addLayout(left, 1)
        cols.addWidget(self.side)
        lay = QVBoxLayout(self.page)
        lay.setContentsMargins(16, 4, 16, 16)
        lay.setSpacing(0)
        lay.addSpacing(HEAD_H)
        lay.addLayout(cols, 1)
        self.setWidget(self.page)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._fit()
        self.show_fight(None)

    def show_fight(self, f: dict | None, span: tuple[float, float] | None = None, pressed: Presses | None = None):
        """f: a live fight (None: none yet); span: where it is on its run's timeline, for the plate's Show on the
        timeline and the presses' See them in order (None: no recorded run has it, so neither button); pressed: what
        you pressed in it"""
        self.span = span
        self.pressed.set(pressed or Presses())
        self.pressed.setVisible(f is not None and pressed is not None)
        self.in_order.setVisible(f is not None and span is not None and bool(pressed and pressed.rows))
        while (it := self.details_lay.takeAt(0)) is not None:
            if it.widget():
                it.widget().setParent(None)
        self.empty.setVisible(f is None)
        for wd in (self.hero, self.plate, self.figures, self.where, self.fold, self.side):
            wd.setVisible(f is not None)
        if f is None:
            self.page.title, self.page.sub = "Fights", ""
            self.page.update()
            return
        v = build_fight(f)
        self.page.title = names.titled(f.get("id", ""), v.name)
        self.page.sub = " · ".join(s for s in (v.when, v.zone) if s)
        self.hero.bar = None if v.efficiency is None else (v.efficiency, "m-cd")
        self.hero.kind, self.hero.status = v.kind, f"{v.duration} long · {v.result}"
        self.hero.set(v.big, v.unit, v.caption, None, v.verdict)
        title, price = v.gap or ("", None)
        self.plate.set(title, price, "damage" if v.gap else None, "Show on the timeline" if span else None, [])
        self.plate.setVisible(v.gap is not None)
        self.figures.set(v.figures)
        most = max((dmg for *_, dmg in v.rows), default=0) or 1
        self.where.lead = v.auto_share
        self.where.set([BarRow(label, f"≈{_n(dmg)}" if dmg > 0 else "–", dmg / most,
                               "m-cd" if label.endswith(" sat ready") else "m-act", detail or None)
                        for label, detail, dmg in v.rows],
                       None if v.left_on_table is None else (LEFT, f"≈{_n(v.left_on_table)}"))
        self.where.setVisible(bool(v.rows or v.auto_share))
        sections = _details(f)
        self.drawer.set_count(len(sections))        # what it holds: its sections
        for title_, widgets in sections:
            self.details_lay.addWidget(SectionHead(title_))
            for wd in widgets:
                self.details_lay.addWidget(wd)
        self.well.set(v.went_well, v.also)
        self.well.setVisible(bool(v.went_well or v.also))
        for part, title_, rows in ((self.pull, "The pull", v.pull), (self.danger, "Danger", v.danger)):
            part.set(title_, rows)
            part.setVisible(bool(rows))
        self.share.set(v.group or [], v.group_line or "")
        self.share.setVisible(v.group is not None)
        self.page.update()

    def resizeEvent(self, ev):
        self._fit()
        super().resizeEvent(ev)

    def _fit(self):
        """the mock-up's narrow hero, plate price, rows and columns below a 1420px window"""
        narrow = self.window().width() < NARROW
        if narrow == self.narrow:
            return
        self.narrow, k = narrow, int(narrow)
        self.hero.setFixedWidth(HERO_W[k])
        self.hero_row.setSpacing(22 if narrow else 28)
        self.side.setFixedWidth(SIDE_W[k] + 28)
        self.plate.price_px = PRICE_PX[k]
        self.where.name_w, self.where.value_w = NAME_W[k], VALUE_W[k]
        for part in (self.hero, self.plate, self.where, self.pull, self.danger, self.share, self.pressed):
            part.narrow = narrow
            part.changed()
