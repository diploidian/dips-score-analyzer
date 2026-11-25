"""The Profile page's Character sheet drawer, painted from a SheetView (dips_score/sheet_view.py): four tabs, Gear (the item
level ladder, then every piece in its rarity's ink), Stats, Abilities, Talents and Legacy.

Sizes follow docs/design/mockups/profile.html, #sheet (CSS px). The shared parts come from kit.py.
"""
from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QPolygonF, QTextLayout
from PyQt6.QtWidgets import QBoxLayout, QButtonGroup, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from ..sheet_view import NA, QUALITY, Ability, Figure, Item, Ladder, SheetView, Talent
from .kit import Part, adv, baseline, box, font, line, rule, text_at, wrapped
from .theme import tok

TWO_COLS = 700              # two columns from this width
GAP = 56                    # between them
TIGHT = 300                 # under it the tabs stand closer
NARROW = 560                # under it the abilities' bars go under their names
SQ, SQ_GAP = 10, 2          # a piece on the ladder


def right_text(p, f, color, right, base, s):
    text_at(p, f, color, right - adv(f, s), base, s)


def tag(p, x, top, s, edge="gold", weight=500) -> float:
    """a 1px frame round a plain fact, 19px high; returns its width"""
    f = font(12, weight)
    w = adv(f, s) + 14
    if p:
        box(p, QRectF(x, top, w, 19), tok(edge))
        line(p, f, tok("tx" if weight > 500 else "tx2"), x + 7, top, 19, s)
    return w


def lead(p, w, y, s) -> float:
    """a tab's sentence; returns its height"""
    return wrapped(p, font(23, 600, num=True), tok("tx"), 0, y, w, 23 * 1.2, s)


def last_line(f, width, s) -> float:
    """how wide the last line of wrapped() is"""
    tl, used = QTextLayout(s, f), 0.0
    tl.beginLayout()
    while (ln := tl.createLine()).isValid():
        ln.setLineWidth(width)
        used = ln.naturalTextWidth()
    tl.endLayout()
    return used


def ink_box(p, r, ink):
    """a piece in its rarity's ink, or an outline when the rarity was not read"""
    if ink:
        p.fillRect(r, tok(ink))
    elif r.width() > 1:
        box(p, r, tok("tx2"))


def heading(p, x, y, s) -> float:
    if p:
        line(p, font(11, 600, num=True, spacing=0.12), tok("mu"), x, y, 12, s.upper())
    return 12 + 5


