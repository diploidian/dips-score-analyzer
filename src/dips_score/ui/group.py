"""The Group tab's page, painted from a GroupView (see dips_score/group_view.py): where you placed and what would move
you up (the plate), the podium, everyone's card with their map, the awards; then everyone's numbers in the All the
numbers drawer, and their class and role in the Edit roles drawer.

Sizes follow docs/design/mockups/group.html (CSS px). The shared parts come from kit.py, the map from radar.py.
"""
from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QFont, QFontMetricsF, QPen
from PyQt6.QtWidgets import (QAbstractItemView, QComboBox, QFrame, QHBoxLayout, QPushButton, QScrollArea,
                             QVBoxLayout, QWidget)

from .. import names
from ..debrief import fmt_time
from ..group_view import ROLE_WORD, GroupView, PlayerCard, breakdown, build_group, of_line
from ..model.roster import CLASSES, ROLES
from ..scoring.group import ordinal
from . import assets, theme
from .debrief import NARROW
from .kit import (HEAD_H, MINUS, Drawer, Fold, Part, Plate, Sheet, Tips, adv, baseline, box, draw_label_tab, draw_tag, elide,
                  flow, font, line, rule, text_at, wrapped)
from .pages import dim_label, fmt_num, item, run_meta, table
from .radar import H as MAP_H, W as MAP_W, draw_map, map_tips
from .theme import tok

PLATE_W = 400
STEP_W, STEP_GAP = 190, 12
STEP_H = {1: 156, 2: 128, 3: 120}       # the podium's steps
RANK_W, PTS_W, GAP = 80, 96, 24         # a card's columns: rank | who and why | map | points, GAP apart
AWARD_W, HOLDER_W = 220, 340            # the awards list's title and holder columns
SOURCE = {"you": "your pick", "addon": "from the add-on", "spells": "guessed from spells",
          "talents": "from your talents", "?": "unknown"}
# All the numbers: each column's help, and its value in a stat line (model.summary.PlayerStats); higher is "more"
STATS = {
    "Damage": ("damage to enemies, pets included", lambda st: st.damage),
    "DPS": ("damage per second of combat", lambda st: st.dps),
    "On bosses": ("damage during boss fights", lambda st: st.boss_damage),
    "Healing": ("healing that landed (overhealing not counted)", lambda st: st.healing),
    "Overheal": ("share of their healing that was wasted on full health", lambda st: st.overheal_share),
    "Taken": ("damage they took", lambda st: st.taken),
    "Deaths": ("times they died (Feign Death not counted)", lambda st: st.deaths),
    "Interrupts": ("spell casts they interrupted", lambda st: st.interrupts),
    "Dispels": ("debuffs and buffs they dispelled", lambda st: st.dispels),
    "Killing blows": ("enemies they landed the killing blow on", lambda st: st.killing_blows),
    "Pulls": ("packs they were first to touch", lambda st: st.pulls_started),
}


def _sign(p, x: float, y: float, plus: bool, ink, size: float = 10):
    """the + or − before a strength, a weakness or a roast: in a size x size box, strokes size / 5 wide"""
    p.save()
    p.setPen(QPen(ink, size / 5))
    m, c = size / 10, size / 2
    p.drawLine(QPointF(x + m, y + c), QPointF(x + size - m, y + c))
    if plus:
        p.drawLine(QPointF(x + c, y + m), QPointF(x + c, y + size - m))
    p.restore()


def _mvp(p, x: float, y: float) -> QRectF:
    """the MVP mark: tracked capitals in a 1px gold frame"""
    f = font(11, 700, num=True, spacing=0.16)
    r = QRectF(x, y, adv(f, "MVP") + 12, 19)
    if p:
        box(p, r, tok("gold"))
        line(p, f, tok("tx"), x + 6, y + 4, 11, "MVP")
    return r


def _mod_head(p, title: str, note: list[str | None], gap: float = 6) -> float:
    """a module's label tab, its muted note beside it: parts gap apart, ink to ink (None: a sample of the map's dashed
    average line, 12px after the words before it); returns where its content starts"""
    r = draw_label_tab(p, 0, 0, title)
    if p:
        f = font(13)
        fm = QFontMetricsF(f)
        x, base = r.right() + 14, baseline(f, 0, 25)
        for k, part in enumerate(note):
            if part is None:
                pen = QPen(tok("mu"), 1.4)
                pen.setDashPattern([4 / 1.4, 3 / 1.4])
                p.setPen(pen)
                p.drawLine(QPointF(x + 12, 12.5), QPointF(x + 12 + 25, 12.5))     # 4 on, 3 off: ends on a dash
                x += 12 + 25
            else:
                ink = fm.tightBoundingRect(part)        # the glyphs' own edges, not their advance
                x += gap if k else 0
                text_at(p, f, tok("mu"), x - ink.left(), base, part)
                x += ink.width()
    return 25 + 12


