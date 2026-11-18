"""The run's tabs (Score, Group, Pulls, Spells, Summary) and the dungeon page."""
from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter
from PyQt6.QtWidgets import (QAbstractItemView, QComboBox, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel,
                             QPushButton, QScrollArea, QSplitter, QTableWidget, QTableWidgetItem, QTreeWidget, QTreeWidgetItem,
                             QVBoxLayout, QWidget)

from ..analysis import Analysis
from ..model.casts import spell_table
from ..model.roster import CLASSES, ROLES
from ..scoring.group import ordinal, player_card
from ..scoring.metrics import Metrics
from ..scoring.score import Scorecard
from ..sources.savedvars import Run
from . import assets, theme
from ..scoring.radar import average
from .radar import RadarChart
from .timeline import player_color, pull_text, spell_color

MARKER_COLORS = {"Skull": "#f0f0f0", "Cross": "#ff4040", "Square": "#40a0ff", "Moon": "#c0d0ff",
                 "Triangle": "#40ff60", "Diamond": "#c040ff", "Circle": "#ff9020", "Star": "#ffe040"}


def fmt_time(s: float) -> str:
    s = int(max(0, s))
    return f"{s // 60}:{s % 60:02d}"


def fmt_num(n: float) -> str:
    if n >= 1e6:
        return f"{n / 1e6:.1f}M"
    if n >= 1e4:
        return f"{n / 1e3:.0f}K"
    if n >= 1e3:
        return f"{n / 1e3:.1f}K"
    return f"{n:.0f}"


def table(headers: list[str], stretch: int | None = None) -> QTableWidget:
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.verticalHeader().setVisible(False)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    hh = t.horizontalHeader()
    hh.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    if stretch is not None:
        hh.setSectionResizeMode(stretch, QHeaderView.ResizeMode.Stretch)
    return t


def item(text, color: QColor | None = None, align_right: bool = False, data=None) -> QTableWidgetItem:
    it = QTableWidgetItem(str(text))
    if color is not None:
        it.setForeground(color)
    if align_right:
        it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    if data is not None:
        it.setData(Qt.ItemDataRole.UserRole, data)
    return it


def dim_label(text: str = "") -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("dim")
    lbl.setWordWrap(True)
    return lbl


# ============================================================================ Score
class Bar(QWidget):
    def __init__(self):
        super().__init__()
        self.value = 0.0
        self.setFixedHeight(10)
        self.setMinimumWidth(120)

    def set(self, v: float, dim: bool = False):
        self.value, self.dim = v, dim
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        r = QRectF(0, 0, self.width(), self.height())
        p.fillRect(r, theme.LANE)
        color = QColor(95, 95, 105) if getattr(self, "dim", False) else theme.score_color(self.value)
        p.fillRect(QRectF(0, 0, r.width() * self.value / 100, r.height()), color)


