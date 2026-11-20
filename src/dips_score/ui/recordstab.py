"""The dungeon page's Records tab, painted from build_records (see dips_score/dungeon_view.py): your best score here;
the plate saying whether the last visit's top fix would have beaten it, on a 60–100 scale; and the ruled records
board, the first new record circled, with a row to the Bosses tab.

Sizes follow docs/design/mockups/records.html (CSS px). The shared parts come from kit.py.
"""
import math

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QPen, QPolygonF

from ..dungeon_view import BossRow, HistoryView, Record, last_word, records_text
from . import theme
from .bossestab import HeroTab
from .historytab import TAB_GAP
from .kit import GRADES, Part, Plate, adv, baseline, box, draw_hand_circle, draw_label_tab, elide, font, line, rule, \
    text_at, wrapped
from .theme import tok


class ReachPlate(Plate):
    """the Within reach plate: its title, then (with a scale) the last visit's score, your best and that score with
    its top fix on a 60–100 scale (lower when the score is), a rule, and the button"""

    def __init__(self):
        super().__init__("Within reach")
        self.title_px = 30
        self.scale: tuple[float, float, float] | None = None       # the last score, the best, the last with the fix
        self.now = "today"         # what the last score is called under the scale ("last visit": not today)

    def draw(self, p, w, wrap=None):
        if self.scale is None:
            return super().draw(p, w, wrap)
        x, cw = 18, w - 36
        y = 12 + 22 + wrapped(p, font(30, 600, num=True), tok("plate-tx"), x, 12 + 22, cw, 30 * 1.15, self.title)
        y = self._scale(p, x, y + 14, cw) + 16
        if p:
            rule(p, x, y, cw, tok("plate-ln"))
        self.button_y = y + 1 + 16
        return (self.button_y + self.button.sizeHint().height() if self.has_button else y + 1) + 14

    def _scale(self, p, x, y, cw) -> float:
        """the mock-up's 56px scale from y: a 8px track, the last score filled in plate-tx and the fix after it in
        plate-ac, the best a 2px tick; "best 82" over it, the ends and "today 75" (self.now) and "with the fix 86"
        under it"""
        t, b, f = self.scale
        lo = min(60.0, 10 * math.floor(t / 10))

        def X(s: float) -> float:
            return x + cw * (min(s, 100) - lo) / (100 - lo)
        if p:
            box(p, QRectF(x, y + 22, cw, 8), tok("plate-ln"))
            p.fillRect(QRectF(x, y + 22, X(t) - x, 8), tok("plate-tx"))
            p.fillRect(QRectF(X(t), y + 22, X(f) - X(t), 8), tok("plate-ac"))
            p.fillRect(QRectF(X(b) - 1, y + 15, 2, 22), tok("plate-tx"))
            words, num = font(12), font(14, 700, num=True)

            def width(s, n):
                return adv(words, s + " ") + adv(num, n)

            def put(left, base, s, n=""):
                text_at(p, num, tok("plate-tx"), left + text_at(p, words, tok("plate-mu"), left, base, s + " "),
                        base, n)

            def centred(c, s, n):
                return min(max(x, c - width(s, n) / 2), x + cw - width(s, n))

            put(centred(X(b), "best", f"{b:.0f}"), y + 13, "best", f"{b:.0f}")
            fix, today = f"{min(f, 100):.0f}", f"{t:.0f}"
            tl = centred(X(t), self.now, today)
            fl = min(max(centred(X(f), "with the fix", fix), tl + width(self.now, today) + 10),
                     x + cw - width("with the fix", fix))
            tl = min(tl, fl - 10 - width(self.now, today))       # no room right of today: today moves left
            put(tl, y + 51, self.now, today)
            put(fl, y + 51, "with the fix", fix)
            ends = f"{lo:.0f}", "100"
            if x + adv(words, ends[0]) + 10 <= tl:
                text_at(p, words, tok("plate-mu"), x, y + 51, ends[0])
            if fl + width("with the fix", fix) + 10 <= x + cw - adv(words, ends[1]):
                text_at(p, words, tok("plate-mu"), x + cw - adv(words, ends[1]), y + 51, ends[1])
        return y + 56