class Placing(Part):
    """the hero: your place, big, its letters raised beside it; and, level with its foot, the "of 5 · …" line and why
    you placed there"""

    def __init__(self):
        super().__init__()
        self.place, self.of, self.reason = None, "", ""

    def set(self, place: int | None, of: str, reason: str):
        self.place, self.of, self.reason = place, of, reason
        self.changed()

    def draw(self, p, w):
        px, spx = (126, 46) if self.narrow else (150, 56)
        f, sf = font(px, 700, num=True, spacing=-0.02), font(spx, 700, num=True)
        of_f, rf = font(21, 600, num=True, spacing=0.04), font(15)
        num = str(self.place) if self.place else "–"
        sup = ordinal(self.place)[len(num):] if self.place else ""
        tx = adv(f, num) + (2 + adv(sf, sup) if sup else 0) + 22
        tw = max(0.0, min(w - tx, 46 * adv(rf, "0")))      # the reason stops at 46ch
        lh, of = px * 0.82, self.of.upper()
        of_h = wrapped(None, of_f, None, 0, 0, max(0.0, w - tx), 21 * 1.15, of)
        text_h = of_h + (8 + wrapped(None, rf, None, 0, 0, tw, 15 * 1.45, self.reason) if self.reason else 0)
        h = max(lh, text_h)
        if p:
            top = 14 + h - lh
            text_at(p, f, tok("tx" if self.place else "mu"), 0, baseline(f, top, lh), num)
            if sup:     # raised to the number's top, 8px down
                line(p, sf, tok("tx"), adv(f, num) + 2, top + 8, spx * 0.82, sup)
            ty = 14 + h - text_h
            wrapped(p, of_f, tok("tx"), tx, ty, max(0.0, w - tx), 21 * 1.15, of)
            if self.reason:
                wrapped(p, rf, tok("tx2"), tx, ty + of_h + 8, tw, 15 * 1.45, self.reason)
        return 14 + h


class Podium(Part):
    """the top three on flat steps, 2nd · 1st · 3rd, on a tx rule; your step outlined in the highlighter"""

    def __init__(self):
        super().__init__()
        self.cards: list[PlayerCard] = []

    def set(self, cards: list[PlayerCard]):
        self.cards = cards
        self.changed()

    def draw(self, p, w):
        y = _mod_head(p, "Podium", ["Placing points = score + 2 per award (max +6)", MINUS, "2 per roast"], 4)
        floor = y + STEP_H[1]
        if p:
            steps = [self.cards[k] for k in (1, 0, 2) if k < len(self.cards)]
            for i, c in enumerate(steps):
                self._step(p, QRectF(i * (STEP_W + STEP_GAP), floor - STEP_H[c.rank], STEP_W, STEP_H[c.rank]), c)
            rule(p, 0, floor, len(steps) * (STEP_W + STEP_GAP) - STEP_GAP, tok("tx"))
        return floor + 1

    @staticmethod
    def _step(p, r: QRectF, c: PlayerCard):
        edge, k = (tok("hl"), 3) if c.you else (tok("ln"), 1)
        p.fillRect(r, tok("panel"))
        for e in (QRectF(r.x(), r.y(), r.width(), k), QRectF(r.x(), r.y(), k, r.height()),
                  QRectF(r.right() - k, r.y(), k, r.height())):      # no edge along the floor
            p.fillRect(e, edge)
        x, y, cw = r.x() + 15, r.y() + 13, r.width() - 30
        line(p, font(34, 700, num=True), tok("tx"), x, y, 34, ordinal(c.rank))
        if c.mvp:
            _mvp(p, r.right() - 13 - _mvp(None, 0, 0).width(), r.y() + 13)
        nf = font(15, 600)
        nw = line(p, nf, tok("tx"), x, y + 34, 21,
                  elide(nf, c.name, cw - (draw_tag(None, 0, 0, "you") + 8 if c.you else 0)))
        if c.you:
            draw_tag(p, x + nw + 8, y + 34 + 10.5, "you")
        line(p, font(12), tok("mu"), x, y + 34 + 21, 12 * 1.4, c.role)
        pf = font(26, 700, num=True)
        base = baseline(pf, r.bottom() - 12 - 26, 26)
        pw = text_at(p, pf, tok("tx"), x, base, f"{c.points:.0f}")
        text_at(p, font(11, 600, num=True, spacing=0.12), tok("mu"), x + pw + 4, base, "POINTS")


