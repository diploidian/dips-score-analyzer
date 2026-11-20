"""The Pulls tab's page, painted from a PullsView (see dips_score/pulls_view.py): how many pulls and how safely you
went into them, the one pull to fix on the plate, the run pull by pull with your mana under it, pull safety and who
pulled, and every pull with its mobs in the All pulls drawer.

Sizes follow docs/design/mockups/pulls.html (CSS px). The shared parts come from kit.py.
"""
import math

from PyQt6.QtCore import QEvent, QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QFont, QFontMetricsF, QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QHeaderView, QLabel, QScrollArea, QSplitter, QStyle,
                             QStyledItemDelegate, QStyleOptionViewItem, QToolTip, QTreeWidget, QTreeWidgetItem,
                             QVBoxLayout, QWidget)

from ..debrief import fmt_time
from ..pulls_view import BREAK_S, LOW, PullsView, build_pulls, fix_plate, pct, safety_figures, slide_note, slide_rows
from . import assets
from .debrief import NARROW, preview_tag
from .kit import (HEAD_H, Drawer, Hero, KeyFigures, Part, Plate, Sheet, adv, baseline, box, draw_hand_circle,
                  draw_hand_note, draw_label_tab, font, hand_font, line, rule, text_at)
from .pages import dim_label, item, run_meta, table
from .theme import tok

PLATE_W = 408        # the plate's column
VERDICT_W = 576      # the verdict stops at 36em
X0, RIGHT = 96, 12   # the track's time axis: after the PULLS / MANA labels, to 12px short of the edge
TRACK_H = 224        # the track and mana line, as the mock-up's 1184 x 224 drawing (only x stretches)
LANE, M100, M0 = 58, 118, 198      # the pulls' line; the mana line's 100% and 0
HEAD = 1 + 12 + 25 + 6             # a section's rule, padding and label tab
BODY_H = 640         # the open drawer: the pulls table, the picked pull's mobs under it
RUNS = Qt.ItemDataRole.UserRole + 1


def radius(mobs: int) -> float:
    """a dot's radius: its area grows with the mobs"""
    return 2.8 * math.sqrt(mobs)


def shade(mana: float | None) -> float:
    """a dot's fill opacity: 0.12 at full mana to 1 at 40%; none without a mana reading"""
    return 0.0 if mana is None else min(1.0, max(0.12, 0.12 + (1 - mana) / 0.6 * 0.88))