class Board(Part):
    """Your records here: a ruled row per record (its name and what counts; the record, when it was set, the last
    visit's, and how that did against it), the first new record circled by the highlighter, the tab's one mark; then
    a row to the Bosses tab"""
    to_bosses = pyqtSignal()
    COLS = (0.26, 0.17, 0.13, 0.13, 0.31)       # the mock-up's widths
    ROW_H, LINK_H = 54, 44

    def __init__(self):
        super().__init__()
        self.records: list[Record] = []
        self.bosses: list[BossRow] = []
        self.word = "today"
        self.circled: int | None = None         # the record circled, as last painted
        self.link_y: float | None = None        # the Bosses row's top, as last laid out
        self.setMouseTracking(True)

    def set_records(self, records: list[Record], bosses: list[BossRow], word: str):
        """word: what the last visit is called ("today", "18 Nov")"""
        self.records, self.bosses, self.word = records, bosses, word
        self.setAccessibleName("Your records here: " + "; ".join(
            f"{r.name} {r.value}, {r.when}, {r.status.replace(' · ', ', ')}" for r in records))
        self.changed()

    def _on_link(self, y: float) -> bool:
        return self.link_y is not None and self.link_y <= y < self.link_y + self.LINK_H

    def mousePressEvent(self, ev):
        if self._on_link(ev.position().y()):
            self.to_bosses.emit()

    def mouseMoveEvent(self, ev):
        self.setCursor(Qt.CursorShape.PointingHandCursor if self._on_link(ev.position().y())
                       else Qt.CursorShape.ArrowCursor)

    def draw(self, p, w):
        draw_label_tab(p, 0, 0, "Your records here")
        y = 25 + TAB_GAP
        xs = [w * sum(self.COLS[:k]) for k in range(len(self.COLS))]
        if p:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            hf = font(11, 700, num=True, spacing=0.14)
            rule(p, 0, y, w, tok("tx"))
            for k, s in enumerate(("Record", "Best", "When", "Today" if self.word == "today" else "Last visit",
                                   "Status")):
                line(p, hf, tok("tx2"), xs[k] + 12, y + 11, 11, s.upper())
            rule(p, 0, y + 32, w, tok("tx"))
        y += 33
        first = next((i for i, r in enumerate(self.records) if r.new_today), None)
        self.circled = first
        for i, r in enumerate(self.records):
            if p:
                self._row(p, xs, y, w, r, i == first)
                rule(p, 0, y + self.ROW_H, w, tok("ln"))
            y += self.ROW_H + 1
        self.link_y = y if self.bosses else None
        if self.bosses:
            if p:
                self._link(p, y, w)
                rule(p, 0, y + self.LINK_H, w, tok("ln"))
            y += self.LINK_H + 1
        return y

    @staticmethod
    def _figure(p, f, ink, x, base, s, unit_f) -> float:
        """s's figure in f, then a grade letter in its ink (same size) or a unit in unit_f, muted; returns its end"""
        fig, _, rest = s.partition(" ")
        x += text_at(p, f, ink, x, base, fig)
        if rest in GRADES:
            return x + text_at(p, f, theme.grade_color(rest), x + adv(f, " "), base, rest) + adv(f, " ")
        return x + (5 + text_at(p, unit_f, tok("mu"), x + 5, base, rest) if rest else 0)

    def _row(self, p, xs, y, w, r: Record, circle: bool):
        nx, nw = xs[0] + 12, xs[1] - xs[0] - 24
        nf = font(15, 500)
        if r.note:
            line(p, nf, tok("tx"), nx, y + 8, 21, elide(nf, r.name, nw))
            line(p, font(12), tok("mu"), nx, y + 8 + 21, 17, elide(font(12), r.note, nw))
        else:
            line(p, nf, tok("tx"), nx, y, self.ROW_H, elide(nf, r.name, nw))
        vf, h = font(30, 700, num=True), self.ROW_H     # each cell centred in the row, as the mock-up's
        self._figure(p, vf, tok("mu" if r.value == "–" else "tx"), xs[1] + 12, baseline(vf, y, h), r.value,
                     font(13, 500))
        latest = r.when == self.word
        wf = font(14, 600 if latest else 400)
        text_at(p, wf, tok("tx" if latest else "tx2"), xs[2] + 12, baseline(wf, y, h), r.when)
        tf = font(18, 600, num=True)
        if r.today.split(" ")[-1] in GRADES:
            self._figure(p, tf, tok("tx2"), xs[3] + 12, baseline(tf, y, h), r.today, tf)
        else:
            text_at(p, tf, tok("tx2"), xs[3] + 12, baseline(tf, y, h), r.today)
        head, _, aside = r.status.partition(" · ")
        sf = font(16, 700 if r.new_today else 600, num=True, spacing=0.03)
        sx, base = xs[4] + 12, baseline(sf, y, h)
        hw = text_at(p, sf, tok("tx" if r.new_today else "tx2"), sx, base, head)
        if aside:
            text_at(p, font(12), tok("mu"), sx + hw + (32 if circle else 14), base,
                    elide(font(12), aside, w - sx - hw - 46))
        if circle:      # the highlighter round the first new record
            draw_hand_circle(p, QRectF(sx - 14, y + self.ROW_H / 2 - 17, hw + 28, 34), tok("hl"), -3)

    def _link(self, p, y, w):
        """"Best on each boss (6) · today 5 of 6 at S", and "Bosses tab" on the right"""
        n = len(self.bosses)
        s = sum(r.today is not None and r.grade == "S" for r in self.bosses)
        mid, bf = y + self.LINK_H / 2, font(14, 500)
        base = baseline(bf, y, self.LINK_H)
        p.setPen(QPen(tok("tx2"), 1.6))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPolyline(QPolygonF([QPointF(15, mid - 4), QPointF(19, mid), QPointF(15, mid + 4)]))
        x = 31 + text_at(p, bf, tok("tx"), 31, base, "Best on each boss")
        when = "today" if self.word == "today" else f"on {self.word}"
        text_at(p, font(14), tok("mu"), x + 4, base, f"({n}) · {s} of {n} at S {when}")
        uf = font(14)
        uf.setUnderline(True)
        text_at(p, uf, tok("tx2"), w - 12 - adv(uf, "Bosses tab"), base, "Bosses tab")


