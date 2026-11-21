"""The dungeon page's History tab, painted from a HistoryView (see dips_score/dungeon_view.py): your score on every
visit over the grade bands, the best and the last called out; the measure that keeps costing you points on the plate;
each counted measure visit by visit; and every visit in a ruled table (double-click one to open it).

Sizes follow docs/design/mockups/history.html (CSS px). The shared parts come from kit.py.
"""
import math
from collections import Counter
from datetime import date
from itertools import groupby

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QFontMetricsF, QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QScrollArea, QVBoxLayout

from ..debrief import display_name, fmt_time
from ..dungeon_view import UNJUDGED, HistoryView, day, plate_text, trend_note
from . import theme
from .kit import HEAD_H, Part, Plate, Sheet, adv, box, draw_label_tab, elide, font, halo_text, line, rule, text_at
from .theme import tok
from .tokens import ink_for

PLATE_W = 420
BANDS = (("S", 90, 100), ("A", 80, 90), ("B", 70, 80), ("C", 60, 70), ("D", 45, 60))
VIEW_W = 640        # the mock-up's chart is drawn 640 x 330: x stretches with the page, y stays
TAB_GAP = 4         # under a label tab, before what it names


def dot(p: QPainter, c: QPointF, r: float, fill, edge, width: float):
    p.setBrush(fill)
    p.setPen(QPen(edge, width))
    p.drawEllipse(c, r, r)