class Standings(Tips):
    """everyone's card, best first: rank (and MVP), name, role, why, their strengths (+) and weaknesses (−), award and
    roast chips, their map, and their placing points over score and grade"""

    def __init__(self):
        super().__init__()
        self.cards: list[PlayerCard] = []
        self.average: list[float] | None = None

    def set(self, cards: list[PlayerCard], average: list[float] | None):
        self.cards, self.average = cards, average
        self.changed()

    def draw(self, p, w):
        y = _mod_head(p, "Standings", ["Every member scored from the combat log only. Map: rings at 25, 50, 75, 100",
                                       None, "group average"])
        tips = []
        for k, c in enumerate(self.cards):
            y += 10 if k else 0
            y += self._card(p, y, w, c, tips)
        if p:
            self.tips = tips
        return y

    def _card(self, p, top, w, c: PlayerCard, tips) -> float:
        """one card from top; returns its height"""
        x0, y0 = 21, top + 17           # inside its 1px edge and 20 x 16 padding
        bx = x0 + RANK_W + GAP
        bw = max(120.0, w - 42 - RANK_W - MAP_W - PTS_W - 3 * GAP)
        body = self._body(None, bx, y0, bw, c, [])
        h = max(body, MAP_H, 40.8 + 6 + 11 + 14 + 18)
        if not p:
            return h + 34
        box(p, QRectF(0, top, w, h + 34), tok("ln"), tok("panel"))
        line(p, font(40, 700, num=True), tok("tx"), x0, y0, 36, ordinal(c.rank))
        if c.mvp:
            _mvp(p, x0, y0 + 36 + 8)
        self._body(p, bx, y0, bw, c, tips)
        mx, my = bx + bw + GAP, y0 + (h - MAP_H) / 2
        if c.radar:
            draw_map(p, mx, my, c.radar, self.average, c.you)
            tips += map_tips(mx, my, c.radar, c.details, self.average)
        else:
            line(p, font(13), tok("mu"), mx, y0 + (h - 18) / 2, 18, "no map for this run")
        right = w - 21
        pf, sf = font(48, 700, num=True), font(11, 600, num=True, spacing=0.14)
        gf, sc = font(16, 700, num=True), font(13)
        pts = f"{c.points:.0f}"
        line(p, pf, tok("tx"), right - adv(pf, pts), y0, 40.8, pts)
        line(p, sf, tok("mu"), right - adv(sf, "POINTS"), y0 + 40.8 + 6, 11, "POINTS")
        base = baseline(gf, y0 + 40.8 + 6 + 11 + 14, 18)
        gw = text_at(p, gf, theme.grade_color(c.grade), right - adv(gf, c.grade), base, c.grade)
        sw = text_at(p, sc, tok("mu"), right - gw - 2 - adv(sc, f"score {c.score:.0f}"), base, f"score {c.score:.0f}")
        tips.append((QRectF(right - gw - 2 - sw, base - 16, gw + 2 + sw, 22), c.breakdown))
        return h + 34

    @staticmethod
    def _body(p, x, y, w, c: PlayerCard, tips) -> float:
        """the who-and-why column: the name line, why, the +/− rows, the chips; returns its height"""
        nf, rf, f, bf = font(17, 600), font(14), font(14), font(14, 600)
        top = y
        if p:
            nw = line(p, nf, tok("tx"), x, y, 23.8, elide(nf, c.name, w * 0.6))
            base = baseline(nf, y, 23.8)
            rw = text_at(p, rf, tok("mu"), x + nw + 10, base, c.role)
            if c.you:
                draw_tag(p, x + nw + 10 + rw + 10, y + 23.8 / 2, "you")
        y += 23.8 + 3
        y += wrapped(p, f, tok("tx2"), x, y, w, 14 * 1.4, c.reason)
        rows = [(True, s) for s in c.plus] + [(False, s) for s in c.minus]
        if rows:
            y += 10
            if p:
                rule(p, x, y, w, tok("ln"))
            y += 1
            space = adv(f, " ")
            for plus, (name, evidence) in rows:
                items = [(f"{name}:", bf, tok("tx"))] + [(s, f, tok("tx2")) for s in evidence.split()]
                rh = flow(p, items, x + 20, y + 5 + 1.4, w - 20, space, 2.8) + 2.8
                if p:
                    _sign(p, x, y + 5 + 5, plus, tok("m-dmg" if plus else "gD"))
                y += 5 + rh + 5
                if p:
                    rule(p, x, y, w, tok("ln"))
                y += 1
        if c.awards:
            y += 12
            cf = font(12, 600)
            cx, row = x, 0
            for title, good, tip in c.awards:
                cw = adv(cf, title) + 18 + (0 if good else 8 + 6)
                if cx > x and cx + cw > x + w:
                    cx, row = x, row + 1
                r = QRectF(cx, y + row * (25 + 6), cw, 25)
                if p:
                    box(p, r, tok("gold" if good else "gD"))
                    tx = r.x() + 9
                    if not good:
                        _sign(p, tx, r.center().y() - 4, False, tok("gD"), 8)
                        tx += 8 + 6
                    line(p, cf, tok("tx"), tx, r.y() + 4, 12 * 1.4, title)
                    tips.append((r, tip))
                cx += cw + 6
            y += (row + 1) * 25 + row * 6
        return y - top