class ScorePanel(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        top = QHBoxLayout()
        head = QVBoxLayout()
        self.title = QLabel("No run selected")
        self.title.setObjectName("title")
        self.sub = dim_label()
        head.addWidget(self.title)
        head.addWidget(self.sub)
        top.addLayout(head, 1)
        self.radar = RadarChart(170)
        self.radar.setVisible(False)
        top.addWidget(self.radar)
        self.grade = QLabel("")
        self.grade.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        top.addWidget(self.grade)
        lay.addLayout(top)
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)
        self.rows = []
        for i in range(6):
            name, bar, num, summary = QLabel(), Bar(), QLabel(), dim_label()
            num.setFixedWidth(30)
            for col, w in enumerate((name, bar, num, summary)):
                grid.addWidget(w, i, col)
            self.rows.append((name, bar, num, summary))
        # the hybrid bonus, under the categories
        self.bonus_name, self.bonus_num, self.bonus_note = QLabel("Hybrid bonus"), QLabel(), dim_label()
        self.bonus_num.setStyleSheet(f"color: {theme.ACCENT.name()}; font-weight: 600;")
        grid.addWidget(self.bonus_name, 6, 0)
        grid.addWidget(self.bonus_num, 6, 1, 1, 2)
        grid.addWidget(self.bonus_note, 6, 3)
        grid.setColumnStretch(3, 1)
        lay.addLayout(grid)
        self.output = dim_label()
        lay.addWidget(self.output)
        self.tips = QLabel("")
        self.tips.setWordWrap(True)
        self.tips.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(self.tips)
        lay.addStretch(1)

    def show_card(self, title: str, sub: str, card: Scorecard | None, m: Metrics | None):
        self.title.setText(title)
        self.sub.setText(sub)
        empty = not card or card.empty
        for row in self.rows + [(self.bonus_name, self.bonus_num, self.bonus_note)]:
            for w in row:
                w.setVisible(False)
        if empty:
            if card and card.note:
                self.sub.setText(sub + " · " + card.note)
            self.grade.setText("")
            self.output.setText("")
            self.tips.setText("")
            return
        c = theme.grade_color(card.grade).name()
        self.grade.setText(f'<span style="font-size:30pt;font-weight:700;color:{c}">{card.total:.0f}</span>'
                           f'<span style="font-size:18pt;color:{c}">&nbsp;{card.grade}</span>'
                           f'<br><span style="color:{theme.DIM.name()}">as {card.role}</span>')
        for (name, bar, num, summary), cat in zip(self.rows, card.categories):
            for w in (name, bar, num, summary):
                w.setVisible(True)
            name.setText(cat.name)
            name.setStyleSheet(f"color: {theme.DIM.name()};" if cat.info_only else "")
            name.setToolTip("info only: weighted 0, doesn't count toward the total" if cat.info_only
                            else f"weight {cat.weight:g}")
            bar.set(cat.score, dim=cat.info_only)
            num.setText(f"{cat.score:.0f}")
            summary.setText(("info only · " if cat.info_only else "") + cat.summary)
        show_bonus = card.bonus > 0
        for w in (self.bonus_name, self.bonus_num, self.bonus_note):
            w.setVisible(show_bonus)
        if show_bonus:
            self.bonus_num.setText(f"+{card.bonus:.1f}")
            self.bonus_note.setText(card.bonus_note)
        out = []
        if m is None:
            pass
        elif m.has_log:
            out.append(f"{m.damage:,} damage ({m.dps:.0f}/s) · {m.healing:,} healing ({m.hps:.0f}/s, "
                       f"{m.overheal_share:.0%} overheal incl. passive) · {m.kills} killing blows · "
                       f"{m.damage_taken:,} taken")
        if m is not None and m.median_first_press is not None:
            out.append(f"first press after a pull: median {m.median_first_press:.2f}s")
        self.output.setText("  ·  ".join(out))
        if card.tips:
            items = "".join(f"<li>{t}</li>" for t in card.tips)
            self.tips.setText(f'<b style="color:{theme.ACCENT.name()}">Work on</b><ul style="margin-left:-20px">{items}</ul>')
        else:
            self.tips.setText(f'<b style="color:{theme.ACCENT.name()}">Nothing stands out - nice run.</b>')


FIGHT_COLUMNS = {
    "healer": ["At", "Fight", "Length", "Score", "Response", "Missed", "Died"],
    "dps": ["At", "Fight", "Length", "Score", "Busy", "Refused", "Presses/cast"],
    "other": ["At", "Fight", "Length", "Score", "Damage", "Taken", "Died"],   # anyone but you
}