class ScoreLine(Part):
    """Score over visits: each scored visit's score, oldest left, joined over the grade bands (S to D, and F under them
    when a score is there); the best and the last called out; a visit too short to compare as a hollow muted dot at its
    card's score, off the line (R10); a visit with no score at all on the floor, muted"""

    def __init__(self):
        super().__init__()
        self.view = HistoryView()
        # as last painted: the best's dot, where its words went ("over", "under", "stacked"; None: left out) and their
        # box, and the boxes of the last's words
        self.best_dot: QPointF | None = None
        self.best_at: str | None = None
        self.best_rect: QRectF | None = None
        self.last_rects: list[QRectF] = []

    def set_view(self, v: HistoryView):
        self.view = v
        n = sum(x.score is not None for x in v.visits)
        self.setAccessibleName(f"Score per visit, {n} scored visit{'' if n == 1 else 's'}")
        self.changed()

    def draw(self, p, w):
        draw_label_tab(p, 0, 0, "Score over visits")
        top = 25 + TAB_GAP
        if p:
            box(p, QRectF(0, top, w, 14 + 330 + 14), tok("ln"), tok("bg"))
            if self.view.visits:
                p.setRenderHint(QPainter.RenderHint.Antialiasing)
                self._chart(p, 16, top + 14, (w - 32) / VIEW_W)
        return top + 14 + 330 + 14

    def _chart(self, p, ox, oy, sx):
        v = self.view
        vs, n = v.visits[::-1], len(v.visits)        # oldest first
        low = min((x.score if x.card_score is None else x.card_score for x in vs
                   if x.score is not None or x.card_score is not None), default=45.0)
        floor = min(45, 5 * math.floor(low / 5))
        bands = BANDS + ((("F", floor, 45),) if floor < 45 else ())

        def X(i: int) -> float:
            return ox + sx * (556 if n == 1 else 44 + i * 512 / (n - 1))

        def Y(s: float) -> float:
            return oy + 20 + (100 - s) * 260 / (100 - floor)

        gf = font(22, 700, num=True)
        for k, (g, lo, hi) in enumerate(bands):
            p.fillRect(QRectF(ox, Y(hi), 600 * sx, Y(lo) - Y(hi)), tok("bg" if k % 2 else "panel"))
            rule(p, ox, Y(hi), 600 * sx, tok("ln"))
            text_at(p, gf, theme.grade_color(g), ox + 612 * sx, (Y(hi) + Y(lo)) / 2 + 8, g)
        rule(p, ox, Y(floor), 600 * sx, tok("tx"))
        # the line through the scored visits, then a dot each: the last in its grade's ink, the best filled
        pts = {i: QPointF(X(i), Y(x.score)) for i, x in enumerate(vs) if x.score is not None}
        p.setPen(QPen(tok("tx"), 2.4, cap=Qt.PenCapStyle.RoundCap, join=Qt.PenJoinStyle.RoundJoin))
        p.drawPolyline(QPolygonF(list(pts.values())))
        for i, q in pts.items():
            if vs[i] is v.last:
                dot(p, q, 9, theme.grade_color(vs[i].grade), tok("bg"), 2.5)
            elif vs[i] is v.best:
                dot(p, q, 6, tok("tx"), tok("bg"), 2)
            else:
                dot(p, q, 4.5, tok("bg"), tok("tx"), 2)
        for i, x in enumerate(vs):
            if x.card_score is not None:
                dot(p, QPointF(X(i), Y(x.card_score)), 4.5, tok("bg"), tok("mu"), 1.5)
        small = font(11)
        for unscored, run in groupby(range(n), key=lambda i: vs[i].score is None and vs[i].card_score is None):
            if unscored:
                run = list(run)
                for i in run:
                    dot(p, QPointF(X(i), Y(floor)), 4, tok("bg"), tok("mu"), 1.5)
                s = "too short" if all(vs[i].note == UNJUDGED for i in run) else "not scored"
                text_at(p, small, tok("mu"), (X(run[0]) + X(run[-1]) - adv(small, s)) / 2, Y(floor) - 18, s)
        self._dates(p, vs, X, Y(floor) + 18)
        self._callouts(p, pts, vs, ox, oy, ox + 600 * sx)

    @staticmethod
    def _dates(p, vs, X, base):
        """under each visit its day, or its time when others that day share it (the day once under them); the last
        visit's time and day in tx 600. A label that would touch the one right of it is left out."""
        n, small, bold = len(vs), font(11), font(11, 600)
        days = Counter(x.when.date() for x in vs[:-1])
        edge = [math.inf, math.inf]         # each line's leftmost label so far (they're placed right to left)

        def put(row: int, cx: float, s: str, f, ink):
            w = adv(f, s)
            if cx + w / 2 + 6 <= edge[row]:
                text_at(p, f, ink, cx - w / 2, base + 14 * row, s)
                edge[row] = cx - w / 2

        for i in range(n - 1, -1, -1):
            x = vs[i]
            if i == n - 1:
                put(0, X(i), f"{x.when:%H:%M}", bold, tok("tx"))
                put(1, X(i), day(x.when), bold, tok("tx"))
                continue
            shared = days[x.when.date()] > 1
            put(0, X(i), f"{x.when:%H:%M}" if shared else day(x.when), small, tok("mu" if x.score is None else "tx2"))
            if shared and (i == 0 or vs[i - 1].when.date() != x.when.date()):      # the first that day
                put(1, (X(i) + X(i + days[x.when.date()] - 1)) / 2, day(x.when), small, tok("tx2"))

    def _callouts(self, p, pts, vs, left, top, right):
        """the last score big in its grade's ink with "Last 75 B · today" and the trend, over and under its dot as the
        mock-up has them, or all on the side with room; then "Best 82 A · 11 Nov" over the best dot, under it, or
        stacked over the last's words: the first that keeps 4px off them and the last's dot, inside the chart (none:
        left out, the best's dot still filled). Each has a halo, so it reads over the line."""
        v, tx = self.view, tok("tx")
        self.best_dot, self.best_at, self.best_rect, self.last_rects = None, None, None, []

        def put(f, ink, x, base, s, draw=True) -> QRectF:
            fm = QFontMetricsF(f)
            if draw:
                halo_text(p, f, ink, x, base, s)
            return QRectF(x, base - fm.ascent(), adv(f, s), fm.ascent() + fm.descent())

        x, keep_off = v.last, []
        if x is not None:
            q = pts[vs.index(x)]
            when = "today" if x.when.date() == date.today() else day(x.when)
            lines = [(font(13, 600), tx, f"Last {x.score:.0f} {x.grade} · {when}")]
            if (t := trend_note(v)) is not None:
                lines.append((font(12), tok("tx2"), t))
            y = q.y() - top
            if 60 <= y and y + 16 + 18 * len(lines) <= 250:      # the mock-up's: the number over the dot, words under
                nb, tb = q.y() - 20, q.y() + 34
            elif y < 60:            # near the top: all under the dot
                nb, tb = q.y() + 50, q.y() + 70
            else:                   # near the floor: all over it
                tb = q.y() - 16 - 18 * (len(lines) - 1)
                nb = tb - 20
            r, big, s = q.x() + 10, font(44, 700, num=True), f"{x.score:.0f}"
            self.last_rects = [put(big, theme.grade_color(x.grade), r - adv(big, s), nb, s)]
            for k, (f, ink, s) in enumerate(lines):
                self.last_rects.append(put(f, ink, r - adv(f, s), tb + 18 * k, s))
            keep_off = self.last_rects + [QRectF(q.x() - 11, q.y() - 11, 22, 22)]
        if v.best is not None and v.best is not v.last:
            q, f = pts[vs.index(v.best)], font(13, 600)
            s = f"Best {v.best.score:.0f} {v.best.grade} · {day(v.best.when)}"
            w, bx = adv(f, s), min(max(left, q.x() - adv(f, s) / 2), right - adv(f, s))
            self.best_dot = q
            spots = [("over", bx, q.y() - 14), ("under", bx, q.y() + 26)]
            if self.last_rects:         # right-aligned with the last's words, over them
                spots.append(("stacked", self.last_rects[0].right() - w,
                              min(o.top() for o in self.last_rects) - 4 - QFontMetricsF(f).descent()))
            for at, sx_, base in spots:
                rect = put(f, tx, sx_, base, s, draw=False)
                if rect.top() >= top and not any(rect.adjusted(-4, -4, 4, 4).intersects(o) for o in keep_off):
                    self.best_at, self.best_rect = at, put(f, tx, sx_, base, s)
                    break