class RecordsTab(HeroTab):
    """the Records tab: your best score here, Within reach (Open the last visit when its top fix would have beaten
    it), and the records board"""
    open_run = pyqtSignal(str)      # the plate's "Open the last visit"
    to_bosses = pyqtSignal()        # the board's Bosses row

    def __init__(self):
        self.board = Board()
        super().__init__(ReachPlate(), [self.board])
        self.view = HistoryView()
        self.plate.clicked.connect(lambda: self.view.last and self.open_run.emit(self.view.last.run_id))
        self.board.to_bosses.connect(self.to_bosses)

    def show_view(self, title: str, meta: str, records: list[Record], within: tuple[str, str] | None,
                  h: HistoryView, bosses: list[BossRow]):
        """h: the dungeon's history (its best and last); bosses: build_bosses' rows, for the Bosses row"""
        self.view = h
        t, b = h.last, h.best
        word = last_word(t.when) if t else "today"
        verdict, title_, body = records_text(h, within, word)
        self.page.title, self.page.sub = title, meta
        self.hero.set("–" if b is None else f"{b.score:.0f}", None if b is None else b.grade,
                      None if b is None else f"Best score here · {last_word(b.when)}", None, verdict)
        # within reach: the last score, the best, and the last with its top fix (its card's most points lost)
        self.plate.scale = (t.score, b.score, t.score + next(iter(t.lost.values()))) if within else None
        self.plate.now = "today" if word == "today" else "last visit"
        self.plate.set(title_, None, None, "Open the last visit" if within else None, [], body)
        self.board.set_records(records, bosses, word)
        self.board.setVisible(bool(records))
        self.page.update()