class ScoreTab(QWidget):
    """a player's scorecard (whole run, or the fight picked on the right) and the fights. You get your full
    scorecard; anyone else is scored from the combat log alone (as on the Summary tab)."""
    zoom = pyqtSignal(float, float)

    def __init__(self):
        super().__init__()
        self.a: Analysis | None = None
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 6, 0, 0)
        pick = QHBoxLayout()
        pick.addWidget(dim_label("Player"))
        self.who = QComboBox()
        self.who.setMinimumWidth(220)
        self.who.currentIndexChanged.connect(self._who_changed)
        pick.addWidget(self.who)
        self.who_note = dim_label()
        pick.addWidget(self.who_note, 1)
        outer.addLayout(pick)
        lay = QHBoxLayout()
        outer.addLayout(lay, 1)
        self.card = ScorePanel()
        card_scroll = QScrollArea()          # the card's text wraps; let it scroll instead of squeezing
        card_scroll.setWidget(self.card)
        card_scroll.setWidgetResizable(True)
        card_scroll.setFrameShape(QFrame.Shape.NoFrame)
        card_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        lay.addWidget(card_scroll, 5)
        right = QVBoxLayout()
        head = QHBoxLayout()
        head.addWidget(dim_label("Fights - click one to score just that fight"), 1)
        self.whole = QPushButton("Whole run")
        self.whole.clicked.connect(self.show_whole)
        head.addWidget(self.whole)
        right.addLayout(head)
        self.fights = table(FIGHT_COLUMNS["healer"], stretch=1)
        self.fights.setMinimumWidth(520)
        self.fights.itemSelectionChanged.connect(self._pick)
        right.addWidget(self.fights)
        lay.addLayout(right, 4)
        self._fight_cards: list = []

    # ------------------------------------------------------------------ who
    def _guid(self) -> str | None:
        return self.who.currentData()

    def _is_me(self) -> bool:
        a = self.a
        return bool(a) and self._guid() == a.data.player_guid

    def set_analysis(self, a: Analysis | None):
        keep = self._guid()
        self.a = a
        self.who.blockSignals(True)
        self.who.clear()
        if a:
            ranks = {pl.guid: pl.rank for pl in a.ranking}
            players = sorted(a.roster.values(), key=lambda p: (not p.is_me, ranks.get(p.guid, 9)))
            for p in players:
                place = f"  ({ordinal(ranks[p.guid])})" if p.guid in ranks else ""
                self.who.addItem(p.name + (" (you)" if p.is_me else "") + place, p.guid)
                if (ic := assets.icon(assets.class_icon_name(p.cls) or "")) is not None:
                    self.who.setItemIcon(self.who.count() - 1, ic)
                self.who.setItemData(self.who.count() - 1, player_color(p), Qt.ItemDataRole.ForegroundRole)
            idx = self.who.findData(keep) if keep else -1
            self.who.setCurrentIndex(idx if idx >= 0 else 0)   # you, by default
        self.who.blockSignals(False)
        self._who_changed()

    def _who_changed(self):
        a, guid = self.a, self._guid()
        self.fights.blockSignals(True)
        self.fights.setRowCount(0)
        self._fight_cards = []
        if a and guid:
            p = a.roster[guid]
            me = self._is_me()
            cols = FIGHT_COLUMNS[a.role] if me else FIGHT_COLUMNS["other"]
            self.fights.setHorizontalHeaderLabels(cols)
            self.who_note.setText(
                "your full scorecard, from the add-on and the combat log" if me else
                f"scored from the combat log as {(p.role or 'DPS').lower() if p.role != 'DPS' else 'a damage dealer'} "
                f"(the add-on only records your own presses and movement)")
            dead_in: dict[int, list] = {}
            for d in a.deaths:
                for i, f in enumerate(a.data.fights):
                    if f.start - 2 <= d.t <= f.end + 5:
                        dead_in.setdefault(i, []).append(d)
                        break
            g = a.group
            for i, fr in enumerate(a.fights):
                f = fr.fight
                if me:
                    m, h, c = fr.metrics, fr.healer, fr.card
                else:
                    c = player_card(a, guid, [(f.start, f.end)])
                self._fight_cards.append(c)
                kill = "" if f.killed is None else (" (killed)" if f.killed else " (wipe)")
                died = ", ".join(d.name.split(" ")[0] for d in dead_in.get(i, [])) or "-"
                score = f"{c.total:.0f} {c.grade}" if not c.empty else "-"
                vals = [fmt_time(f.start), f.label + kill, f"{f.duration:.0f}s", score]
                if not me:
                    w = [(f.start, f.end)]
                    vals += [fmt_num(_sum_window(g.damage[guid], w)), fmt_num(_sum_window(g.taken[guid], w)), died]
                elif a.role == "healer":
                    resp = f"{h.median_response:.1f}s" if h.median_response is not None else "-"
                    vals += [resp, f"{h.missed}/{len(h.judged)}" if h.judged else "-", died]
                else:
                    vals += [f"{m.uptime:.0%}", str(m.failed), f"{m.presses_per_cast:.1f}"]
                r = self.fights.rowCount()
                self.fights.insertRow(r)
                for col, v in enumerate(vals):
                    color = theme.grade_color(c.grade) if col == 3 and not c.empty else \
                        theme.DEATH if col == 6 and v != "-" and cols[6] == "Died" else None
                    self.fights.setItem(r, col, item(v, color, align_right=col in (4, 5) and not me))
        self.fights.blockSignals(False)
        self.show_whole()

    # ------------------------------------------------------------------ showing
    def show_whole(self):
        a = self.a
        self.fights.clearSelection()
        if not a or not self._guid():
            self.card.show_card("No run selected", "", None, None)
            return
        rd = a.data
        parts = f" ({len(rd.run.parts)} pieces)" if len(rd.run.parts) > 1 else ""
        when = (f"{rd.run.start_time:%A %d %B, %H:%M}{parts} · {fmt_time(rd.duration)} long, "
                f"{fmt_time(a.metrics.combat_time)} in combat over {len(rd.fights)} fights")
        if self._is_me():
            sync = "; ".join(s.describe() for s in rd.sync if s.anchors) or "no clock anchors"
            self.card.show_card(rd.run.zone, f"{when} · sync: {sync}", a.card, a.metrics)
            self._show_radar()
            return
        pl = next((x for x in a.ranking if x.guid == self._guid()), None)
        p = a.roster[self._guid()]
        title = f"{p.name} - {rd.run.zone}"
        sub = when + (f" · placed {ordinal(pl.rank)} of {len(a.ranking)}" if pl else "")
        self.card.show_card(title, sub, pl.card if pl else player_card(a, p.guid), None)
        self._show_radar()

    def _show_radar(self):
        """the selected player's radar (for the whole run) next to their grade"""
        a, guid = self.a, self._guid()
        r = a.radars.get(guid) if a and guid else None
        self.card.radar.setVisible(r is not None)
        if r is not None:
            p = a.roster[guid]
            self.card.radar.set_data(r, player_color(p), p.name, average(a.radars))

    def _pick(self):
        a = self.a
        rows = self.fights.selectionModel().selectedRows()
        if not a or not rows:
            return
        i = rows[0].row()
        fr = a.fights[i]
        f = fr.fight
        kill = "" if f.killed is None else (" - killed" if f.killed else " - wipe")
        who = "" if self._is_me() else f"{a.roster[self._guid()].name} · "
        card = fr.card if self._is_me() else self._fight_cards[i]
        self.card.show_card(f"{f.label}{kill}", f"{who}{a.data.run.zone} · at {fmt_time(f.start)} · {f.duration:.0f}s",
                            card, fr.metrics if self._is_me() else None)
        pad = max(3.0, f.duration * 0.08)
        self.zoom.emit(f.start - pad, f.end + pad)