class Gear(Part):
    def __init__(self):
        super().__init__()
        self.view = SheetView()

    def set(self, v: SheetView):
        self.view = v
        said = lambda i: ", ".join(filter(None, (i.slot, i.name, i.rarity, i.level and f"level {i.level}", i.stats, *i.flags, *i.text)))  # noqa: E731
        ladder = v.ladder and "Item levels: " + "; ".join(f"{lv} {', '.join(s for s, _ in slots)}" for lv, _, slots in v.ladder.marks)
        self.setAccessibleName("Gear: " + ". ".join(x.rstrip(".") for x in filter(None, (
            v.ladder and v.ladder.verdict, ladder, v.wear, v.partly, *map(said, v.gear), not v.gear and "could not be read"))))
        self.changed()

    def draw(self, p, w):
        v, y = self.view, 2.0
        if not v.gear:
            return y + lead(p, w, y, "Your gear could not be read.") + 10
        if v.ladder:
            y += lead(p, w, y, v.ladder.verdict) + 14
            y += self.ladder(p, y, w, v.ladder) + 20
        if v.wear:
            if p:
                line(p, font(14, 600), tok("tx"), 0, y, 20, v.wear)
            y += 28
        if v.partly:
            y += wrapped(p, font(13), tok("tx2"), 0, y, w, 13 * 1.4, v.partly) + 10
        if w < TWO_COLS:
            return self.column(p, 0, y, w, v.gear) + 8
        cw, half = (w - GAP) / 2, len(v.gear) // 2
        return max(self.column(p, 0, y, cw, v.gear[:half]), self.column(p, cw + GAP, y, cw, v.gear[half:])) + 8

    def ladder(self, p, y, w, l: Ladder) -> float:
        nf, lf, mf, bf = font(12, 500), font(14, 600, num=True), font(15, 700, num=True), font(14, 600, num=True)
        tall = max(len(slots) for *_, slots in l.marks)
        axis = y + 17 + tall * (SQ + SQ_GAP)
        at = lambda x: 22 + (w - 44) * x  # noqa: E731
        last = len(l.marks) - 1
        if p:
            rule(p, 0, axis, w, tok("tx"))
            for _, x, slots in l.marks:
                for k, (_, ink) in enumerate(slots):
                    ink_box(p, QRectF(round(at(x)) - SQ // 2, round(axis) - (k + 1) * (SQ + SQ_GAP), SQ, SQ), ink)
            # the two ends first, then what fits beside what is there
            order = [0, last] + [k for k in range(1, last)]
            taken: list[tuple[float, float]] = []
            for k in order:
                lv, x, _ = l.marks[k]
                tw = adv(lf, str(lv))
                x0 = at(x) - tw / 2
                if all(x0 > b + 3 or x0 + tw < a - 3 for a, b in taken):
                    taken.append((x0, x0 + tw))
                    line(p, lf, tok("tx2"), x0, axis + 5, 14, str(lv))
            taken = []
            for k in [0, last] + [k for k in (1, 2, last - 1) if 0 < k < last and w >= TWO_COLS]:
                _, x, slots = l.marks[k]
                name = slots[0][0] + (f" +{len(slots) - 1}" if len(slots) > 1 else "")
                tw = adv(nf, name)
                x0 = min(max(0.0, at(x) - tw / 2), w - tw)
                if all(x0 > b + 6 or x0 + tw < a - 6 for a, b in taken):
                    taken.append((x0, x0 + tw))
                    line(p, nf, tok("tx2"), x0, axis - len(slots) * (SQ + SQ_GAP) - 17, 15, name)
            mx, words = at(l.at), f"average {l.mean}"
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(tok("tx"))
            p.drawPolygon(QPolygonF([QPointF(mx, axis + 22), QPointF(mx + 5, axis + 29), QPointF(mx - 5, axis + 29)]))
            p.setBrush(Qt.BrushStyle.NoBrush)
            line(p, mf, tok("tx"), min(max(0.0, mx - adv(mf, words) / 2), w - adv(mf, words)), axis + 32, 15, words)
        y2 = axis + 32 + 15 + 14
        total, x = sum(n for *_, n in l.rarities), 0.0
        free = w - 2 * max(0, len(l.rarities) - 1)
        sizes = [free * n / total for *_, n in l.rarities] if total else []
        said = [f"{n} {word}" for word, _, n in l.rarities]
        fits = all(adv(bf, s) <= size for s, size in zip(said, sizes))
        for (_, ink, _), size, s in zip(l.rarities, sizes, said):
            if p:
                p.fillRect(QRectF(x, y2, size, 10), tok(ink))
                if fits:
                    line(p, bf, tok("tx2"), x, y2 + 16, 14, s)
            x += size + 2
        if p and not fits:
            line(p, bf, tok("tx2"), 0, y2 + 16, 14, ", ".join(said))
        return y2 + (30 if total else -14) - y

    def column(self, p, x, y, w, items: list[Item]) -> float:
        for i in items:
            y += self.item(p, x, y, w, i)
        return y

    @staticmethod
    def item(p, x, y, w, i: Item) -> float:
        sf, nf, lf, tf = font(12), font(20, 600, num=True), font(24, 700, num=True), font(13)
        gutter = 72 if w < 480 else 84
        bx = x + gutter + 14
        bw = w - gutter - 14 - (adv(lf, i.level) + 14 if i.level else 0)
        y1 = y + 1 + 8
        if p:
            rule(p, x, y, w, tok("ln"))
        if i.empty:
            if p:
                line(p, sf, tok("tx2"), x, y1, 19, i.slot)
                tag(p, bx, y1, "empty", weight=600)
            return 1 + 8 + 19 + 9
        base = baseline(nf, y1, 23)
        h = wrapped(p, nf, tok(i.ink), bx, y1, bw, 23, i.name)
        if p:
            text_at(p, sf, tok("tx2"), x, base, i.slot)
            text_at(p, sf, tok("mu"), x, base + 17, i.rarity)
            if i.level:
                right_text(p, lf, tok("tx"), x + w, base, i.level)
        h += 2
        sw = adv(tf, i.stats)
        tags = sum(adv(font(12, 500), f) + 14 + 10 for f in i.flags)
        inline = i.stats and sw + tags <= bw
        if i.stats:
            h += wrapped(p, tf, tok("tx2"), bx, y1 + h, bw, 13 * 1.4, i.stats)
        tx, ty = (bx + sw + 10, y1 + h - 13 * 1.4) if inline else (bx, y1 + h + (2 if i.flags else 0))
        for f in i.flags:
            tx += tag(p, tx, ty, f, "ln" if f == "lowest" else "gold") + 10
        if i.flags:
            h += 1 if inline else 23
        for s in i.text:
            h += 2 + wrapped(p, tf, tok("tx"), bx, y1 + h + 2, bw, 13 * 1.4, s)
        return 1 + 8 + max(h, 23 + 17) + 9


class Stats(Part):
    def __init__(self):
        super().__init__()
        self.view, self.unread = SheetView(), True

    def set(self, v: SheetView):
        self.view = v
        # nothing of the game's own figures in the snapshot
        self.unread = {t for t, _ in v.stats} <= {"From your fights", "Professions"}
        self.setAccessibleName("Stats: " + ("could not be read. " if self.unread else "") + " ".join(f"{g}: " + "; ".join(", ".join(filter(None, (
            f"{f.name} {f.value}", f.note + (" (estimate)" if f.estimate else "")))) for f in rows) + "." for g, rows in v.stats))
        self.changed()

    def draw(self, p, w):
        groups, y = dict(self.view.stats), 0.0
        if self.unread:
            y += 2 + lead(p, w, 2, "Your stats could not be read.") + 14
        first = [(t, groups[t]) for t in ("From your fights", "Primary") if t in groups]
        rest = [(t, rows) for t, rows in self.view.stats if t not in dict(first)]
        cols = 2 if w >= TWO_COLS else 1
        cw = (w - GAP * (cols - 1)) / cols
        ys = [y] * cols
        for k, (t, rows) in enumerate(first):
            c = k % cols
            ys[c] += self.group(p, c * (cw + GAP), ys[c], cw, t, rows) + 18
        y = max(ys) + 4
        n = 3 if w >= 900 else 2 if w >= 520 else 1
        cw = (w - 40 * (n - 1)) / n
        ys = [y] * n
        for t, rows in rest:                            # each to the shortest column, whole
            c = min(range(n), key=lambda k: ys[k])
            ys[c] += self.group(p, c * (cw + 40), ys[c], cw, t, rows) + 16
        return max(ys)

    def group(self, p, x, y0, w, title, rows) -> float:
        y = y0 + heading(p, x, y0, title)
        if title == "Primary" and any(f.gear or f.buffs is not None for f in rows):
            y += self.key(p, x, y, w) + 8
        for f in rows:
            y += self.figure(p, x, y, w, f, big=title == "From your fights")
        return y - y0

    def key(self, p, x, y, w) -> float:
        kf, cx, cy = font(12), x, y
        rows = dict(self.view.stats).get("Primary", [])
        inks = [i for f in rows for i, n in f.gear if n]
        words = {ink: word for word, ink in QUALITY.values()}
        items = [(i, f"from {words.get(i, 'other')} gear") for i in dict.fromkeys(inks)]
        items.append(("tx2", "your own, without gear or buffs" if any(f.buffs is not None for f in rows) else "your own and buffs"))
        if any(f.buffs for f in rows):
            items.append(("m-upk", "from buffs, enchants and sets"))
        for ink, s in items:
            iw = 8 + 6 + adv(kf, s)
            if cx > x and cx + iw > x + w:
                cx, cy = x, cy + 17
            if p:
                ink_box(p, QRectF(cx, cy + 4, 8, 8), ink)
                line(p, kf, tok("tx2"), cx + 14, cy, 16, s)
            cx += iw + 16
        return cy + 16 - y

    @staticmethod
    def figure(p, x, y, w, f: Figure, big=False) -> float:
        nf, vf, tf = font(15 if big else 14, 500), font(30 if big else 18, 700, num=True), font(12)
        pad, lh = (9, 30) if big else (5, 20)
        y1, vw = y + 1 + pad, adv(vf, f.value)
        base = baseline(vf, y1, lh)
        if p:
            rule(p, x, y, w, tok("ln"))
            right_text(p, vf, tok("mu" if f.value == NA else "tx"), x + w, base, f.value)
        # a long name wraps: its first line shares the value's baseline
        top = base - baseline(nf, 0, 20)
        h = max(lh, top - y1 + wrapped(p, nf, tok("tx"), x, top, w - vw - 12, 20, f.name))
        if f.bar is not None:
            if p:
                by = round(y1 + h + 6)
                p.fillRect(QRectF(x, by, w, 10), tok("track"))
                full, at = w * f.bar, x
                for ink, n in f.gear:
                    if n:
                        ink_box(p, QRectF(at, by, max(0.0, w * n - 2), 10), ink)
                        p.fillRect(QRectF(at + w * n - 2, by, 2, 10), tok("bg"))
                        at += w * n
                own = x + full - w * (f.buffs or 0)
                p.fillRect(QRectF(at, by, max(0.0, own - at), 10), tok("tx2"))
                if f.buffs:
                    p.fillRect(QRectF(own, by, w * f.buffs, 10), tok("bg"))
                    p.fillRect(QRectF(own + 2, by, max(0.0, w * f.buffs - 2), 10), tok("m-upk"))
            h += 6 + 10
        if f.note:
            nh = wrapped(p, tf, tok("tx2"), x, y1 + h + 2, w, 12 * 1.4, f.note)
            h += 2 + nh
            if f.estimate:
                at = last_line(tf, w, f.note) + 10
                if at + adv(font(12, 500), "estimate") + 14 <= w:      # it is the sentence's, not the figure's
                    tag(p, x + at, y1 + h - 18, "estimate", "ln")
                    h += 1
                else:
                    tag(p, x, y1 + h + 3, "estimate", "ln")
                    h += 3 + 19
        return 1 + pad + h + pad + 1


class Abilities(Part):
    def __init__(self):
        super().__init__()
        self.view = SheetView()

    def set(self, v: SheetView):
        self.view = v
        said = lambda a: ", ".join(filter(None, (a.name, a.casts and f"{a.casts} casts", a.share and f"{a.share} of your damage", a.flag)))  # noqa: E731
        self.setAccessibleName("Abilities: " + ". ".join(x.rstrip(".") for x in filter(None, (
            v.lead, *map(said, v.abilities), v.idle, not (v.abilities or v.idle) and "could not be read"))))
        self.changed()

    def draw(self, p, w):
        v, y = self.view, 2.0
        if not (v.abilities or v.idle):
            return y + lead(p, w, y, "Your abilities could not be read.") + 10
        if v.lead:
            y += lead(p, w, y, v.lead) + 14
        bars, rest = [a for a in v.abilities if a.bar is not None], [a for a in v.abilities if a.bar is None]
        if bars:
            y += self.head(p, y, w)
            for a in bars:
                y += self.row(p, y, w, a)
        if rest:
            y += 20
            y += heading(p, 0, y, "Cast, with no damage of their own")
            y += self.rest(p, y, w, rest)
        if v.idle:
            y += 16
            if p:
                rule(p, 0, y, w, tok("tx"))
            y += 10 + wrapped(p, font(14), tok("tx2"), 0, y + 10, w, 14 * 1.4, v.idle)
        return y + 10

    @staticmethod
    def lanes(w) -> tuple[float, float, float]:
        """where the casts end, and the bar begins and ends"""
        name = min(260.0, w * .3)
        return name + 16 + 90, name + 16 + 90 + 16, w - 64 - 16

    def head(self, p, y, w) -> float:
        if p:
            hf = font(11, 600, num=True, spacing=0.12)
            if w < NARROW:
                right_text(p, hf, tok("mu"), w - 64 - 16, baseline(hf, y, 12), "CASTS")
                right_text(p, hf, tok("mu"), w, baseline(hf, y, 12), "SHARE")
            else:
                casts, x0, _ = self.lanes(w)
                right_text(p, hf, tok("mu"), casts, baseline(hf, y, 12), "CASTS IN FIGHTS")
                line(p, hf, tok("mu"), x0, y, 12, "SHARE OF YOUR DAMAGE")
        return 12 + 5

    def row(self, p, y, w, a: Ability) -> float:
        nf, cf, vf = font(14, 500), font(15, 500, num=True), font(20, 700, num=True)
        tight = w < NARROW
        casts, x0, x1 = (w - 64 - 16, 0.0, w) if tight else self.lanes(w)
        y1, room = y + 1 + 5, casts - adv(cf, a.casts) - 12
        flag = adv(font(12, 500), a.flag) + 14 + 10 if a.flag else 0.0
        name_w = adv(nf, a.name)
        below = bool(a.flag) and name_w + flag > room
        nh = wrapped(p, nf, tok("tx"), 0, y1, room, 20, a.name)
        if a.flag:
            tag(p, 0 if below else name_w + 10, y1 + nh + 2 if below else y1, a.flag)
        h = nh + (23 if below else 0)
        by = y1 + h + 5 if tight else y1 + 5
        if p:
            rule(p, 0, y, w, tok("ln"))
            right_text(p, cf, tok("tx"), casts, baseline(cf, y1, 20), a.casts)
            right_text(p, vf, tok("m-dmg"), w, baseline(vf, y1, 20), a.share)
            p.fillRect(QRectF(x0, round(by), x1 - x0, 10), tok("track"))
            p.fillRect(QRectF(x0, round(by), max(1.0, (x1 - x0) * min(1.0, a.bar)), 10), tok("m-dmg"))
        return 1 + 5 + h + (15 if tight else 0) + 5

    @staticmethod
    def rest(p, y, w, rows: list[Ability]) -> float:
        nf, vf = font(14), font(16, 500, num=True)
        n = 3 if w >= 900 else 2 if w >= 520 else 1
        cw, each = (w - 40 * (n - 1)) / n, -(-len(rows) // n)
        for k, a in enumerate(rows):
            x, top = k // each * (cw + 40), y + k % each * 30
            if p:
                rule(p, x, top, cw, tok("ln"))
                line(p, nf, tok("tx"), x, top + 5, 20, a.name)
                right_text(p, vf, tok("tx"), x + cw, baseline(vf, top + 5, 20), a.casts)
        return each * 30


class Talents(Part):
    def __init__(self):
        super().__init__()
        self.view = SheetView()

    def set(self, v: SheetView):
        self.view = v
        said = lambda rows: [f"{t.name} {t.rank} of {t.of}" for t in rows]  # noqa: E731
        self.setAccessibleName("Talents and Legacy: " + ". ".join(x.rstrip(".") for x in filter(None, (
            v.talents_note, *said(v.talents), v.legacy_note, *said(v.legacy),
            not (v.talents or v.legacy or v.talents_note or v.legacy_note) and "could not be read"))))
        self.changed()

    def draw(self, p, w):
        v, y = self.view, 2.0
        if not (v.talents or v.legacy or v.talents_note or v.legacy_note):
            return y + lead(p, w, y, "Your talents could not be read.") + 10
        if v.talents_note:
            y += lead(p, w, y, v.talents_note) + 14
        y += self.rows(p, y, w, v.talents)
        if v.legacy_note:
            y += 16
            if p:
                rule(p, 0, y, w, tok("tx"))
            y += 10 + wrapped(p, font(14), tok("tx2"), 0, y + 10, w, 14 * 1.4, v.legacy_note) + (10 if v.legacy else 0)
        return y + self.rows(p, y, w, v.legacy) + 10

    def rows(self, p, y, w, rows: list[Talent]) -> float:
        n = 2 if w >= TWO_COLS else 1
        cw, each = (w - GAP * (n - 1)) / n, -(-len(rows) // n)
        nf, vf, ink = font(14, 500), font(18, 700, num=True), self.view.ink
        ys = [y] * n
        # every row has its pips or none does: without room, the words alone say it
        pips = cw - 56 - 14 - 15 * max((t.of for t in rows), default=0) >= 106
        for k, t in enumerate(rows):
            c = k // each
            x, top, right = c * (cw + GAP), ys[c], c * (cw + GAP) + cw
            px = right - 56 - 14 - t.of * 15 + 4
            h = wrapped(p, nf, tok("tx"), x, top + 7, (px if pips else right - 56) - x - 12, 20, t.name)
            ys[c] = top + 7 + h + 6
            if not p:
                continue
            rule(p, x, top, cw, tok("ln"))
            right_text(p, vf, tok("tx"), right, baseline(vf, top + 7, 20), f"{t.rank} of {t.of}")
            for j in range(t.of if pips else 0):
                r = QRectF(px + j * 15, top + 11, 11, 11)
                box(p, r, tok(ink if j < t.rank else "tx2"), tok(ink) if j < t.rank else None)
        return max(ys) - y


class Message(Part):
    """what to do before there is a sheet"""
    text = ""

    def draw(self, p, w):
        return 2 + lead(p, w, 2, self.text) + 14


class Head(Part):
    """beside the tabs: when the sheet was read"""
    text = ""

    def draw(self, p, w):
        return max(29.0, 6 + wrapped(p, font(12), tok("tx2"), 0, 6, w, 17, self.text) + 6)


class CharacterSheet(QWidget):
    """the drawer's body: the tabs, when it was read, and the picked tab's part"""
    TABS = (("Gear", Gear), ("Stats", Stats), ("Abilities", Abilities), ("Talents and Legacy", Talents))

    def __init__(self):
        super().__init__()
        self.head, self.message = Head(), Message()
        self.parts: list[Part] = [cls() for _, cls in self.TABS]
        self.buttons = QButtonGroup(self)
        self.bar = QWidget()
        self.bar.setAccessibleName("Character sheet")
        self.row = QBoxLayout(QBoxLayout.Direction.LeftToRight, self.bar)
        self.row.setContentsMargins(0, 2, 0, 14)
        self.row.setSpacing(0)
        row = QHBoxLayout()
        row.setSpacing(0)
        for k, (name, _) in enumerate(self.TABS):
            b = QPushButton(name, checkable=True)
            b.setProperty("tab", "1")
            b.setProperty("last", "1" if k == len(self.TABS) - 1 else "0")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFocusPolicy(Qt.FocusPolicy.TabFocus)       # the focus ring is for the keyboard, as on a Drawer
            b.setMinimumWidth(1)        # the page never scrolls sideways
            self.buttons.addButton(b, k)
            row.addWidget(b)
        row.addStretch(0)
        self.row.addLayout(row)
        self.row.addSpacing(16)
        self.row.addWidget(self.head, 1)
        self.buttons.button(0).setChecked(True)
        self.buttons.idClicked.connect(lambda _k: self._show())
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 8)
        lay.setSpacing(0)
        lay.addWidget(self.message)
        lay.addWidget(self.bar)
        for part in self.parts:
            lay.addWidget(part)
        self.view = SheetView()
        self._show()

    def resizeEvent(self, ev):
        """in a narrow page the date goes under the tabs, in a very narrow one the tabs stand closer"""
        across = QBoxLayout.Direction.LeftToRight if self.width() >= NARROW else QBoxLayout.Direction.TopToBottom
        if self.row.direction() != across:
            self.row.setDirection(across)
        tight = "1" if self.width() < TIGHT else "0"
        for b in self.buttons.buttons():
            if b.property("tight") != tight:
                b.setProperty("tight", tight)
                b.style().unpolish(b)
                b.style().polish(b)
        super().resizeEvent(ev)

    def set(self, v: SheetView):
        self.view = v
        self.head.text = v.taken
        self.head.setAccessibleName(v.taken)
        self.message.text = v.need
        self.message.setAccessibleName(v.need)
        self.message.changed()
        for part in self.parts:
            part.set(v)
        self.head.changed()
        self._show()

    def _show(self):
        there = not self.view.need
        self.message.setVisible(not there)
        self.bar.setVisible(there)
        for k, part in enumerate(self.parts):
            part.setVisible(there and k == self.buttons.checkedId())
