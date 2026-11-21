"""The dungeon page's Bosses tab, painted from build_bosses (see dips_score/dungeon_view.py): today's average boss score
and the weakest boss on the plate; the route, a station per boss with the weakest circled; and each boss in a ruled
row with its score visit by visit. HeroTab, the page the Bosses and Records tabs share, is here too.

Sizes follow docs/design/mockups/bosses.html (CSS px). The shared parts come from kit.py.
"""
from itertools import groupby

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QScrollArea, QVBoxLayout, QWidget

from ..debrief import display_name, fmt_time
from ..dungeon_view import MINUS, BossRow, HistoryView, bosses_text, day, last_word
from ..scoring.score import grade
from . import theme
from .debrief import NARROW
from .historytab import TAB_GAP, dot
from .kit import (HEAD_H, Hero, Part, Plate, Sheet, adv, baseline, box, draw_hand_circle, draw_hand_note,
                  draw_label_tab, elide, font, hand_font, line, rule, text_at, wrapped)
from .theme import tok

PLATE_W = 420
VERDICT_W = 600     # the verdict stops at the mock-up's 600px


def secs(s: float) -> str:
    """a fight's length: "31 s", or "1:42" from 100 s"""
    return f"{s:.0f} s" if s < 100 else fmt_time(s)


class HeroTab(QScrollArea):
    """a dungeon tab's page: its head, the hero beside the plate, then its parts; scrolling when the window is small"""

    def __init__(self, plate: Plate, parts: list[QWidget]):
        super().__init__()
        self.page, self.hero, self.plate, self.narrow = Sheet(), Hero(), plate, None
        self.hero.setMaximumWidth(VERDICT_W)
        plate.setFixedWidth(PLATE_W)
        row = QHBoxLayout()
        row.setContentsMargins(0, 14, 0, 0)
        row.setSpacing(0)
        row.addWidget(self.hero, 100, Qt.AlignmentFlag.AlignTop)    # to its verdict's width, then the gap grows
        row.addSpacing(28)
        row.addStretch(1)
        row.addWidget(plate, 0, Qt.AlignmentFlag.AlignTop)
        lay = QVBoxLayout(self.page)
        lay.setContentsMargins(16, 4, 16, 16)
        lay.setSpacing(0)
        lay.addSpacing(HEAD_H)
        lay.addLayout(row)
        for part in parts:
            lay.addSpacing(26)
            lay.addWidget(part)
        lay.addStretch(1)
        self.setWidget(self.page)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)

    def resizeEvent(self, ev):
        narrow = self.window().width() < NARROW      # the mock-up's smaller hero
        if narrow != self.narrow:
            self.narrow = self.hero.narrow = narrow
            self.hero.changed()
        super().resizeEvent(ev)


class Route(Part):
    """The route: a station per boss in the order you met them (its grade letter in a ring of its ink, its name and
    score), joined by a line; the weakest circled by the highlighter, the tab's one mark"""
    BOX_H = 22 + 52 + 10 + 18 + 4 + 24 + 16

    def __init__(self):
        super().__init__()
        self.rows: list[BossRow] = []
        self.weakest: BossRow | None = None
        self.circled: QRectF | None = None      # the highlighter's ring, as last painted

    def set_rows(self, rows: list[BossRow], weakest: BossRow | None):
        self.rows, self.weakest = rows, weakest
        self.setAccessibleName("The route: " + ", ".join(
            f"{r.name} {r.today:.0f} {r.grade}" if r.today is not None else f"{r.name} {r.missed[-1]}" for r in rows))
        self.changed()

    def draw(self, p, w):
        draw_label_tab(p, 0, 0, "The route")
        top = 25 + TAB_GAP
        if p and self.rows:
            box(p, QRectF(0, top, w, self.BOX_H), tok("ln"), tok("bg"))
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            cw, cy = w / len(self.rows), top + 22 + 26
            if len(self.rows) > 1:
                p.fillRect(QRectF(cw / 2, cy - 1.5, w - cw, 3), tok("tx"))
            gf, nf, sf, mf = font(26, 700, num=True), font(13), font(24, 700, num=True), font(13)
            for k, r in enumerate(self.rows):
                cx, scored = cw * (k + 0.5), r.today is not None
                ink = theme.grade_color(r.grade) if scored else tok("mu")
                dot(p, QPointF(cx, cy), 24.75, tok("bg"), ink, 2.5)
                g = r.grade if scored else "–"
                text_at(p, gf, ink, cx - adv(gf, g) / 2, baseline(gf, cy - 13, 26), g)
                name = elide(nf, r.name, cw - 8)
                line(p, nf, tok("tx"), cx - adv(nf, name) / 2, top + 22 + 52 + 10, 18, name)
                s, f, sink = (f"{r.today:.0f}", sf, tok("tx")) if scored else (r.missed[-1], mf, tok("mu"))
                line(p, f, sink, cx - adv(f, s) / 2, top + 22 + 52 + 10 + 18 + 4, 24, s)
            self.circled = None
            if self.weakest in self.rows:
                cx = cw * (self.rows.index(self.weakest) + 0.5)
                self.circled = QRectF(cx - 40, cy - 35, 80, 70)
                draw_hand_circle(p, self.circled, tok("hl"), -6)
                nw = adv(hand_font(26), "weakest")
                x = cx + 44 if cx + 44 + nw <= w - 8 else cx - 44 - nw      # the last station: on its left
                draw_hand_note(p, "weakest", QPointF(x, top + 22 + 4), None, 26)
        return top + self.BOX_H