def _sum_window(series, windows) -> int:
    return sum(v for t, v in series if any(a <= t <= b for a, b in windows))


# ============================================================================ Group
SOURCE = {"you": "your pick", "addon": "from the add-on", "spells": "guessed from spells", "?": "unknown"}


class GroupTab(QWidget):
    """who was in the group: class and role for each, changeable"""
    changed = pyqtSignal(str, str, str)      # guid, class, role
    forget = pyqtSignal()

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 6, 0, 0)
        head = QHBoxLayout()
        head.addWidget(dim_label("Class and role for everyone in the group. They're filled in from the add-on (new runs) "
                                 "or guessed from what each player cast; pick another to correct it. Your picks are "
                                 "remembered for that player, and your own role decides how you're scored."), 1)
        btn = QPushButton("Forget my picks")
        btn.clicked.connect(self.forget.emit)
        head.addWidget(btn)
        lay.addLayout(head)
        self.t = table(["", "Player", "Class", "Role", "From", "Damage", "Healing", "Taken", "Deaths", "Interrupts",
                        "Dispels"], stretch=1)
        self.t.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        lay.addWidget(self.t)

    def set_analysis(self, a: Analysis | None):
        self.t.setRowCount(0)
        if not a or not a.summary:
            return
        players = sorted(a.roster.values(), key=lambda p: ({"TANK": 0, "HEALER": 1}.get(p.role or "", 2), p.name))
        for p in players:
            st = a.summary.stats[p.guid]
            r = self.t.rowCount()
            self.t.insertRow(r)
            c = player_color(p)
            ic = assets.icon(assets.class_icon_name(p.cls) or "")
            dot = item("" if ic else "●", c)
            if ic:
                dot.setIcon(ic)
            dot.setToolTip(f"{(p.cls or '?').title()}")
            self.t.setItem(r, 0, dot)
            name = item(p.name + ("  (you)" if p.is_me else ""), c)
            f = QFont()
            f.setBold(True)
            name.setFont(f)
            self.t.setItem(r, 1, name)
            cls = QComboBox()
            for k in CLASSES:
                cls.addItem(k.title(), k)
            cls.setCurrentIndex(max(0, cls.findData(p.cls)))
            role = QComboBox()
            for k in ROLES:
                role.addItem(k.title() if k != "DPS" else "DPS", k)
            role.setCurrentIndex(max(0, role.findData(p.role)))
            cls.currentIndexChanged.connect(lambda _, g=p.guid, cb=cls, rb=role: self.changed.emit(g, cb.currentData(), rb.currentData()))
            role.currentIndexChanged.connect(lambda _, g=p.guid, cb=cls, rb=role: self.changed.emit(g, cb.currentData(), rb.currentData()))
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


