"""The Summary tab: a podium "photo" of the top three, everyone's placing with why they placed there,
and (behind a button) all the numbers. Everything has a tooltip."""
from __future__ import annotations

from PyQt6.QtCore import QEvent, QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
from PyQt6.QtWidgets import (QAbstractItemView, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QToolTip,
                             QVBoxLayout, QWidget)

from ..analysis import Analysis
from ..scoring.group import award_points, ordinal, placing_reason
from . import assets, theme
from .pages import dim_label, fmt_num, fmt_time, item, table
from ..scoring.radar import average
from .radar import RadarChart
from .timeline import player_color, text_color

MEDALS = {1: QColor(255, 205, 70), 2: QColor(200, 205, 215), 3: QColor(205, 135, 75)}
ROLE_WORD = {"TANK": "Tank", "HEALER": "Healer", "DPS": "Damage"}


def card_tooltip(a: Analysis, pl) -> str:
    """a player's placing, broken down (rich text)"""
    p = a.roster[pl.guid]
    rows = []
    for c in pl.card.categories:
        w = "info" if c.info_only else f"x{c.weight:g}"
        rows.append(f"<tr><td>{c.name}</td><td align=right><b>{'-' if c.unavailable else f'{c.score:.0f}'}</b></td>"
                    f"<td style='color:#888'>&nbsp;{w}</td><td>&nbsp;{c.summary}</td></tr>")
    if pl.card.bonus:
        rows.append(f"<tr><td>Hybrid bonus</td><td align=right><b>+{pl.card.bonus:.1f}</b></td><td></td>"
                    f"<td>&nbsp;{pl.card.bonus_note}</td></tr>")
    for aw in pl.awards:
        rows.append(f"<tr><td>{aw.title}</td><td align=right><b>{'+2' if aw.good else '-2'}</b></td><td></td>"
                    f"<td>&nbsp;{aw.stat}</td></tr>")
    return (f"<b style='color:{text_color(p).name()}'>{p.name}</b> - {ordinal(pl.rank)}, "
            f"{pl.points:.0f} points<br>{pl.card.total:.0f} as {ROLE_WORD.get(p.role or 'DPS', 'Damage').lower()}"
            f"{', ' + format(award_points(pl.awards), '+g') + ' from awards' if pl.awards else ''}"
            f"<table cellspacing=2>{''.join(rows)}</table>")