class BossTable(Part):
    """Boss by boss: a ruled row per boss (its name; its score on the last visit with the grade in its ink; kill time,
    your DPS and share of damage; its score visit by visit over the dashed 90, the last a big dot in its grade's ink;
    its best), then how to read it"""
    ROW_H = 58

    def __init__(self):
        super().__init__()
        self.rows: list[BossRow] = []
        self.heads: tuple[str, ...] = ()
        self.word = "today"

    def set_rows(self, rows: list[BossRow], span: str, word: str):
        """span: the score column's head; word: what the last visit is called ("today", "18 Nov")"""
        self.rows, self.word = rows, word
        self.heads = ("Boss", "Today" if word == "today" else "Last visit", "Kill time", "Your DPS", "Share of damage",
                      span, "Best")
        self.setAccessibleName("Boss by boss: " + "; ".join(
            f"{r.name} {r.today:.0f} {r.grade}" if r.today is not None else f"{r.name} {r.missed[-1]}" for r in rows))
        self.changed()

    @staticmethod
    def _cells(r: BossRow) -> list[list[tuple[str, object, object]]]:
        """each column's runs of (text, font, ink); the score column's is drawn, so it holds none"""
        body, mu, tx = font(15), tok("mu"), tok("tx")

        def plain(s):
            return [(s, body, tx if s != "–" else mu)]
        today = [(f"{r.today:.0f} ", font(28, 700, num=True), tx), (r.grade, font(20, 700, num=True),
                                                                     theme.grade_color(r.grade))] \
            if r.today is not None else [("–", font(28, 700, num=True), mu)]
        best = [(f"{r.best[0]:.0f} {grade(r.best[0])}", body, mu), (f" · {r.best[1]}", font(12), mu)] if r.best \
            else plain("–")
        return [[(r.name, font(15, 500), tx)], today, plain("–" if r.kill_s is None else secs(r.kill_s)),
                plain("–" if r.dps is None else f"{r.dps:.0f}"),
                plain("–" if r.share is None else f"{r.share:.0%}"), [], best]

    def draw(self, p, w):
        draw_label_tab(p, 0, 0, "Boss by boss")
        y = 25 + TAB_GAP
        hf = font(11, 700, num=True, spacing=0.14)
        heads = [s.upper() for s in self.heads]
        rows = [self._cells(r) for r in self.rows]
        nat = [max([adv(hf, s), 220 if k == 5 else 0] + [sum(adv(f, t) for t, f, _ in c[k]) for c in rows]) + 24
               for k, s in enumerate(heads)]        # each column's widest, padded 12 either side, then stretched to w
        xs = [w * sum(nat[:k]) / sum(nat) for k in range(len(nat))]
        lo = min([70.0] + [5 * (s // 5) for r in self.rows for s in r.history if s is not None])    # shared y-scale
        if p:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            rule(p, 0, y, w, tok("tx"))
            for k, s in enumerate(heads):
                line(p, hf, tok("tx2"), xs[k] + 12, y + 11, 11, s)
            rule(p, 0, y + 32, w, tok("tx"))
        y += 33
        for r, cells in zip(self.rows, rows):
            if p:
                for k, runs in enumerate(cells):
                    if runs:
                        x, base = xs[k] + 12, baseline(runs[0][1], y, self.ROW_H)
                        for s, f, ink in runs:
                            x += text_at(p, f, ink, x, base, s)
                self._spark(p, xs[5] + 12, y + 3, r, lo)
                rule(p, 0, y + self.ROW_H, w, tok("ln"))
            y += self.ROW_H + 1
        y += 10
        last = "today" if self.word == "today" else "the last visit"
        return y + wrapped(p, font(12), tok("mu"), 0, y, w, 12 * 1.4,
                           "Share of damage: yours against an even split of the group's, so 100% is even. "
                           f"Dashed line: 90, the S line. Big dot: {last}.")

    @staticmethod
    def _spark(p, x, y, r: BossRow, lo: float):
        """the mock-up's 220 x 52: the boss's score on each scored visit over the dashed 90; a visit without one as a
        hollow dot on the floor saying why (when there's room); the last a big dot in its grade's ink"""
        vals, n = r.history, len(r.history)

        def X(i: int) -> float:
            return x + (210 if n == 1 else 10 + i * 200 / (n - 1))

        def Y(s: float) -> float:
            return y + 4 + (100 - s) * 40 / (100 - lo)

        pen = QPen(tok("mu"), 1)
        pen.setDashPattern([4, 3])
        p.setPen(pen)
        p.drawLine(QPointF(x, Y(90)), QPointF(x + 220, Y(90)))
        p.setPen(QPen(tok("tx2"), 1.6, join=Qt.PenJoinStyle.RoundJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)
        for missing, run in groupby(range(n), key=lambda i: vals[i] is None):
            if not missing:
                p.drawPolyline(QPolygonF([QPointF(X(i), Y(vals[i])) for i in run]))
        small, edge = font(11), x - 100.0      # edge: the floor row's rightmost dot or word so far
        floor = [i for i in range(n) if vals[i] is None]
        for i in floor:     # each on the floor, saying why right of it (the last: left), when that touches nothing
            dot(p, QPointF(X(i), y + 46), 3.5, tok("bg"), tok("mu"), 1.5)
            why = r.missed[i]
            tw = adv(small, why)
            lx = X(i) - 7 - tw if i == n - 1 else X(i) + 7
            if lx >= edge + 6 and lx + tw <= next((X(j) - 10 for j in floor if j > i), x + 232):
                text_at(p, small, tok("mu"), lx, y + 50, why)
                edge = lx + tw
            edge = max(edge, X(i) + 4)
        for i, s in enumerate(vals):
            if s is None:
                continue
            if i == n - 1:
                dot(p, QPointF(X(i), Y(s)), 5, theme.grade_color(r.grade), tok("bg"), 1.5)
            else:
                dot(p, QPointF(X(i), Y(s)), 2.5, tok("tx2"), tok("tx2"), 0)


class BossesTab(HeroTab):
    """the Bosses tab: the average boss score on the last scored visit, the weakest boss on the plate (Show the fight:
    that visit's timeline, at it), the route, and each boss visit by visit"""
    show_fight = pyqtSignal(str, float, float)      # the last visit's run id, and where its timeline should show

    def __init__(self):
        self.route, self.table = Route(), BossTable()
        super().__init__(Plate("Boss to fix"), [self.route, self.table])
        self.plate.title_px = 34
        self.run_id, self.weakest = "", None
        self.plate.clicked.connect(self._show)

    def _show(self):
        if self.weakest and self.weakest.fight:
            a, b = self.weakest.fight
            pad = max(3.0, (b - a) * 0.08)      # as a fight picked on the Debrief
            self.show_fight.emit(self.run_id, a - pad, b + pad)

    def show_view(self, title: str, meta: str, rows: list[BossRow], weakest: BossRow | None, average: float | None,
                  h: HistoryView):
        """h: the dungeon's history, for the last and first scored visits"""
        scored = [v for v in h.visits if v.score is not None]
        word = last_word(scored[0].when) if scored else "today"
        self.run_id, self.weakest = (scored[0].run_id if scored else ""), weakest
        caption, verdict = bosses_text(rows, weakest, word)
        self.page.title, self.page.sub = title, meta
        self.hero.set("–" if average is None else f"{average:.0f}", None if average is None else grade(average),
                      caption, None, verdict)
        if weakest is None:
            self.plate.set(verdict.rstrip("."), None, None, None, [])
        else:
            lost = weakest.lost
            self.plate.set(f"{weakest.name} · {weakest.today:.0f} {weakest.grade}",
                           f"{MINUS}{lost[0][1]:.1f} points" if lost else None,
                           " · ".join([display_name(lost[0][0])] + [f"then {MINUS}{q:.1f} {display_name(c)}"
                                                                    for c, q in lost[1:2]]) if lost else None,
                           "Show the fight" if weakest.fight else None, [],
                           " · ".join([secs(weakest.kill_s)] + ([f"{weakest.dps:.0f} DPS"] if weakest.dps else [])))
        self.route.set_rows(rows, weakest)
        self.route.setVisible(bool(rows))
        span = f"Score, {day(scored[-1].when)} to {word}" if len(scored) > 1 else "Score by visit"
        self.table.set_rows(rows, span, word)
        self.table.setVisible(bool(rows))
        self.page.update()