# ============================================================================ Pulls
class PullsTab(QWidget):
    zoom = pyqtSignal(float, float)

    def __init__(self):
        super().__init__()
        self.a: Analysis | None = None
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 6, 0, 0)
        split = QSplitter()
        self.list = table(["#", "At", "Pull", "Mobs", "Packs", "Pulled by", "Length", "Died"], stretch=2)
        self.list.itemSelectionChanged.connect(self._pick)
        split.addWidget(self.list)
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(6, 0, 0, 0)
        self.head = QLabel("Pick a pull")
        self.head.setObjectName("title")
        self.sub = dim_label()
        rl.addWidget(self.head)
        rl.addWidget(self.sub)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Mob", "Marker", "Went for", "Died", "Kill #", "Killed by"])
        self.tree.setRootIsDecorated(True)
        self.tree.header().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        rl.addWidget(self.tree, 1)
        rl.addWidget(dim_label("Who pulled: the first player to touch the mob (an ability, or \"body pull\" when the mob "
                               "attacked first). \"Went for\" is the first player it hit: the log has no threat data, "
                               "so that's a good guess at its first target, not a certainty."))
        split.addWidget(right)
        split.setSizes([520, 620])
        lay.addWidget(split)

    def set_analysis(self, a: Analysis | None):
        self.a = a
        self.list.blockSignals(True)
        self.list.setRowCount(0)
        self.tree.clear()
        self.head.setText("Pick a pull")
        self.sub.setText("")
        if a:
            for pl in a.pulls:
                if not pl.packs and not pl.fight.boss:
                    continue
                died = [d for d in a.deaths if pl.start - 2 <= d.t <= pl.fight.end + 5]
                first = pl.packs[0] if pl.packs else None
                puller = a.roster.get(first.puller) if first and first.puller else None
                r = self.list.rowCount()
                self.list.insertRow(r)
                vals = [pl.index + 1, fmt_time(pl.start), pl.fight.label, len(pl.enemies), len(pl.packs),
                        puller.name if puller else "?", f"{pl.fight.end - pl.start:.0f}s",
                        ", ".join(d.name.split(" ")[0] for d in died) or "-"]
                for col, v in enumerate(vals):
                    color = player_color(puller) if col == 5 and puller else theme.BOSS.lighter(250) if col == 2 and pl.fight.boss \
                        else theme.FAIL if col == 4 and v > 1 else theme.DEATH if col == 7 and v != "-" else None
                    self.list.setItem(r, col, item(v, color, align_right=col in (3, 4), data=pl.index if col == 0 else None))
        self.list.blockSignals(False)

    def _pick(self):
        a = self.a
        rows = self.list.selectionModel().selectedRows()
        if not a or not rows:
            return
        idx = self.list.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        pl = a.pulls[idx]
        self.head.setText(pl.fight.label + (" - killed" if pl.fight.killed else " - wipe" if pl.fight.killed is False else ""))
        n_dead = sum(1 for e in pl.enemies if e.died is not None)
        self.sub.setText(f"at {fmt_time(pl.start)} · {pl.fight.end - pl.start:.0f}s · {len(pl.enemies)} mobs in "
                         f"{len(pl.packs)} pack{'s' if len(pl.packs) != 1 else ''} · {n_dead} killed")
        order = {en.guid: n for n, en in enumerate(pl.kill_order, 1)}
        name = lambda g: a.roster[g].name if g in a.roster else "-"  # noqa: E731
        self.tree.clear()
        for i, pk in enumerate(pl.packs, 1):
            puller = a.roster.get(pk.puller) if pk.puller else None
            top = QTreeWidgetItem([f"{'Extra pack' if pk.extra else 'Pack'} {i} at {fmt_time(pk.start)} - "
                                   f"{puller.name if puller else '?'} ({pk.how})"])
            top.setForeground(0, theme.FAIL if pk.extra else theme.TEXT)
            f = QFont()
            f.setBold(True)
            top.setFont(0, f)
            for en in pk.enemies:
                died = f"{fmt_time(en.died)} (+{en.died - pl.start:.0f}s)" if en.died is not None else "alive"
                killer = f"{name(en.killer)}" + (f" - {en.killing_blow}" if en.killing_blow else "") if en.killer else "-"
                child = QTreeWidgetItem([en.name, en.marker or "", name(en.first_target), died,
                                         str(order.get(en.guid, "")), killer])
                if en.marker:
                    child.setForeground(1, QColor(MARKER_COLORS.get(en.marker, "#ffffff")))
                    if (mi := assets.icon(assets.marker_name(en.marker) or "")) is not None:
                        child.setIcon(1, mi)
                for col, g in ((2, en.first_target), (5, en.killer)):
                    if g in a.roster:
                        child.setForeground(col, player_color(a.roster[g]))
                top.addChild(child)
            self.tree.addTopLevelItem(top)
            top.setFirstColumnSpanned(True)
            top.setExpanded(True)
        self.zoom.emit(pl.start - 3, pl.fight.end + 3)