class Podium(QWidget):
    """the top three on steps, 2nd - 1st - 3rd, under a spotlight"""

    def __init__(self):
        super().__init__()
        self.a: Analysis | None = None
        self.spots: list[tuple[QRectF, object]] = []
        self.setMinimumHeight(300)
        self.setMouseTracking(True)

    def set_analysis(self, a: Analysis | None):
        self.a = a
        self.update()

    def event(self, ev):
        if ev.type() == QEvent.Type.ToolTip and self.a:
            for r, pl in self.spots:
                if r.contains(QPointF(ev.pos())):
                    QToolTip.showText(ev.globalPos(), card_tooltip(self.a, pl), self)
                    return True
            QToolTip.hideText()
            return True
        return super().event(ev)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()
        # the "photo": a dark stage, a spotlight from above, a frame
        bg = QLinearGradient(0, 0, 0, h)
        bg.setColorAt(0, QColor(20, 22, 34))
        bg.setColorAt(1, QColor(10, 10, 14))
        p.fillRect(QRectF(0, 0, w, h), bg)
        spot = QRadialGradient(QPointF(w / 2, h * 0.15), w * 0.45)
        spot.setColorAt(0, QColor(255, 240, 200, 55))
        spot.setColorAt(1, QColor(255, 240, 200, 0))
        p.fillRect(QRectF(0, 0, w, h), QBrush(spot))
        p.setPen(QPen(QColor(255, 255, 255, 30), 1))
        p.drawRect(QRectF(0.5, 0.5, w - 1, h - 1))
        self.spots = []
        if not self.a or not self.a.ranking:
            p.setPen(theme.DIM)
            p.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, "No one to rank yet")
            return
        top = self.a.ranking[:3]
        step_w = min(220.0, w / 3.6)
        floor = h - 26
        heights = {1: 120, 2: 88, 3: 64}
        order = [pl for pl in (top[1:2] + top[0:1] + top[2:3])]
        x0 = w / 2 - step_w * 1.5
        p.fillRect(QRectF(x0 - 30, floor, step_w * 3 + 60, 4), QColor(255, 255, 255, 25))
        for i, pl in enumerate(order):
            rank = pl.rank
            x = x0 + i * step_w
            sh = heights.get(rank, 50)
            step = QRectF(x + 6, floor - sh, step_w - 12, sh)
            grad = QLinearGradient(0, step.top(), 0, step.bottom())
            medal = MEDALS.get(rank, QColor(120, 120, 130))
            grad.setColorAt(0, medal.darker(120))
            grad.setColorAt(1, medal.darker(230))
            path = QPainterPath()
            path.addRoundedRect(step, 4, 4)
            p.setBrush(QBrush(grad))     # set it: the brush left over from the last token would win
            p.setPen(QPen(medal, 1.5))
            p.drawPath(path)
            p.setBrush(Qt.BrushStyle.NoBrush)
            # the place number on the step
            f = QFont(theme.FONT, 26 if rank == 1 else 20)
            f.setBold(True)
            p.setFont(f)
            p.setPen(QColor(255, 255, 255, 220))
            p.drawText(QRectF(step.left(), step.top() + 4, step.width(), 44), Qt.AlignmentFlag.AlignCenter,
                       ordinal(rank))
            p.setFont(QFont(theme.FONT, 9))
            p.setPen(QColor(255, 255, 255, 170))
            p.drawText(QRectF(step.left(), step.top() + 46, step.width(), 18), Qt.AlignmentFlag.AlignCenter,
                       f"{pl.points:.0f} points")
            # the player standing on it: a class-colored token, their name, role, awards
            player = self.a.roster[pl.guid]
            c = player_color(player)
            cy = step.top() - 64
            token = QRectF(x + step_w / 2 - 22, cy, 44, 44)
            halo = QRadialGradient(token.center(), 34)
            halo.setColorAt(0, QColor(c.red(), c.green(), c.blue(), 90))
            halo.setColorAt(1, QColor(c.red(), c.green(), c.blue(), 0))
            p.setBrush(QBrush(halo))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(token.adjusted(-14, -14, 14, 14))
            p.setBrush(c.darker(170))
            p.setPen(QPen(c, 2))
            p.drawEllipse(token)
            f = QFont(theme.FONT, 15)
            f.setBold(True)
            p.setFont(f)
            cls_pm = assets.class_pixmap(player.cls)
            if cls_pm is not None:
                clip = QPainterPath()
                clip.addEllipse(token.adjusted(2, 2, -2, -2))
                p.save()
                p.setClipPath(clip)
                p.drawPixmap(token.adjusted(2, 2, -2, -2).toRect(), cls_pm)
                p.restore()
            else:
                p.setPen(c)
                p.drawText(token, Qt.AlignmentFlag.AlignCenter, player.name[:1])
            if pl.mvp:
                f = QFont(theme.FONT, 9)
                f.setBold(True)
                p.setFont(f)
                badge = QRectF(token.center().x() - 22, token.top() - 20, 44, 16)
                bp = QPainterPath()
                bp.addRoundedRect(badge, 8, 8)
                p.fillPath(bp, MEDALS[1])
                p.setPen(QColor(30, 25, 10))
                p.drawText(badge, Qt.AlignmentFlag.AlignCenter, "MVP")
            f = QFont(theme.FONT, 10)
            f.setBold(True)
            p.setFont(f)
            p.setPen(c)
            p.drawText(QRectF(x, step.top() - 18, step_w, 16), Qt.AlignmentFlag.AlignCenter, player.name)
            good = [aw.title for aw in pl.awards if aw.good]
            if good:   # under the floor, so short steps don't crowd it
                p.setFont(QFont(theme.FONT, 8))
                p.setPen(QColor(255, 255, 255, 150))
                p.drawText(QRectF(x, floor + 6, step_w, 16), Qt.AlignmentFlag.AlignCenter,
                           " · ".join(good[:2]) + (" ..." if len(good) > 2 else ""))
            self.spots.append((QRectF(x, cy - 22, step_w, floor - cy + 22), pl))
        p.setFont(QFont(theme.FONT, 8))
        p.setPen(QColor(255, 255, 255, 90))
        p.drawText(QRectF(10, 8, w - 20, 16), Qt.AlignmentFlag.AlignRight,
                   f"{self.a.data.run.zone} · {self.a.data.run.start_time:%d %b %Y}")