class Awards(Part):
    """every award, then every roast: the title underlined in gold (a roast's in gD), what it's for, who and how
    much"""

    def __init__(self):
        super().__init__()
        self.rows: list[tuple[str, str, str, str, bool]] = []
        self.me: str | None = None

    def set(self, rows: list[tuple[str, str, str, str, bool]], me: str | None):
        """me: your name, marked "(you)" """
        self.rows, self.me = rows, me
        self.changed()

    def draw(self, p, w):
        y = _mod_head(p, "Awards this run", [f"+2 for each award (max +6), {MINUS}2 for each roast"])
        if p:
            rule(p, 0, y, w, tok("tx"))
        y += 1
        tf, sf, f, hf = font(17, 700, num=True, spacing=0.03), font(11, 600, spacing=0.12), font(14), font(14, 500)
        bx = AWARD_W + 16
        hx = max(bx + 120, w - HOLDER_W)
        bw, hw = hx - 16 - bx, w - hx
        for title, blurb, holder, stat, good in self.rows:
            who = [(s, hf, tok("tx")) for s in holder.split()]
            who += [("(you)", hf, tok("mu"))] if holder == self.me else []
            who += [(s, hf, tok("tx")) for s in f"· {stat}".split()]
            bh = wrapped(None, f, None, 0, 0, bw, 14 * 1.4, blurb)
            hh = flow(None, who, 0, 0, hw, adv(hf, " "), 2.8)
            h = max(18.7, bh, hh)
            if p:
                ty = y + 10 + (h - 18.7) / 2
                tw = line(p, tf, tok("tx"), 0, ty, 18.7, title)
                if not good:
                    tw += 8 + line(p, sf, tok("mu"), tw + 8, ty + 4, 11, "ROAST")
                p.fillRect(QRectF(0, ty + 18.7 - 2, tw, 2), tok("gold" if good else "gD"))
                wrapped(p, f, tok("tx2"), bx, y + 10 + (h - bh) / 2, bw, 14 * 1.4, blurb)
                flow(p, who, hx, y + 10 + (h - hh) / 2, hw, adv(hf, " "), 2.8)
            y += 10 + h + 10
            if p:
                rule(p, 0, y, w, tok("ln"))
            y += 1
        return y