# ============================================================================ Spells
class SpellsTab(QWidget):
    highlight = pyqtSignal(object, object)   # guid, spell name (None, None: clear)

    def __init__(self):
        super().__init__()
        self.a: Analysis | None = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 6, 0, 0)
        row = QHBoxLayout()
        row.addWidget(dim_label("Player"))
        self.who = QComboBox()
        self.who.currentIndexChanged.connect(self._fill)
        row.addWidget(self.who)
        row.addWidget(dim_label("Fights"))
        self.scope = QComboBox()
        for label, key in (("Whole run", "all"), ("Bosses", "boss"), ("Trash", "trash")):
            self.scope.addItem(label, key)
        self.scope.currentIndexChanged.connect(self._fill)
        row.addWidget(self.scope)
        clear = QPushButton("Clear highlight")
        clear.clicked.connect(lambda: (self.t.clearSelection(), self.highlight.emit(None, None)))
        row.addWidget(clear)
        row.addStretch(1)
        self.total = dim_label()
        row.addWidget(self.total)
        lay.addLayout(row)
        self.t = table(["", "Spell", "Casts", "Per min", "Failed", "Damage", "Healing", "Overheal", "Crit", "Share"],
                       stretch=1)
        self.t.itemSelectionChanged.connect(self._pick)
        lay.addWidget(self.t)
        lay.addWidget(dim_label("Click a spell to light up its casts in that player's row on the timeline."))

    def set_analysis(self, a: Analysis | None):
        self.a = a
        self.who.blockSignals(True)
        self.who.clear()
        if a:
            players = sorted(a.roster.values(), key=lambda p: (not p.is_me, p.name))
            for p in players:
                self.who.addItem(p.name + (" (you)" if p.is_me else ""), p.guid)
                if (ic := assets.icon(assets.class_icon_name(p.cls) or "")) is not None:
                    self.who.setItemIcon(self.who.count() - 1, ic)
                self.who.setItemData(self.who.count() - 1, player_color(p), Qt.ItemDataRole.ForegroundRole)
        self.who.blockSignals(False)
        self._fill()

    def _windows(self):
        a, key = self.a, self.scope.currentData()
        if key == "all":
            return None
        return [(f.start - 2, f.end + 2) for f in a.data.fights if (f.boss is not None) == (key == "boss")]

    def _fill(self):
        self.t.blockSignals(True)
        self.t.setRowCount(0)
        a, guid = self.a, self.who.currentData()
        if a and guid:
            windows = self._windows()
            rows = spell_table(a.data, guid, windows, a.pets.get(guid))
            combat = sum(b - c for c, b in windows) if windows else a.metrics.combat_time or 1
            total = sum(r.damage + r.healing for r in rows) or 1
            self.total.setText(f"{fmt_num(sum(r.damage for r in rows))} damage · {fmt_num(sum(r.healing for r in rows))} "
                               f"healing · {sum(r.casts for r in rows)} casts")
            for r in rows:
                if not (r.casts or r.damage or r.healing or r.failed):
                    continue
                i = self.t.rowCount()
                self.t.insertRow(i)
                share = (r.damage + r.healing) / total
                vals = ["■", r.spell, r.casts or "", f"{r.casts * 60 / combat:.1f}" if r.casts else "",
                        r.failed or "", fmt_num(r.damage) if r.damage else "", fmt_num(r.healing) if r.healing else "",
                        f"{r.overheal_share:.0%}" if r.healing or r.overheal else "", f"{r.crit_share:.0%}" if r.hits else "",
                        f"{share:.0%}" if share >= 0.005 else ""]
                sid = r.spell_id if r.spell_id and 0 < r.spell_id < 10_000_000 else None
                spell_pm = assets.spell_pixmap(sid)
                if spell_pm is not None:
                    vals[0] = ""
                for col, v in enumerate(vals):
                    it = item(v, spell_color(r.spell.replace(" (pet)", "")) if col == 0 else
                              theme.FAIL if col == 4 else None,
                              align_right=col >= 2, data=r.spell if col == 1 else None)
                    if col == 0 and spell_pm is not None:
                        it.setIcon(QIcon(spell_pm))
                    self.t.setItem(i, col, it)
        else:
            self.total.setText("")
        self.t.blockSignals(False)
        self.highlight.emit(None, None)

    def _pick(self):
        rows = self.t.selectionModel().selectedRows()
        if not rows:
            return
        spell = self.t.item(rows[0].row(), 1).data(Qt.ItemDataRole.UserRole)
        self.highlight.emit(self.who.currentData(), spell)