class StandingRow(QFrame):
    """one player's placing: rank, name, why, strengths, weaknesses, awards"""

    def __init__(self, a: Analysis, pl):
        super().__init__()
        p = a.roster[pl.guid]
        c = player_color(p)
        medal = MEDALS.get(pl.rank, QColor(110, 110, 120))
        self.setStyleSheet(f"StandingRow {{ background: {theme.panel()}; border: 1px solid {theme.EDGE.name()};"
                           f" border-left: 3px solid {medal.name()}; }} QLabel {{ border: 0; background: transparent; }}")
        self.setToolTip(card_tooltip(a, pl))
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        place = QLabel(ordinal(pl.rank))
        place.setFixedWidth(52)
        place.setStyleSheet(f"color: {medal.name()}; font-size: 18pt; font-weight: 700;")
        place.setToolTip(f"{ordinal(pl.rank)} place: {pl.points:.0f} points "
                         f"({pl.card.total:.0f} score{', ' + format(award_points(pl.awards), '+g') + ' awards' if pl.awards else ''})")
        lay.addWidget(place)
        body = QVBoxLayout()
        icon_png = assets.png_path(assets.class_icon_name(p.cls) or "")
        icon_html = f"<img src='{icon_png}' width=18 height=18>&nbsp;" if icon_png else ""
        head = QLabel(f"{icon_html}<span style='color:{text_color(p).name()}; font-weight:600; font-size:11pt; "
                      f"font-family:\"{theme.TITLE_FONT}\"'>{p.name}</span>"
                      f"<span style='color:{theme.DIM.name()}'>&nbsp;&nbsp;{ROLE_WORD.get(p.role or 'DPS')}"
                      f"{' · MVP' if pl.mvp else ''}{' · you' if p.is_me else ''}</span>")
        body.addWidget(head)
        why = dim_label(placing_reason(pl, a))
        body.addWidget(why)
        for s in pl.strengths:
            lbl = QLabel(f"<span style='color:{theme.BUSY.name()}'>+</span> {s}")
            lbl.setWordWrap(True)
            lbl.setToolTip("a strength: one of their best-scoring categories")
            body.addWidget(lbl)
        for s in pl.weaknesses:
            lbl = QLabel(f"<span style='color:{theme.FAIL.name()}'>-</span> {s}")
            lbl.setWordWrap(True)
            lbl.setToolTip("held them back: one of their lowest-scoring categories")
            body.addWidget(lbl)
        if pl.awards:
            chips = QHBoxLayout()
            chips.setSpacing(6)
            for aw in pl.awards:
                chip = QLabel(aw.title)
                color = theme.ACCENT if aw.good else theme.IDLE
                chip.setStyleSheet(f"color: {color.name()}; border: 1px solid {color.name()}; padding: 1px 6px;")
                chip.setToolTip(f"<b>{aw.title}</b> ({'award, +2' if aw.good else 'roast, -2'})<br>{aw.blurb}<br>{aw.stat}")
                chips.addWidget(chip)
            chips.addStretch(1)
            body.addLayout(chips)
        lay.addLayout(body, 1)
        if pl.guid in a.radars:
            chart = RadarChart(150, compact=True)
            chart.set_data(a.radars[pl.guid], c, p.name, average(a.radars))
            lay.addWidget(chart, 0, Qt.AlignmentFlag.AlignVCenter)
        pts = QLabel(f"{pl.points:.0f}")
        pts.setStyleSheet(f"color: {theme.grade_color(pl.card.grade).name()}; font-size: 18pt; font-weight: 700;")
        pts.setToolTip("placing points: their score plus awards")
        lay.addWidget(pts, 0, Qt.AlignmentFlag.AlignTop)


STAT_HELP = {
    "Damage": "damage to enemies, pets included",
    "DPS": "damage per second of combat",
    "On bosses": "damage during boss fights",
    "Healing": "healing that landed (overhealing not counted)",
    "Overheal": "share of their healing that was wasted on full health",
    "Taken": "damage they took",
    "Deaths": "times they died (Feign Death not counted)",
    "Interrupts": "spell casts they interrupted",
    "Dispels": "debuffs and buffs they dispelled",
    "Killing blows": "enemies they landed the killing blow on",
    "Pulls": "packs they were first to touch",
}