class Measures(Part):
    """Each measure, visit by visit: a cell per counted measure (its name; its last score, big; its score on every
    scored visit in its ink, on a shared 0–100 scale, over the 90 target dashed) and a cell saying how to read them"""
    COLS, CELL_H = 4, 144

    def __init__(self):
        super().__init__()
        self.view = HistoryView()

    def set_view(self, v: HistoryView):
        self.view = v
        self.changed()

    def draw(self, p, w):
        draw_label_tab(p, 0, 0, "Each measure, visit by visit")
        top = 25 + TAB_GAP
        names = list(self.view.series)
        rows = math.ceil((len(names) + 1) / self.COLS)
        h = 1 + rows * (self.CELL_H + 1)
        if p:
            p.fillRect(QRectF(0, top, w, h), tok("ln"))     # the 1px rules round and between the cells
            xs = [round(k * (w - 1) / self.COLS) for k in range(self.COLS + 1)]
            for k in range(rows * self.COLS):
                c = k % self.COLS
                r = QRectF(xs[c] + 1, top + 1 + (k // self.COLS) * (self.CELL_H + 1), xs[c + 1] - xs[c] - 1,
                           self.CELL_H)
                p.fillRect(r, tok("panel"))
                if k < len(names):
                    self._cell(p, r, names[k])
                elif k == len(names):
                    self._key(p, r)
        return top + h

    def _cell(self, p, r: QRectF, name: str):
        vals, ink = self.view.series[name], tok(ink_for(name))
        x0, y, iw = r.x() + 14, r.y() + 10, r.width() - 28
        nf = font(12, 600, num=True, spacing=0.12)
        line(p, nf, tok("tx2"), x0, y, 16, elide(nf, display_name(name).upper(), iw))
        last, m = vals[-1], len(vals)
        # in tx, as the Debrief's measure scores: some inks miss 4.5:1 on panel (Upkeep by day, 4.42)
        line(p, font(44, 700, num=True), tok("mu" if last is None else "tx"), x0, y + 18, 44,
             "–" if last is None else f"{last:.0f}")
        sy = y + 18 + 44 + 4        # the sparkline: the mock-up's 200 x 60, x stretched to the cell

        def X(j: int) -> float:
            return x0 + iw * (192 if m == 1 else 8 + j * 184 / (m - 1)) / 200

        def Y(s: float) -> float:
            return sy + 4 + (100 - s) * 0.52

        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(tok("mu"), 1)
        pen.setDashPattern([4, 3])
        p.setPen(pen)
        p.drawLine(QPointF(x0, Y(90)), QPointF(x0 + iw, Y(90)))
        p.setPen(QPen(ink, 2, cap=Qt.PenCapStyle.RoundCap, join=Qt.PenJoinStyle.RoundJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)
        for missing, run in groupby(range(m), key=lambda j: vals[j] is None):
            if not missing:
                p.drawPolyline(QPolygonF([QPointF(X(j), Y(vals[j])) for j in run]))
        if last is not None:
            dot(p, QPointF(X(m - 1), Y(last)), 4.5, ink, tok("bg"), 1.5)

    @staticmethod
    def _key(p, r: QRectF):
        x0, y = r.x() + 14, r.y() + 10
        line(p, font(12, 600, num=True, spacing=0.12), tok("tx2"), x0, y, 16, "HOW TO READ")
        sy, f = y + 16, font(12)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(tok("mu"), 1)
        pen.setDashPattern([4, 3])
        p.setPen(pen)
        p.drawLine(QPointF(x0 + 6, sy + 14), QPointF(x0 + 40, sy + 14))
        p.setPen(QPen(tok("tx"), 2))
        p.drawLine(QPointF(x0 + 6, sy + 32), QPointF(x0 + 40, sy + 32))
        dot(p, QPointF(x0 + 23, sy + 50), 4.5, tok("tx"), tok("tx"), 1)
        for k, s in enumerate(("target 90", "oldest to newest visit", "latest visit")):
            text_at(p, f, tok("tx2"), x0 + 50, sy + 18 + 18 * k, s)


class VisitTable(Part):
    """Visits, newest first, in a ruled table: a visit not scored is muted, its score cell saying why. Double-click a
    visit to open it (open_run)."""
    open_run = pyqtSignal(str)
    HEADS = ("When", "Length", "In combat", "Score", "Bosses", "Deaths", "Wipes")

    def __init__(self):
        super().__init__()
        self.view = HistoryView()
        self.hits: list[tuple[float, float, str]] = []      # each row's top, bottom and run id, as last laid out
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName("Visits, newest first. Double-click a visit to open it.")

    def set_view(self, v: HistoryView):
        self.view = v
        self.changed()

    def mouseDoubleClickEvent(self, ev):
        y = ev.position().y()
        rid = next((rid for top, bottom, rid in self.hits if top <= y < bottom), None)
        if rid:
            self.open_run.emit(rid)

    @staticmethod
    def _cells(v) -> list[list[tuple[str, object, object]]]:
        """each column's runs of (text, font, ink)"""
        body, ink = font(14), tok("mu" if v.score is None else "tx")

        def plain(s):
            return [(s, body, ink)]
        when = plain(f"{v.when.day} {v.when:%b %H:%M}") + ([(f" · {v.pieces} pieces", font(13), tok("mu"))]
                                                          if v.pieces > 1 else [])
        if v.score is not None:
            score = [(f"{v.score:.0f} ", font(18, 600, num=True), ink),
                     (v.grade, font(18, 700, num=True), theme.grade_color(v.grade))]
        elif v.card_score is not None:      # too short to compare (R10): its card's score, muted
            score = [(f"{v.card_score:.0f} ", font(18, 600, num=True), ink), (v.grade, font(18, 700, num=True), ink),
                     (f" · {v.note}", body, ink)]
        else:
            score = plain(v.note)
        return [when, plain("—" if v.length is None else fmt_time(v.length)),
                plain(fmt_time(v.combat) if v.combat else "—"), score, plain(v.bosses),
                plain("—" if v.deaths is None else str(v.deaths)), plain("—" if v.wipes is None else str(v.wipes))]

    def draw(self, p, w):
        draw_label_tab(p, 0, 0, "Visits")
        y = 25 + TAB_GAP
        hf = font(11, 700, num=True, spacing=0.14)
        rows = [self._cells(v) for v in self.view.visits]
        heads = [h.upper() for h in self.HEADS]
        nat = [max([adv(hf, s) + (13 if k == 0 else 0)] + [sum(adv(f, t) for t, f, _ in r[k]) for r in rows]) + 24
               for k, s in enumerate(heads)]       # each column's widest, padded 12 either side, then stretched to w
        xs = [w * sum(nat[:k]) / sum(nat) for k in range(len(nat))]
        if p:
            rule(p, 0, y, w, tok("tx"))
            for k, s in enumerate(heads):
                tw = line(p, hf, tok("tx2"), xs[k] + 12, y + 11, 11, s)
                if k == 0:
                    self._arrow(p, xs[0] + 12 + tw + 4, y + 11)
            rule(p, 0, y + 32, w, tok("tx"))
        y += 33
        self.hits = []
        for v, cells in zip(self.view.visits, rows):
            if p:
                for k, runs in enumerate(cells):
                    x = xs[k] + 12
                    for s, f, ink in runs:
                        x += line(p, f, ink, x, y + 9, 22, s)
                rule(p, 0, y + 40, w, tok("ln"))
            self.hits.append((y, y + 41, v.run_id))
            y += 41
        y += 8
        if p:
            line(p, font(13), tok("mu"), 0, y, 13 * 1.4, "Double-click a visit to open it.")
        return y + 13 * 1.4 + 6

    @staticmethod
    def _arrow(p, x, top):
        """the mock-up's 9 x 11 arrow: sorted newest first"""
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(tok("tx2"), 1.5))
        p.drawLine(QPointF(x + 4.5, top + 1.5), QPointF(x + 4.5, top + 10))
        p.drawPolyline(QPolygonF([QPointF(x + 1.5, top + 7), QPointF(x + 4.5, top + 10), QPointF(x + 7.5, top + 7)]))
        p.restore()


class HistoryTab(QScrollArea):
    """the History tab: the page, scrolling when the window is small"""
    open_run = pyqtSignal(str)      # a visit double-clicked, or the plate's "Open the last visit"

    def __init__(self):
        super().__init__()
        self.view = HistoryView()
        self.page = Sheet()
        self.chart, self.plate = ScoreLine(), Plate("Recurring fix")
        self.measures, self.table = Measures(), VisitTable()
        self.plate.title_px = 34
        self.plate.setFixedWidth(PLATE_W)
        self.plate.clicked.connect(lambda: self.view.last and self.open_run.emit(self.view.last.run_id))
        self.table.open_run.connect(self.open_run)
        hero = QHBoxLayout()
        hero.setContentsMargins(0, 14, 0, 0)
        hero.setSpacing(28)
        hero.addWidget(self.chart, 1, Qt.AlignmentFlag.AlignTop)
        hero.addWidget(self.plate, 0, Qt.AlignmentFlag.AlignTop)
        lay = QVBoxLayout(self.page)
        lay.setContentsMargins(16, 4, 16, 16)
        lay.setSpacing(0)
        lay.addSpacing(HEAD_H)
        lay.addLayout(hero)
        for part in (self.measures, self.table):
            lay.addSpacing(26)
            lay.addWidget(part)
        lay.addStretch(1)
        self.setWidget(self.page)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)

    def show_view(self, title: str, meta: str, v: HistoryView):
        self.view = v
        self.page.title, self.page.sub = title, meta
        self.chart.set_view(v)
        head, body = plate_text(v)
        self.plate.set(head, None, None, "Open the last visit" if v.recurring else None, [], body)
        self.measures.set_view(v)
        self.measures.setVisible(bool(v.series))
        self.table.set_view(v)
        self.page.update()