class GroupTab(QScrollArea):
    """the Group tab: the page, scrolling; and the Edit roles drawer, where everyone's class and role can be changed"""
    changed = pyqtSignal(str, str, str)      # a class or role picked: guid, class, role
    forget = pyqtSignal()                    # Forget my picks
    show_me = pyqtSignal(float, float)       # "Show your death": the Timeline tab, zoomed to it

    def __init__(self):
        super().__init__()
        self.view = GroupView()
        self.narrow = None
        self.page = Sheet()
        self.placing, self.plate = Placing(), Plate("To move up")
        self.plate.setFixedWidth(PLATE_W)
        self.plate.clicked.connect(lambda: self.view.death_at is not None and self.show_me.emit(
            self.view.death_at - 20, self.view.death_at + 5))
        self.podium, self.standings, self.awards = Podium(), Standings(), Awards()
        roles = QWidget()
        rl = QVBoxLayout(roles)
        rl.setContentsMargins(0, 0, 0, 12)
        head = QHBoxLayout()
        head.addWidget(dim_label("Class and role for everyone in the group. They're filled in from the add-on (new "
                                 "runs) or guessed from what each player cast; pick another to correct it. Your picks "
                                 "are remembered for that player, and your own role decides how you're scored."), 1)
        btn = QPushButton("Forget my picks")
        btn.clicked.connect(self.forget.emit)
        head.addWidget(btn, 0, Qt.AlignmentFlag.AlignTop)
        rl.addLayout(head)
        self.t = table(["", "Player", "Class", "Role", "From", "Damage", "Healing", "Taken", "Deaths", "Interrupts",
                        "Dispels"], stretch=1)
        self.t.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.t.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        rl.addWidget(self.t)
        self.roles_drawer = Drawer("Edit roles", roles)
        numbers = QWidget()
        nl = QVBoxLayout(numbers)
        nl.setContentsMargins(0, 0, 0, 12)
        self.run_line = dim_label()         # bosses and trash killed, deaths, wipes
        nl.addWidget(self.run_line)
        self.numbers = table(["Player", "Role", *STATS], stretch=0)
        self.numbers.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.numbers.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        for col, (what, _) in enumerate(STATS.values(), 2):
            self.numbers.horizontalHeaderItem(col).setToolTip(what)
        nl.addWidget(self.numbers)
        self.numbers_drawer = Drawer("All the numbers", numbers)

        hero_row = QHBoxLayout()
        hero_row.setContentsMargins(0, 8, 0, 0)
        hero_row.setSpacing(28)
        hero_row.addWidget(self.placing, 1, Qt.AlignmentFlag.AlignTop)
        hero_row.addWidget(self.plate, 0, Qt.AlignmentFlag.AlignTop)
        lay = QVBoxLayout(self.page)
        lay.setContentsMargins(16, 4, 16, 16)
        lay.setSpacing(0)
        lay.addSpacing(HEAD_H)
        lay.addLayout(hero_row)
        for part in (self.podium, self.standings, self.awards):
            lay.addSpacing(26)
            lay.addWidget(part)
        lay.addSpacing(26)
        lay.addWidget(Fold(self.numbers_drawer))
        lay.addWidget(Fold(self.roles_drawer, last=True))
        lay.addStretch(1)
        self.setWidget(self.page)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)

    def set_analysis(self, a):
        self._fill_roles(a)
        self._fill_numbers(a)
        if not a:
            self.show_view(GroupView(), "No run selected", "")
            return
        self.show_view(build_group(a), names.titled(a.data.run.id, a.data.run.zone), run_meta(a))

    def show_view(self, view: GroupView, title: str, sub: str):
        self.view = view
        self.page.title, self.page.sub = title, sub
        you = next((c for c in view.cards if c.you), None)
        reason = view.reason or ("You aren't in this group's standings." if view.cards else
                                 "No one to rank in this run.")
        self.placing.set(view.place, of_line(view), reason)
        if view.move_up:
            title, body = view.move_up
        else:       # you placed first (or aren't placed: the plate is hidden)
            title = "You placed first."
            body = f"Strongest at {you.plus[0][0].lower()}: {you.plus[0][1]}." if you and you.plus else None
        death = view.move_up is not None and view.death_at is not None      # placed 1st: nothing to move up from
        self.plate.set(title, None, None, "Show your death" if death else None, [], body)
        self.plate.setVisible(you is not None)
        self.podium.set(view.podium)
        self.standings.set(view.cards, view.average)
        self.awards.set(view.awards, you.name if you else None)
        for part, shown in ((self.podium, view.podium), (self.standings, view.cards), (self.awards, view.awards)):
            part.setVisible(bool(shown))
        self.roles_drawer.set_count(len(view.cards))
        self.page.update()

    def _fill_roles(self, a):
        """everyone's class and role, changeable (changed), with what each was taken from"""
        self.t.setRowCount(0)
        if not a or not a.summary:
            return
        bold = QFont()
        bold.setBold(True)
        players = sorted(a.roster.values(), key=lambda p: ({"TANK": 0, "HEALER": 1}.get(p.role or "", 2), p.name))
        for p in players:
            st = a.summary.stats[p.guid]
            r = self.t.rowCount()
            self.t.insertRow(r)
            ic = assets.icon(assets.class_icon_name(p.cls) or "")
            dot = item("" if ic else "●")
            if ic:
                dot.setIcon(ic)
            # NightElf -> Night Elf
            race = "".join(" " + ch if ch.isupper() and i else ch for i, ch in enumerate(p.race or ""))
            dot.setToolTip(" ".join(x for x in (race, (p.cls or "?").title()) if x))
            self.t.setItem(r, 0, dot)
            name = item(p.name + ("  (you)" if p.is_me else ""))
            name.setFont(bold)
            self.t.setItem(r, 1, name)
            cls = QComboBox()
            for k in CLASSES:
                cls.addItem(k.title(), k)
            cls.setCurrentIndex(max(0, cls.findData(p.cls)))
            role = QComboBox()
            for k in ROLES:
                role.addItem(k.title() if k != "DPS" else "DPS", k)
            role.setCurrentIndex(max(0, role.findData(p.role)))
            for box_ in (cls, role):
                box_.currentIndexChanged.connect(
                    lambda _, g=p.guid, cb=cls, rb=role: self.changed.emit(g, cb.currentData(), rb.currentData()))
            self.t.setCellWidget(r, 2, cls)
            self.t.setCellWidget(r, 3, role)
            if p.cls_from == p.role_from:
                src = SOURCE.get(p.cls_from, "?")
            else:
                src = f"class {SOURCE.get(p.cls_from, '?')}, role {SOURCE.get(p.role_from, '?')}"
            self.t.setItem(r, 4, item(src, theme.DIM))
            for col, v in enumerate([fmt_num(st.damage), fmt_num(st.healing), fmt_num(st.taken), st.deaths,
                                     st.interrupts, st.dispels], 5):
                self.t.setItem(r, col, item(v, theme.DEATH if col == 8 and v else None, align_right=True))
        _fit(self.t)

    def _fill_numbers(self, a):
        """the old Summary tab's numbers: the run line, and everyone's stats in placing order, each with where it
        ranks in the group"""
        t = self.numbers
        t.setRowCount(0)
        s = a.summary if a else None
        self.run_line.setText("" if not s else
                              f"{fmt_time(a.data.duration)} long, {fmt_time(s.combat_time)} in combat · bosses "
                              f"{s.bosses_killed}/{s.bosses} · {s.trash_killed} trash killed · {len(a.deaths)} "
                              f"death{'s' if len(a.deaths) != 1 else ''}"
                              + (f" · {s.wipes} wipe{'s' if s.wipes != 1 else ''}" if s.wipes else ""))
        stats = list(s.stats.values()) if s else []
        placing = {pl.guid: pl for pl in a.ranking} if a else {}
        order = list(placing)
        for st in sorted(stats, key=lambda st: order.index(st.player.guid) if st.player.guid in order else 99):
            p, r = st.player, t.rowCount()
            t.insertRow(r)
            vals = [p.name, ROLE_WORD.get(p.role, "DPS"), fmt_num(st.damage), f"{st.dps:.0f}", fmt_num(st.boss_damage),
                    fmt_num(st.healing), f"{st.overheal_share:.0%}" if st.healing else "", fmt_num(st.taken),
                    st.deaths or "", st.interrupts or "", st.dispels or "", st.killing_blows or "",
                    st.pulls_started or ""]
            for col, v in enumerate(vals):
                name = (["Player", "Role"] + list(STATS))[col]
                it = item(v, theme.DEATH if name == "Deaths" and v else None, align_right=col >= 2)
                if name in STATS:
                    what, key = STATS[name]
                    mine, total = key(st), sum(key(o) for o in stats)
                    share = f", {mine / total:.0%} of the group's" if total and name not in ("DPS", "Overheal") else ""
                    it.setToolTip(f"{p.name} — {name.lower()}: {what}\n"
                                  f"{ordinal(1 + sum(key(o) > mine for o in stats))} highest in the group{share}")
                elif col == 0 and p.guid in placing:
                    it.setToolTip(breakdown(placing[p.guid], a))
                elif col == 1:
                    it.setToolTip("role: your pick" if p.role_from == "you" else f"role: from {p.role_from}")
                t.setItem(r, col, it)
        self.numbers_drawer.set_count(t.rowCount())
        _fit(t)

    def resizeEvent(self, ev):
        narrow = self.window().width() < NARROW      # the mock-up's smaller placing figure
        if narrow != self.narrow:
            self.narrow = narrow
            for part in (self.placing, self.plate):
                part.narrow = narrow
                part.changed()
        super().resizeEvent(ev)


def _fit(t):
    """a drawer's table, as tall as its rows: the page scrolls, not the table"""
    t.resizeRowsToContents()
    t.setFixedHeight(t.horizontalHeader().sizeHint().height() + t.verticalHeader().length() + 2 * t.frameWidth())