# ============================================================================ Dungeon page
class ScoreChart(QWidget):
    """a bar per visit, oldest to newest, colored by grade"""

    def __init__(self):
        super().__init__()
        self.points: list[tuple[str, float | None, str]] = []   # label, score, grade
        self.setMinimumHeight(170)

    def set_points(self, pts):
        self.points = pts
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        r = QRectF(40, 10, self.width() - 50, self.height() - 34)
        p.setFont(QFont(theme.FONT, 8))
        for v in (0, 50, 100):
            y = r.bottom() - v / 100 * r.height()
            p.setPen(theme.GRID)
            p.drawLine(int(r.left()), int(y), int(r.right()), int(y))
            p.setPen(theme.DIM)
            p.drawText(QRectF(0, y - 8, 34, 16), Qt.AlignmentFlag.AlignRight, str(v))
        n = len(self.points)
        if not n:
            return
        w = min(60.0, r.width() / n)
        for i, (label, score, grade) in enumerate(self.points):
            x = r.left() + i * w + w * 0.15
            if score is not None:
                h = score / 100 * r.height()
                p.fillRect(QRectF(x, r.bottom() - h, w * 0.7, h), theme.grade_color(grade))
                p.setPen(theme.TEXT)
                p.drawText(QRectF(x - 5, r.bottom() - h - 16, w * 0.7 + 10, 14), Qt.AlignmentFlag.AlignCenter,
                           f"{score:.0f}")
            p.setPen(theme.DIM)
            p.drawText(QRectF(x - 10, r.bottom() + 4, w * 0.7 + 20, 14), Qt.AlignmentFlag.AlignCenter, label)