class SummaryTab(QWidget):
    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        scroll.setWidget(body)
        outer.addWidget(scroll)
        self.lay = QVBoxLayout(body)
        self.lay.setContentsMargins(0, 6, 8, 8)
        self.head = QLabel("")
        self.head.setObjectName("title")
        self.sub = dim_label()
        self.lay.addWidget(self.head)
        self.lay.addWidget(self.sub)
        self.podium = Podium()
        self.lay.addWidget(self.podium)
        self.lay.addWidget(dim_label("Everyone is scored on what the combat log shows, by their role (your full scorecard "
                                     "is on the Score tab). Awards add 2 points each (up to 6); roasts take 2 off. "
                                     "Hover anyone for the breakdown."))
        self.standings = QVBoxLayout()
        self.standings.setSpacing(6)
        self.lay.addLayout(self.standings)
        self.more = QPushButton("Show all the numbers")
        self.more.setCheckable(True)
        self.more.toggled.connect(self._toggle)
        row = QHBoxLayout()
        row.addWidget(self.more)
        row.addStretch(1)
        self.lay.addLayout(row)
        self.t = table(["", "Player", "Role", "Damage", "DPS", "On bosses", "Healing", "Overheal", "Taken", "Deaths",
                        "Interrupts", "Dispels", "Killing blows", "Pulls"], stretch=1)
        self.t.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.t.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.t.setVisible(False)
        for col, name in enumerate(["", "Player", "Role"] + list(STAT_HELP)):
            hi = self.t.horizontalHeaderItem(col)
            if hi and name in STAT_HELP:
                hi.setToolTip(STAT_HELP[name])
        self.lay.addWidget(self.t)
        self.lay.addStretch(1)

    def _toggle(self, on: bool):
        self.t.setVisible(on)
        self.more.setText("Hide the numbers" if on else "Show all the numbers")

    def set_analysis(self, a: Analysis | None):
        while self.standings.count():
            w = self.standings.takeAt(0).widget()
            if w:            # off the screen now, not when Qt gets round to deleting it
                w.hide()
                w.setParent(None)
                w.deleteLater()
        self.t.setRowCount(0)
        self.podium.set_analysis(a)
        if not a or not a.summary:
            self.head.setText("")
            self.sub.setText("")
            return
        s = a.summary
        self.head.setText(f"{a.data.run.zone} - summary")
        wipes = f" · {s.wipes} wipe{'s' if s.wipes != 1 else ''}" if s.wipes else ""
        self.sub.setText(f"{fmt_time(a.data.duration)} long, {fmt_time(s.combat_time)} in combat · bosses "
                         f"{s.bosses_killed}/{s.bosses} · {s.trash_killed} trash killed · "
                         f"{len(a.deaths)} death{'s' if len(a.deaths) != 1 else ''}{wipes}")
        for pl in a.ranking:
            self.standings.addWidget(StandingRow(a, pl))
        self._fill_numbers(a)

    def _fill_numbers(self, a: Analysis):
        s = a.summary
        stats = list(s.stats.values())
        keys = {  # column -> (value of a stat line, higher is "more")
            3: lambda st: st.damage, 4: lambda st: st.dps, 5: lambda st: st.boss_damage, 6: lambda st: st.healing,
            7: lambda st: st.overheal_share, 8: lambda st: st.taken, 9: lambda st: st.deaths,
            10: lambda st: st.interrupts, 11: lambda st: st.dispels, 12: lambda st: st.killing_blows,
            13: lambda st: st.pulls_started,
        }
        names = list(STAT_HELP)
        order = [pl.guid for pl in a.ranking]
        for st in sorted(stats, key=lambda st: order.index(st.player.guid) if st.player.guid in order else 99):
            p = st.player
            r = self.t.rowCount()
            self.t.insertRow(r)
            c = text_color(p)
            vals = ["●", p.name, ROLE_WORD.get(p.role or "DPS"), fmt_num(st.damage), f"{st.dps:.0f}",
                    fmt_num(st.boss_damage), fmt_num(st.healing), f"{st.overheal_share:.0%}" if st.healing else "",
                    fmt_num(st.taken), st.deaths or "", st.interrupts or "", st.dispels or "", st.killing_blows or "",
                    st.pulls_started or ""]
            for col, v in enumerate(vals):
                it = item(v, c if col in (0, 1) else theme.DEATH if col == 9 and v else None, align_right=col >= 3)
                if col in keys:
                    key = keys[col]
                    mine = key(st)
                    place = 1 + sum(1 for o in stats if key(o) > mine)
                    total = sum(key(o) for o in stats)
                    share = f", {mine / total:.0%} of the group's" if total and col not in (4, 7) else ""
                    it.setToolTip(f"<b>{p.name}</b> - {names[col - 3].lower()}: {STAT_HELP[names[col - 3]]}<br>"
                                  f"{ordinal(place)} highest in the group{share}")
                elif col in (0, 1):
                    pl = next((x for x in a.ranking if x.guid == p.guid), None)
                    if pl:
                        it.setToolTip(card_tooltip(a, pl))
                elif col == 2:
                    it.setToolTip(f"role: from {p.role_from}" if p.role_from != "you" else "role: your pick")
                self.t.setItem(r, col, it)
        self.t.setFixedHeight(self.t.horizontalHeader().height() + 4 +
                              sum(self.t.rowHeight(i) for i in range(self.t.rowCount())))