class Track(Part):
    """The run, pull by pull: a dot per pull at its time, sized by mobs and shaded by your mana going in, "you" over
    the pulls you pulled, breaks dotted, the death pull circled in highlighter; under it your mana line, with the
    slide marked. Hover a dot for its time, mobs and mana."""

    def __init__(self):
        super().__init__()
        self.view, self.duration = PullsView(), 0.0

    def set_view(self, view: PullsView, duration: float):
        self.view, self.duration = view, duration
        self.changed()

    def _x(self, t: float, w: float) -> float:
        dur = self.duration or max((r.end for r in self.view.rows), default=1.0)
        return X0 + (w - RIGHT - X0) * t / dur

    def event(self, ev):
        if ev.type() == QEvent.Type.ToolTip:
            pos, near = ev.pos(), None
            for r in self.view.rows:
                d = math.hypot(pos.x() - self._x(r.start, self.width()), pos.y() - HEAD - LANE)
                if d <= max(radius(r.mobs), 3.6) + 4 and (near is None or d < near[0]):
                    near = (d, r)
            if near is None:
                QToolTip.hideText()
                ev.ignore()
                return True
            r = near[1]
            QToolTip.showText(ev.globalPos(), f"{r.at}: no pack data" if not r.mobs else
                              f"{r.at} · {r.mobs} mob{'s' if r.mobs != 1 else ''} · "
                              f"{'–' if r.mana is None else pct(r.mana)} mana", self)
            return True
        return super().event(ev)

    def draw(self, p, w):
        if p:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            rule(p, 0, 0, w, tok("ln"))
            draw_label_tab(p, 0, 13, "The run, pull by pull")
            self._key(p, w, 13 + 12.5)
            self._track(p, w, HEAD)
        return HEAD + TRACK_H + 12

    def _key(self, p, w, mid):
        """the legend, right of the tab: size = mobs, mana at pull, no pack data"""
        f, mu, ink = font(12, 600, num=True, spacing=0.04), tok("mu"), tok("m-pace")
        rows = self.view.rows
        parts = [("size = mobs", None), (None, [(2.8, 0.12), (5.6, 0.12), (7.4, 0.12)]), ("1 · 4 · 7", None)]
        if any(r.mana is not None for r in rows):
            parts += [None, ("mana at pull 100%", None), (None, [(4.5, a) for a in (0.12, 0.41, 0.71, 1.0)]),
                      ("40%", None)]
        if any(not r.mobs for r in rows):
            parts += [None, (None, None), ("no pack data", None)]

        def width(part):
            if part is None:
                return 14                       # 20 between groups, less the 6 every part gets
            s, dots = part
            return adv(f, s) if s else 7.2 if dots is None else sum(2 * r for r, _ in dots) + 4 * (len(dots) - 1)

        x = w - sum(width(part) + 6 for part in parts) + 6
        base = mid + (QFontMetricsF(f).capHeight()) / 2
        for part in parts:
            if part is not None:
                s, dots = part
                if s:
                    text_at(p, f, mu, x, base, s)
                elif dots is None:
                    self._no_packs(p, QPointF(x + 3.6, mid))
                else:
                    dx = x
                    for r, a in dots:
                        self._dot(p, QPointF(dx + r, mid), r, a, ink, halo=False)
                        dx += 2 * r + 4
            x += width(part) + 6

    @staticmethod
    def _dot(p, c, r, alpha, ink, halo=True):
        if halo:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(tok("bg"))
            p.drawEllipse(c, r + 1.3, r + 1.3)
        fill = tok("m-pace")
        fill.setAlphaF(alpha)
        p.setBrush(fill)
        p.setPen(QPen(ink, 1))
        p.drawEllipse(c, r, r)

    @staticmethod
    def _no_packs(p, c):
        pen = QPen(tok("mu"), 1)
        pen.setDashPattern([2, 2])
        p.setPen(pen)
        p.setBrush(tok("bg"))
        p.drawEllipse(c, 3.6, 3.6)

    def _track(self, p, w, oy):
        v, rows = self.view, self.view.rows
        mu, tx, tx2, ink = tok("mu"), tok("tx"), tok("tx2"), tok("m-pace")
        small, lab = font(11, 500, num=True, spacing=0.02), font(11, 600, num=True, spacing=0.14)
        X, x1, lane = (lambda t: self._x(t, w)), w - RIGHT, oy + LANE

        def mana_y(m):
            return oy + M0 - m * (M0 - M100)

        # 1. labels and the time axis
        text_at(p, lab, mu, 0, oy + 62, "PULLS")
        text_at(p, lab, mu, 0, oy + 122, "MANA")
        dur = self.duration or max((r.end for r in rows), default=1.0)
        step = next((s for s in (60, 120, 300, 600, 900, 1200, 1800, 3600) if dur / s <= 8), 7200)
        text_at(p, small, mu, X0, oy + 216, "0:00")
        for k in range(1, int(dur // step) + 1):
            if k * step <= dur - step / 2:       # not on top of the end time
                s = fmt_time(k * step)
                text_at(p, small, mu, X(k * step) - adv(small, s) / 2, oy + 216, s)
        end = fmt_time(dur)
        text_at(p, small, mu, x1 - adv(small, end), oy + 216, end)
        # 2. the lane: a hairline broken by the breaks (dotted, labelled), each fight a heavy span on it
        brk = [(rows[k - 1], r) for k, r in enumerate(rows)
               if k and r.gap_before_s is not None and r.gap_before_s >= BREAK_S]
        edges = [X0] + [x for a, b in brk for x in (X(a.end), X(b.start))] + [x1]
        for xa, xb in zip(edges[::2], edges[1::2]):
            p.fillRect(QRectF(xa, lane - 0.5, xb - xa, 1), mu)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(mu)
        bf = font(12, 600, num=True, spacing=0.02)
        for (a, b), (_, _, mins) in zip(brk, v.breaks):
            xa, xb = X(a.end) + 3, X(b.start) - 3
            for k in range(int((xb - xa) // 6) + 1):
                p.drawEllipse(QPointF(xa + 6 * k, lane), 1, 1)
            cx, s = (xa + xb) / 2, f"break {mins} min"
            text_at(p, bf, tx2, cx - adv(bf, s) / 2, oy + 82, s)
            if b.mana is not None:
                s = f"back at {pct(b.mana)} mana"
                text_at(p, small, mu, cx - adv(small, s) / 2, oy + 95, s)
        for r in rows:
            p.fillRect(QRectF(X(r.start), lane - 1.5, max(1.0, X(r.end) - X(r.start)), 3), mu)
        # 3. a dotted guide from the death pull down to its mana
        fix = v.fix if v.fix and v.fix.you_died else None
        if fix and fix.mana is not None:
            pen = QPen(mu, 1)
            pen.setDashPattern([1, 3])
            p.setPen(pen)
            p.setOpacity(0.6)
            p.drawLine(QPointF(X(fix.start), oy + 70), QPointF(X(fix.start), mana_y(fix.mana)))
            p.setOpacity(1)
        # 4. the dots, then "you" over your pulls
        for r in rows:
            c = QPointF(X(r.start), lane)
            if r.mobs:
                self._dot(p, c, radius(r.mobs), shade(r.mana), ink)
            else:
                self._no_packs(p, c)
        yf = font(11, 600, num=True)
        for r in rows:
            if r.you_pulled:
                x = X(r.start)
                p.setPen(QPen(tx, 1.2))
                p.drawLine(QPointF(x, oy + 35), QPointF(x, lane - max(radius(r.mobs), 3.6) - 3))
                text_at(p, yf, tx, round(x - adv(yf, "you") / 2), oy + 31, "you")
        # 5. the mana line: the axis, 50% dashed, a line per stretch between breaks (dashed across them)
        p.fillRect(QRectF(X0, oy + M0, x1 - X0, 1), mu)
        pen = QPen(mu, 1)
        pen.setDashPattern([3, 3])
        p.setPen(pen)
        p.setOpacity(0.55)
        p.drawLine(QPointF(X0, mana_y(LOW)), QPointF(x1, mana_y(LOW)))
        p.setOpacity(1)
        for s, y in (("100%", M100), ("50%", mana_y(LOW) - oy), ("0", M0)):
            text_at(p, small, mu, 88 - adv(small, s), oy + y + 4, s)
        lines, cur, bridges = [], [], []
        for k, r in enumerate(rows):
            pt = None if r.mana is None else QPointF(X(r.start), mana_y(r.mana))
            after_break = any(b is r for _, b in brk)
            if after_break or pt is None:
                if after_break and cur and pt is not None:
                    bridges.append((cur[-1], pt))
                if cur:
                    lines.append(cur)
                cur = []
            if pt is not None:
                cur.append(pt)
        lines += [cur] if cur else []
        if not lines:
            text_at(p, font(12), mu, X0 + 8, mana_y(0.75), "no mana in this log")
        p.setBrush(Qt.BrushStyle.NoBrush)
        pen = QPen(ink, 1.6, cap=Qt.PenCapStyle.RoundCap, join=Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        for pts in lines:
            p.drawPolyline(QPolygonF(pts))
        pen.setDashPattern([2 / 1.6, 4 / 1.6])
        p.setPen(pen)
        for a, b in bridges:
            p.drawLine(a, b)
        # 6. the slide: its pulls marked, and a note after the last
        slide = slide_rows(rows)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(ink)
        for r in slide:
            p.drawEllipse(QPointF(X(r.start), mana_y(r.mana)), 2.6, 2.6)
        if slide:
            nf, s = font(12, 500, num=True, spacing=0.02), slide_note(slide)
            last = slide[-1]
            x = min(X(last.start) + 12, x1 - adv(nf, s))
            text_at(p, nf, tx2, x, min(mana_y(last.mana) + 22, oy + 192), s)
        # 7. the page's one highlighter mark: the death pull circled, "died here"
        if fix:
            xs, xe = X(fix.start), X(fix.end)
            cx, rx = (xs + xe) / 2, max(20.0, (xe - xs) / 2 + 12)
            draw_hand_circle(p, QRectF(cx - rx, lane - 14, 2 * rx, 28), tok("hl"), -5)
            tw = adv(hand_font(22), "died here")
            side = 1 if cx + rx + 10 + tw <= w else -1
            ax = cx + rx + 10 if side > 0 else cx - rx - 10 - tw
            draw_hand_note(p, "died here", QPointF(ax, oy + 34), QPointF(cx + rx * 0.4 * side, lane - 16), 22)


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
        return HEAD


class PulledBy(Part):
    """Pulled by, most first: a neutral square, the name in tx and the count; an unknown puller in mu"""

    def __init__(self):
        super().__init__()
        self.pullers: list[tuple[str | None, int]] = []
        self.me: str | None = None

    def set(self, pullers: list[tuple[str | None, int]], me: str | None):
        """me: your name, marked "(you)" """
        self.pullers, self.me = pullers, me
        self.changed()

    def draw(self, p, w):
        y = 10.0
        if p:
            rule(p, 0, y, w, tok("ln"))
        y += 1 + 8
        lf, nf, sf, cf = font(11, 600, num=True, spacing=0.14), font(13), font(12), font(15, 600, num=True)
        items = [[("PULLED BY", lf, "mu", 0)]]        # each a run of (text, font, ink, gap before); None: the square
        for name, n in self.pullers:
            if name is None:
                items.append([("unknown", nf, "mu", 0), (str(n), cf, "tx", 6)])
            else:
                you = [("(you)", sf, "mu", 4)] if name == self.me else []
                items.append([(None, None, "tx2", 0), (name, nf, "tx", 6), *you, (str(n), cf, "tx", 6)])
        x, row = 0.0, 0
        for run in items:
            rw = sum(dx + (8 if s is None else adv(f, s)) for s, f, _, dx in run)
            if x and x + rw > w:
                x, row = 0.0, row + 1
            base = y + row * 26 + 15
            for s, f, ink, dx in run:
                x += dx
                if s is None:
                    if p:
                        p.fillRect(QRectF(x, base - 8, 8, 8), tok(ink))
                    x += 8
                else:
                    x += text_at(p, f, tok(ink), x, base, s)
            x += 20
        return y + row * 26 + 20 + 12


class Runs(QStyledItemDelegate):
    """a table cell drawn as runs on one line, from its RUNS data: (text, kind), kind tx, mu (a note), em (600), tag
    (a kind tag) or sq (the neutral square before a name)"""
    STYLE = {"tx": (13, 400, "tx"), "mu": (12, 400, "mu"), "em": (13, 600, "tx")}

    def _draw(self, p, runs, x, r: QRectF) -> float:
        """runs from x, on r's middle; returns their width"""
        x0, base = x, baseline(font(13), r.y(), r.height())
        tf = font(11, 600, num=True, spacing=0.14)
        for k, (s, kind) in enumerate(runs):
            x += 6 if k else 0
            if kind == "sq":
                if p:
                    p.fillRect(QRectF(x, base - 8, 8, 8), tok("tx2"))
                x += 8
            elif kind == "tag":         # as kit.tag draws it
                s, top = s.upper(), r.center().y() - 9
                tw = adv(tf, s) + 14
                if p:
                    box(p, QRectF(x, top, tw, 18), tok("ln"))
                    line(p, tf, tok("mu"), x + 7, top + 4, 11, s)
                x += tw
            else:
                px, weight, ink = self.STYLE[kind]
                x += text_at(p, font(px, weight), tok(ink), x, base, s)
        return x - x0

    def paint(self, p, opt, idx):
        runs = idx.data(RUNS)
        if not runs:
            super().paint(p, opt, idx)
            return
        o = QStyleOptionViewItem(opt)
        self.initStyleOption(o, idx)
        o.text = ""
        (o.widget.style() if o.widget else QApplication.style()).drawControl(
            QStyle.ControlElement.CE_ItemViewItem, o, p, o.widget)
        p.save()
        self._draw(p, runs, opt.rect.x() + 6, QRectF(opt.rect))
        p.restore()

    def sizeHint(self, opt, idx):
        hint = super().sizeHint(opt, idx)
        runs = idx.data(RUNS)
        if runs:
            hint.setWidth(math.ceil(self._draw(None, runs, 0, QRectF(0, 0, 0, hint.height()))) + 12)
        return hint


class DrawerRow(QWidget):
    """the All pulls drawer's header, between rules"""

    def __init__(self, drawer: Drawer):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 12, 0, 12)
        lay.addWidget(drawer)
        lay.addStretch(1)

    def paintEvent(self, _ev):
        p = QPainter(self)
        rule(p, 0, 0, self.width(), tok("ln"))
        rule(p, 0, self.height() - 1, self.width(), tok("ln"))


class PullsTab(QScrollArea):
    """the Pulls tab: the page, scrolling when the window is small or the drawer is open"""
    zoom = pyqtSignal(float, float)       # a pull picked in the drawer: the timeline readies there, the tab stays
    show_me = pyqtSignal(float, float)    # "Show this pull": the Timeline tab, zoomed to it

    def __init__(self):
        super().__init__()
        self.a = None
        self.view = PullsView()
        self.narrow = None
        self.page = Sheet()
        self.hero, self.plate = Hero(), Plate("Pull to fix")
        self.hero.unit = (48, 42, 600, 12, 6)
        self.hero.setMaximumWidth(VERDICT_W)
        self.plate.setFixedWidth(PLATE_W)
        self.plate.clicked.connect(lambda: self.view.fix and self.show_me.emit(*self._window(self.view.fix)))
        self.track, self.safety, self.figures, self.pulled = Track(), SectionHead("Pull safety", "preview"), \
            KeyFigures(), PulledBy()
        # the drawer: every pull, and the picked pull's mobs under them
        self.table = table(["#", "At", "Fight", "Mobs", "Packs", "Pulled by", "Your health", "Your mana",
                            "Gap before", "Length", "Died"], stretch=2)
        self.table.setItemDelegate(Runs(self.table))
        self.table.itemSelectionChanged.connect(self._pick)
        mobs = QWidget()
        ml = QVBoxLayout(mobs)
        ml.setContentsMargins(0, 12, 0, 0)
        self.mob_head = QLabel("Pick a pull")
        self.mob_head.setObjectName("title")
        self.mob_sub = dim_label()
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Mob", "Marker", "Went for", "Died", "Kill #", "Killed by"])
        self.tree.header().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for wd in (self.mob_head, self.mob_sub):
            ml.addWidget(wd)
        ml.addWidget(self.tree, 1)
        ml.addWidget(dim_label("Who pulled: the first player to touch the mob (an ability, or \"body pull\" when the mob "
                               "attacked first). \"Went for\" is the first player it hit: the log has no threat data, "
                               "so that's a good guess at its first target, not a certainty."))
        body = QSplitter(Qt.Orientation.Vertical)
        body.addWidget(self.table)
        body.addWidget(mobs)
        body.setSizes([380, 260])
        body.setFixedHeight(BODY_H)
        self.drawer = Drawer("All pulls", body)

        hero_row = QHBoxLayout()
        hero_row.setContentsMargins(0, 14, 0, 16)
        hero_row.setSpacing(0)
        hero_row.addWidget(self.hero, 100, Qt.AlignmentFlag.AlignTop)   # to its verdict's width, then the gap grows
        hero_row.addSpacing(28)
        hero_row.addStretch(1)
        hero_row.addWidget(self.plate, 0, Qt.AlignmentFlag.AlignTop)
        lay = QVBoxLayout(self.page)
        lay.setContentsMargins(16, 4, 16, 16)
        lay.setSpacing(0)
        lay.addSpacing(HEAD_H)
        lay.addLayout(hero_row)
        for wd in (self.track, self.safety, self.figures, self.pulled, DrawerRow(self.drawer), body):
            lay.addWidget(wd)
        lay.addStretch(1)
        self.setWidget(self.page)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)

    @staticmethod
    def _window(r) -> tuple[float, float]:
        return r.start - 3, r.end + 3

    def set_analysis(self, a):
        self.a = a
        if not a:
            self.show_view(PullsView(), "No run selected", "", 0.0)
            return
        self.show_view(build_pulls(a), a.data.run.zone, run_meta(a), a.data.duration)

    def show_view(self, view: PullsView, title: str, sub: str, duration: float):
        self.view = view
        self.page.title, self.page.sub = title, sub
        self.hero.set(str(view.total) if view.rows else "–", "pull" if view.total == 1 else "pulls", None, None,
                      view.verdict)
        head, price, caption, advice = fix_plate(view.fix)
        self.plate.set(head, price, caption, "Show this pull" if view.fix else None, [(advice, "")] if advice else [])
        self.track.set_view(view, duration)
        self.figures.set(safety_figures(view))
        self.pulled.set(view.pullers, next((r.pulled_by for r in view.rows if r.you_pulled), None))
        for part in (self.track, self.safety, self.figures, self.pulled):
            part.setVisible(bool(view.rows))
        self.drawer.set_count(view.total)
        self._fill_table()
        self.page.update()

    def _fill_table(self):
        t = self.table
        t.blockSignals(True)
        t.setRowCount(0)
        bold = QFont()
        bold.setBold(True)
        for k, r in enumerate(self.view.rows):
            t.insertRow(k)
            fight = ([(r.label, "tx")] if r.boss else []) + [("Boss" if r.boss else "Trash", "tag")] + \
                ([("you died", "em")] if r.you_died else [])
            packs = [(str(r.packs), "tx")] + ([(f"{r.extra_packs} joined", "mu")] if r.extra_packs else []) \
                if r.packs else [("—", "tx")]
            who = [("", "sq"), (r.pulled_by, "tx")] if r.pulled_by else [("unknown", "mu")]
            cells = [(r.n, None), (r.at, None), (" ".join(s for s, _ in fight), fight), (r.mobs or "—", None),
                     (" ".join(s for s, _ in packs), packs), (r.pulled_by or "unknown", who),
                     ("—" if r.hp is None else pct(r.hp), None), ("—" if r.mana is None else pct(r.mana), None),
                     ("—" if r.gap_before_s is None else fmt_time(r.gap_before_s), None), (f"{r.length_s} s", None),
                     (", ".join(r.died) or "—", None)]
            for col, (text, runs) in enumerate(cells):
                it = item(text, align_right=col in (0, 1, 3, 6, 7, 8, 9), data=k if col == 0 else None)
                if runs:
                    it.setData(RUNS, runs)
                if col == 7 and r.mana is not None and r.mana < LOW:
                    it.setFont(bold)
                t.setItem(k, col, it)
        t.blockSignals(False)
        self._mobs(None)

    def _pick(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        k = self.table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        self._mobs(k)
        self.zoom.emit(*self._window(self.view.rows[k]))

    def _mobs(self, k: int | None):
        """pull k's packs and mobs in the tree beside the table (None: nothing picked yet)"""
        self.tree.clear()
        a = self.a
        if k is None or not a or k >= len(a.pulls):
            self.mob_head.setText("Pick a pull")
            self.mob_sub.setText("")
            return
        pl = a.pulls[k]
        self.mob_head.setText(pl.fight.label + (" - killed" if pl.fight.killed else
                                                " - wipe" if pl.fight.killed is False else ""))
        n_dead = sum(1 for e in pl.enemies if e.died is not None)
        self.mob_sub.setText(f"at {fmt_time(pl.start)} · {pl.fight.end - pl.start:.0f}s · {len(pl.enemies)} mobs in "
                             f"{len(pl.packs)} pack{'s' if len(pl.packs) != 1 else ''} · {n_dead} killed")
        order = {en.guid: n for n, en in enumerate(pl.kill_order, 1)}
        name = lambda g: a.roster[g].name if g in a.roster else "-"  # noqa: E731
        bold = QFont()
        bold.setBold(True)
        for i, pk in enumerate(pl.packs, 1):
            top = QTreeWidgetItem([f"{'Extra pack' if pk.extra else 'Pack'} {i} at {fmt_time(pk.start)} - "
                                   f"{name(pk.puller) if pk.puller else '?'} ({pk.how})"])
            top.setFont(0, bold)
            for en in pk.enemies:
                died = f"{fmt_time(en.died)} (+{en.died - pl.start:.0f}s)" if en.died is not None else "alive"
                killer = name(en.killer) + (f" - {en.killing_blow}" if en.killing_blow else "") if en.killer else "-"
                child = QTreeWidgetItem([en.name, en.marker or "", name(en.first_target), died,
                                         str(order.get(en.guid, "")), killer])
                if en.marker and (mi := assets.icon(assets.marker_name(en.marker) or "")) is not None:
                    child.setIcon(1, mi)
                top.addChild(child)
            self.tree.addTopLevelItem(top)
            top.setFirstColumnSpanned(True)
            top.setExpanded(True)

    def resizeEvent(self, ev):
        narrow = self.window().width() < NARROW      # the mock-up's smaller hero and figures
        if narrow != self.narrow:
            self.narrow = narrow
            for part in (self.hero, self.figures):
                part.narrow = narrow
                part.changed()
        super().resizeEvent(ev)