class DungeonPage(QWidget):
    open_run = pyqtSignal(str)   # run id

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        self.head = QLabel("")
        self.head.setObjectName("title")
        self.sub = dim_label()
        lay.addWidget(self.head)
        lay.addWidget(self.sub)
        lay.addWidget(dim_label("Your score on each visit, oldest to newest"))
        self.chart = ScoreChart()
        lay.addWidget(self.chart)
        self.t = table(["When", "Length", "In combat", "Score", "Bosses", "Deaths", "Wipes", "Pieces"], stretch=0)
        self.t.itemDoubleClicked.connect(self._open)
        lay.addWidget(self.t, 1)
        lay.addWidget(dim_label("Double-click a visit to open it."))

    def show_dungeon(self, zone: str, runs: list[Run], analyses: dict[str, Analysis]):
        self.head.setText(zone)
        self.sub.setText(f"{len(runs)} visit{'s' if len(runs) != 1 else ''}")
        self.t.setRowCount(0)
        pts = []
        for run in runs:
            a = analyses.get(run.id)
            r = self.t.rowCount()
            self.t.insertRow(r)
            if a:
                card = a.card
                score = f"{card.total:.0f} {card.grade}" if not card.empty else "-"
                s = a.summary
                vals = [f"{run.start_time:%a %d %b %H:%M}", fmt_time(a.data.duration), fmt_time(a.metrics.combat_time),
                        score, f"{s.bosses_killed}/{s.bosses}" if s else "-", len(a.deaths), len(a.wipes) or "",
                        len(run.parts)]
            else:
                vals = [f"{run.start_time:%a %d %b %H:%M}", "", "", "...", "", "", "", len(run.parts)]
            for col, v in enumerate(vals):
                color = theme.grade_color(a.card.grade) if a and col == 3 and not a.card.empty else None
                self.t.setItem(r, col, item(v, color, data=run.id if col == 0 else None))
        for run in reversed(runs):
            a = analyses.get(run.id)
            ok = a and not a.card.empty
            pts.append((f"{run.start_time:%d %b}", a.card.total if ok else None, a.card.grade if ok else "-"))
        self.chart.set_points(pts)

    def _open(self, it):
        rid = self.t.item(it.row(), 0).data(Qt.ItemDataRole.UserRole)
        if rid:
            self.open_run.emit(rid)
