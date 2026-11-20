"""The timeline: one lane per thing, all on the same clock.

    Pulls      each fight (bosses in purple); hover for the mobs, markers, who pulled, kill order
    Deaths     an X per death in the dead player's class color; wipes shade every lane red
    Response   (healer) each dip under 60%: a bar until you started a heal on them -
               green under 1.5s, orange under 3s, red slower; long red: no heal from you; grey: covered
    Activity   (dps) busy (green) / idle gaps of 2.5s+ (red)
    Casts      your cast bars: blue ok, red interrupted; orange ticks: refused presses
    Presses    one tick per press: white key, orange click; red under a mash burst
    Moving     when you were moving
    then, for every player (tank, healers, damage; names in class colors):
      spells   every cast, colored by spell (a bar for cast times); hover for spell and target
      health   their health, 0-100%; X: death

Mouse wheel zooms at the pointer, drag pans, double-click shows the whole run. Hover for details.
`highlight(guid, spell)` dims every cast but that spell's (from the Spells tab).
"""
from __future__ import annotations

import zlib
from bisect import bisect_left, bisect_right
from dataclasses import dataclass, field

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QToolTip, QWidget

from ..analysis import Analysis
from ..model.casts import CastEvent
from ..model.deaths import Death, Wipe
from ..model.pulls import Pull
from ..model.roster import Player
from ..model.run import AUTO_REPEAT
from ..scoring.healer import RESPONSE_CAP, Dip
from ..scoring.metrics import GCD, SPAM_COUNT, SPAM_WINDOW, busy_intervals, gaps, moving_intervals
from . import assets, theme

GUTTER = 118
AXIS_H = 22
ROW = 24
SPELL_ROW = 20
HEALTH_ROW = 54
ROLE_ORDER = {"TANK": 0, "HEALER": 1, "DPS": 2}


def text_color(p: Player | None) -> QColor:
    """the class colour, darkened if needed so a name reads on the panel (day themes)"""
    return theme.readable(player_color(p))


def player_color(p: Player | None) -> QColor:
    if not p:
        return QColor(190, 190, 200)
    r, g, b = p.color
    return QColor(int(r * 255), int(g * 255), int(b * 255))


def spell_color(name: str) -> QColor:
    """a steady color per spell name"""
    h = zlib.crc32(name.encode()) % 360
    return QColor.fromHsv(h, 150, 235)


@dataclass
class Cast:
    start: float
    end: float
    spell: int | None
    result: str     # "ok", "interrupted", "failed", "instant"


@dataclass
class Lane:
    key: str               # "pulls", "deaths", ..., "spells", "health"
    label: str
    height: int
    color: QColor = field(default_factory=lambda: QColor(theme.DIM))
    guid: str | None = None
    top: float = 0.0


@dataclass
class Data:
    role: str = "healer"
    duration: float = 1.0
    pulls: list[Pull] = field(default_factory=list)
    busy: list[tuple[float, float]] = field(default_factory=list)
    idle: list[tuple[float, float]] = field(default_factory=list)
    casts: list[Cast] = field(default_factory=list)
    fails: list[tuple[float, int | None]] = field(default_factory=list)
    presses: list[tuple[float, str, bool, str]] = field(default_factory=list)
    moving: list[tuple[float, float]] = field(default_factory=list)
    dips: list[Dip] = field(default_factory=list)
    deaths: list[Death] = field(default_factory=list)
    wipes: list[Wipe] = field(default_factory=list)
    players: list[Player] = field(default_factory=list)
    roster: dict[str, Player] = field(default_factory=dict)
    player_casts: dict[str, list[CastEvent]] = field(default_factory=dict)
    hp: dict[str, list[tuple[float, float]]] = field(default_factory=dict)
    names: dict[int, str] = field(default_factory=dict)
    hits: dict[str, list[tuple[float, int, str, str]]] = field(default_factory=dict)   # on each player: t, amount, spell, from

    def name(self, sid: int | None) -> str:
        return "?" if sid is None else self.names.get(sid, f"spell {sid}")


def build_data(a: Analysis) -> Data:
    rd = a.data
    D = Data(role=a.role, duration=max(1.0, rd.duration), pulls=a.pulls, dips=a.healer.dips,
             deaths=a.deaths, wipes=a.wipes, roster=a.roster, player_casts=a.casts)
    D.players = sorted(a.roster.values(), key=lambda p: (ROLE_ORDER.get(p.role or "DPS", 3), not p.is_me, p.name))
    busy, _ = busy_intervals(rd.lines)
    D.busy = busy
    D.idle = gaps(busy, [(f.start, f.end) for f in rd.fights], 2.5)
    D.moving = moving_intervals(rd.lines, rd.segment_spans)
    for e in rd.events:
        if e.spell_id and e.spell_name:
            D.names.setdefault(e.spell_id, e.spell_name)
        if e.dst in a.roster and e.event.endswith("_DAMAGE") and not e.event.endswith("_LANDED") and e.amount:
            src = a.roster[e.src].name if e.src in a.roster else (e.src_name or "?")
            D.hits.setdefault(e.dst, []).append((rd.rel(e.ts), e.amount, e.spell_name or "Melee", src))
        if e.info and e.info.guid in a.roster and e.info.max_hp:
            D.hp.setdefault(e.info.guid, []).append((rd.rel(e.ts), e.info.hp_pct))

    casting: tuple[int | None, float] | None = None
    recent: dict[str, list[float]] = {}
    for ln in rd.lines:
        c, t, sid = ln.code, ln.t, ln.num(0)
        if c == "CB":
            casting = (sid, t)
        elif c in ("CK", "CF", "CI") and casting and casting[0] == sid:
            D.casts.append(Cast(casting[1], t, sid, {"CK": "ok", "CF": "failed", "CI": "interrupted"}[c]))
            casting = None
            if c == "CF":
                D.fails.append((t, sid))
        elif c == "CK" and sid not in AUTO_REPEAT:
            D.casts.append(Cast(t, t + GCD, sid, "instant"))
        elif c == "CF" and sid not in AUTO_REPEAT:
            D.fails.append((t, sid))
        elif c == "A":
            slot = ln.f(0)
            r = [x for x in recent.get(slot, []) if t - x <= SPAM_WINDOW] + [t]
            recent[slot] = r
            what = D.name(ln.num(2)) if ln.f(1) == "spell" else f"{ln.f(1)} {ln.f(2)}"
            D.presses.append((t, ln.fields[-1] if ln.fields else "?", len(r) >= SPAM_COUNT, what))
    return D


REACT_MIN, REACT_MAX = 0.2, 3.0   # a cast this soon after a drop is a response to it (human reaction time,
                                 # then a little to pick the spell); sooner is too fast to be one
DROP = 0.10                      # health falling at least this much ...
DROP_WITHIN = 3.0                # ... inside this many seconds is a sharp drop


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _health_at(series, t: float):
    """(health at t, change over the 2 seconds before)"""
    if not series:
        return None, None
    times = [x for x, _ in series]
    i = bisect_right(times, t) - 1
    if i < 0:
        return None, None
    now = series[i][1]
    j = bisect_right(times, t - 2.0) - 1
    before = series[j][1] if j >= 0 else None
    return now, (now - before) if before is not None else None


def _sharp_drop(series, t: float):
    """a fall of DROP or more ending in the DROP_WITHIN seconds up to t: (when it started, from, to)"""
    if not series:
        return None
    times = [x for x, _ in series]
    lo, hi = bisect_left(times, t - DROP_WITHIN - 2.0), bisect_right(times, t)
    pts = series[lo:hi]
    best = None
    for k, (tk, pk) in enumerate(pts):
        if tk > t:
            break
        later = [(tj, pj) for tj, pj in pts[k + 1:] if tj - tk <= DROP_WITHIN and tj >= t - DROP_WITHIN]
        if not later:
            continue
        tj, low = min(later, key=lambda v: v[1])
        if pk - low >= DROP and (best is None or pk - low > best[1] - best[2]):
            start = next((tx for tx, px in pts[k + 1:] if px < pk - 0.02), tj)
            best = (start, pk, low)
    return best


def _casting_at(casts, t: float) -> str:
    """what a player is casting at t (a cast bar, or an instant within half a second)"""
    for c in casts:
        a = c.began if c.began is not None else c.t - 0.25
        if a - 0.25 <= t <= c.t + 0.25:
            tgt = f" on {c.target}" if c.target else ""
            state = "" if c.ok else " (failed)"
            return _esc(f"{c.spell}{tgt}{state}")
    return ""


def _reactions(D, p, t0: float):
    """casts that started REACT_MIN-REACT_MAX after t0 and answer p's drop: anyone's cast on p, or p's own next
    casts. (player, cast, delay)"""
    out = []
    first = p.name.split(" ")[0]
    for who in D.players:
        for c in D.player_casts.get(who.guid, []):
            start = c.began if c.began is not None else c.t
            delay = start - t0
            if delay < REACT_MIN or delay > REACT_MAX or c.auto or not c.ok:
                continue
            if who.guid == p.guid or (c.target and c.target.split(" ")[0] == first):
                out.append((who, c, delay))
    out.sort(key=lambda r: r[2])
    return out[:5]


def _fmt(t: float) -> str:
    sign = "-" if t < 0 else ""
    t = abs(t)
    return f"{sign}{int(t // 60)}:{t % 60:04.1f}"


def _dip_color(d: Dip) -> QColor:
    if d.covered:
        return QColor(150, 150, 160, 120)
    if d.response is None:
        return QColor(240, 80, 80, 110)
    if d.response <= 1.5:
        return theme.BUSY
    if d.response <= 3.0:
        return theme.FAIL
    return theme.IDLE


def pull_text(pl: Pull, roster: dict[str, Player]) -> str:
    """the hover text for a pull (also used by the Pulls tab)"""
    name = lambda g: roster[g].name if g in roster else "?"  # noqa: E731
    lines = [f"{pl.fight.label} at {_fmt(pl.start)}, {pl.fight.duration:.0f}s"]
    for i, pk in enumerate(pl.packs, 1):
        head = "Extra pack" if pk.extra else "Pack"
        lines.append(f"{head} {i} at {_fmt(pk.start)}: {name(pk.puller)} ({pk.how})")
        for en in pk.enemies:
            mark = f"[{en.marker}] " if en.marker else ""
            lines.append(f"   {mark}{en.name}")
    order = pl.kill_order
    if order:
        lines.append("Kill order:")
        for n, en in enumerate(order, 1):
            mark = f"[{en.marker}] " if en.marker else ""
            by = f" - {name(en.killer)}" + (f", {en.killing_blow}" if en.killing_blow else "") if en.killer else ""
            lines.append(f"   {n}. {_fmt(en.died)}  {mark}{en.name}{by}")
    return "\n".join(lines)


class Timeline(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.D: Data | None = None
        self.lanes: list[Lane] = []
        self.v0, self.v1 = 0.0, 60.0
        self.hl_guid: str | None = None
        self.hl_spell: str | None = None
        self._drag: tuple[float, float, float] | None = None
        self.hover_x: float | None = None     # the crosshair
        self.setMouseTracking(True)
        self._layout()

    # -------------------------------------------------------------- data and view
    def set_analysis(self, a: Analysis | None):
        self.D = build_data(a) if a else None
        self.hl_guid = self.hl_spell = None
        self._layout()
        self.show_all()

    def _layout(self):
        L: list[Lane] = [Lane("pulls", "Pulls", ROW), Lane("deaths", "Deaths", ROW)]
        role = self.D.role if self.D else "healer"
        L.append(Lane("response", "Response", ROW) if role == "healer" else Lane("activity", "Activity", ROW))
        L += [Lane("casts", "Your casts", ROW), Lane("presses", "Presses", ROW), Lane("moving", "Moving", ROW)]
        for p in (self.D.players if self.D else []):
            c = player_color(p)
            L.append(Lane("spells", p.name, SPELL_ROW, c, p.guid))
            L.append(Lane("health", "health", HEALTH_ROW, c, p.guid))
        y = AXIS_H
        for ln in L:
            ln.top = y
            y += ln.height + (8 if ln.key == "health" else 4)
        self.lanes = L
        self._height = int(y + 6)
        self.setMinimumHeight(self._height)
        self.updateGeometry()

    def sizeHint(self) -> QSize:
        return QSize(900, self._height)

    def show_all(self):
        d = self.D.duration if self.D else 60
        self.set_view(-d * 0.01, d * 1.01)

    def set_view(self, a: float, b: float):
        if b - a < 2:
            mid = (a + b) / 2
            a, b = mid - 1, mid + 1
        self.v0, self.v1 = a, b
        self.update()

    def highlight(self, guid: str | None, spell: str | None):
        self.hl_guid, self.hl_spell = guid, spell
        self.update()

    def x(self, t: float) -> float:
        return GUTTER + (t - self.v0) / (self.v1 - self.v0) * (self.width() - GUTTER - 8)

    def t(self, x: float) -> float:
        return self.v0 + (x - GUTTER) / (self.width() - GUTTER - 8) * (self.v1 - self.v0)

    def lane_rect(self, lane: Lane) -> QRectF:
        return QRectF(GUTTER, lane.top, self.width() - GUTTER - 8, lane.height)

    def lane_at(self, y: float) -> Lane | None:
        for ln in self.lanes:
            if ln.top - 2 <= y <= ln.top + ln.height + 2:
                return ln
        return None

    def lane(self, key: str) -> Lane | None:
        return next((ln for ln in self.lanes if ln.key == key), None)

    # -------------------------------------------------------------- input
    def wheelEvent(self, ev):
        if ev.modifiers() & Qt.KeyboardModifier.ShiftModifier or ev.angleDelta().y() == 0:
            return super().wheelEvent(ev)   # let the scroll area scroll
        t = self.t(ev.position().x())
        f = 0.8 if ev.angleDelta().y() > 0 else 1.25
        self.set_view(t - (t - self.v0) * f, t + (self.v1 - t) * f)
        ev.accept()

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self._drag = (ev.position().x(), self.v0, self.v1)

    def mouseMoveEvent(self, ev):
        x = ev.position().x()
        self.hover_x = x if x >= GUTTER else None
        if self._drag:
            x0, a, b = self._drag
            dt = (x - x0) / (self.width() - GUTTER - 8) * (b - a)
            self.set_view(a - dt, b - dt)
            return
        self.update()
        self._hover(ev)

    def leaveEvent(self, ev):
        self.hover_x = None
        self.update()
        QToolTip.hideText()

    def mouseReleaseEvent(self, ev):
        self._drag = None

    def mouseDoubleClickEvent(self, ev):
        self.show_all()

    def _hover(self, ev):
        D = self.D
        pos = ev.position()
        lane = self.lane_at(pos.y())
        if not D or lane is None or pos.x() < GUTTER:
            QToolTip.hideText()
            return
        t = self.t(pos.x())
        tol = 6 / (self.width() - GUTTER) * (self.v1 - self.v0)
        detail = getattr(self, f"_tip_{lane.key}")(lane, t, tol)
        QToolTip.showText(ev.globalPosition().toPoint(), self.moment_html(t, detail), self)

    # the moment under the crosshair --------------------------------------------------------------
    def moment_html(self, t: float, detail: str | None) -> str:
        """what's under the pointer (detail), then everyone at time t: health and its change, hits taken,
        what they're casting, and for a sharp drop, who reacted and how fast"""
        D = self.D
        out = [f"<b>{_fmt(t)}</b>"]
        if detail:
            out.append(_esc(detail).replace("\n", "<br>"))
        rows = []
        for p in D.players:
            g = p.guid
            color = text_color(p).name()
            hp_now, change = _health_at(D.hp.get(g, []), t)
            hp = "" if hp_now is None else f"{hp_now:.0%}"
            if change is not None and abs(change) >= 0.05:
                c = theme.DEATH.name() if change < 0 else theme.grade_color("S").name()
                hp += f" <span style='color:{c}'>({change:+.0%})</span>"
            taken = sum(a for tt, a, _, _ in D.hits.get(g, []) if t - 1.5 <= tt <= t)
            doing = _casting_at(D.player_casts.get(g, []), t)
            dead = any(d.guid == g and d.t <= t and (t - d.t) < 30 for d in D.deaths)
            line = (f"<tr><td style='color:{color}'><b>{p.name}</b></td><td align=right>{'dead' if dead else hp}</td>"
                    f"<td>&nbsp;{('-' + format(taken, ',') + ' taken') if taken else ''}</td>"
                    f"<td>&nbsp;{doing}</td></tr>")
            rows.append(line)
            drop = _sharp_drop(D.hp.get(g, []), t)
            if drop:
                t0, frm, to = drop
                hits = [h for h in D.hits.get(g, []) if t0 - 1 <= h[0] <= t0 + 1.5]
                cause = ""
                if hits:
                    big = max(hits, key=lambda h: h[1])
                    cause = f" by {big[2]} ({big[3]})"
                rows.append(f"<tr><td></td><td colspan=3 style='color:{theme.readable(theme.FAIL).name()}'>dropped {frm:.0%} -> {to:.0%} at "
                            f"{_fmt(t0)}{_esc(cause)}</td></tr>")
                for who, c, delay in _reactions(D, p, t0):
                    own = who.guid == g
                    what = f"{c.spell}" + ("" if own else f" on {p.name.split(' ')[0]}")
                    rows.append(f"<tr><td></td><td colspan=3>&nbsp;&rarr; <span style='color:{text_color(who).name()}'>"
                                f"{'their next cast' if own else who.name}</span>: {_esc(what)} "
                                f"<span style='color:{theme.DIM.name()}'>{delay:.1f}s after</span></td></tr>")
        if rows:
            out.append("<table cellspacing=1>" + "".join(rows) + "</table>")
        return "<br>".join(out)

    # hover texts, one per lane kind
    def _tip_pulls(self, lane, t, tol):
        for pl in self.D.pulls:
            if pl.start <= t <= pl.fight.end:
                return pull_text(pl, self.D.roster)

    def _tip_deaths(self, lane, t, tol):
        for d in self.D.deaths:
            if abs(d.t - t) <= tol * 2:
                lines = [f"{d.name} died at {_fmt(d.t)}" + (f" - {d.killed_by}" if d.killed_by else "")]
                for r in d.recap[-8:]:
                    hp = f"  ({r.hp:.0%})" if r.hp is not None else ""
                    sign = "-" if r.kind == "hit" else "+"
                    lines.append(f"  {r.t:5.1f}s  {sign}{r.amount:,}  {r.spell} ({r.source}){hp}")
                return "\n".join(lines)
        for w in self.D.wipes:
            first = min((d.t for d in w.deaths), default=w.t)
            if first - tol <= t <= w.t + tol:
                return f"Wipe{' on ' + w.boss if w.boss else ''} at {_fmt(w.t)}: " + ", ".join(d.name for d in w.deaths)

    def _tip_response(self, lane, t, tol):
        for d in self.D.dips:
            end = d.start + (d.response if d.response is not None else RESPONSE_CAP)
            if d.start - tol <= t <= max(end, d.start) + tol:
                head = f"{d.name} fell to {d.hp:.0%} at {_fmt(d.start)}"
                if d.response is not None:
                    return f"{head}\nyou started {d.spell} {d.response:.1f}s later"
                if d.covered:
                    return f"{head}\nback up without you (someone else covered it)"
                return f"{head}\nno heal from you within {RESPONSE_CAP:.0f}s"

    def _tip_activity(self, lane, t, tol):
        for a, b in self.D.idle:
            if a <= t <= b:
                return f"Idle {b - a:.1f}s\n{_fmt(a)} - {_fmt(b)}"

    def _tip_casts(self, lane, t, tol):
        near = [f for f in self.D.fails if abs(f[0] - t) <= tol]
        if near:
            return "Refused: " + ", ".join(self.D.name(s) for _, s in near)
        for c in self.D.casts:
            instant = c.result == "instant"
            if (abs(c.start - t) <= tol) if instant else (c.start - tol <= t <= c.end + tol):
                return f"{self.D.name(c.spell)} - {c.result}\n{_fmt(c.start)}" + \
                       ("" if instant else f", {c.end - c.start:.2f}s cast")

    def _tip_presses(self, lane, t, tol):
        near = [p for p in self.D.presses if abs(p[0] - t) <= tol]
        if near:
            return "\n".join(f"{_fmt(p[0])}  {p[3]}  ({'key' if p[1] == 'K' else 'click' if p[1] == 'C' else '?'})"
                             + ("  mashing" if p[2] else "") for p in near[:6])

    def _tip_moving(self, lane, t, tol):
        for a, b in self.D.moving:
            if a <= t <= b:
                return f"Moving {b - a:.1f}s"

    def _tip_spells(self, lane, t, tol):
        out = []
        for c in self.D.player_casts.get(lane.guid, []):
            a = c.began if c.began is not None else c.t
            if a - tol <= t <= c.t + tol:
                tgt = f" on {c.target}" if c.target else ""
                state = "" if c.ok else f" - failed{': ' + c.reason if c.reason else ''}"
                length = f", {c.t - c.began:.1f}s cast" if c.began is not None else ""
                out.append(f"{_fmt(c.t)}  {c.spell}{tgt}{length}{state}")
        if out:
            return f"{self.D.roster[lane.guid].name}\n" + "\n".join(out[:8])

    def _tip_health(self, lane, t, tol):
        series = self.D.hp.get(lane.guid, [])
        near = [(tt, p) for tt, p in series if abs(tt - t) < 3]
        if near:
            tt, p = min(near, key=lambda v: abs(v[0] - t))
            return f"{self.D.roster[lane.guid].name}: {p:.0%} at {_fmt(tt)}"

    # -------------------------------------------------------------- drawing
    def paintEvent(self, ev):
        p = QPainter(self)
        p.setFont(QFont(theme.FONT, 8))
        for ln in self.lanes:
            r = self.lane_rect(ln)
            p.fillRect(r, theme.LANE if ln.key != "health" else QColor(24, 24, 30))
            if ln.key == "health":
                continue
            p.setPen(theme.readable(ln.color, theme.BG) if ln.key == "spells" else theme.DIM)
            if ln.key == "spells":
                f = QFont(theme.FONT, 9)
                f.setBold(True)
                p.setFont(f)
                p.drawText(QRectF(4, r.top(), GUTTER - 10, r.height() + HEALTH_ROW),
                           Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight, ln.label)
                cls = self.D.roster[ln.guid].cls if self.D and ln.guid in self.D.roster else None
                cls_pm = assets.class_pixmap(cls)
                if cls_pm is not None:
                    p.drawPixmap(QRectF(4, r.top() + 18, 18, 18).toRect(), cls_pm)
                role = self.D.roster[ln.guid].role if self.D and ln.guid in self.D.roster else ""
                p.setFont(QFont(theme.FONT, 8))
                p.setPen(theme.DIM)
                p.drawText(QRectF(4, r.top() + 16, GUTTER - 10, 14),
                           Qt.AlignmentFlag.AlignRight, (role or "").lower())
            else:
                p.drawText(QRectF(4, r.top(), GUTTER - 10, r.height()),
                           Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, ln.label)
        self._axis(p)
        D = self.D
        if not D:
            p.setPen(theme.DIM)
            p.drawText(QRectF(0, 0, self.width(), self.height()), Qt.AlignmentFlag.AlignCenter, "No run selected")
            return
        p.setClipRect(QRectF(GUTTER, 0, self.width() - GUTTER - 8, self.height()))
        for ln in self.lanes:
            getattr(self, f"_draw_{ln.key}")(p, ln, self.lane_rect(ln))
        # the crosshair, through every lane, with the time on the axis
        if self.hover_x is not None:
            p.setPen(QPen(QColor(255, 255, 255, 110), 1))
            p.drawLine(QPointF(self.hover_x, AXIS_H), QPointF(self.hover_x, self.height()))
            p.setPen(theme.EDGE)
            p.setBrush(theme.PANEL)
            p.drawRect(QRectF(self.hover_x - 28, 2, 56, AXIS_H - 6))
            p.setPen(theme.TEXT)
            p.drawText(QRectF(self.hover_x - 28, 2, 56, AXIS_H - 6), Qt.AlignmentFlag.AlignCenter,
                       _fmt(self.t(self.hover_x)))
        # wipes: a red wash over everything
        for w in D.wipes:
            first = min((d.t for d in w.deaths), default=w.t - 3)
            x0, x1 = self.x(first), self.x(w.t + 2)
            p.fillRect(QRectF(x0, AXIS_H, max(3.0, x1 - x0), self.height() - AXIS_H), QColor(200, 30, 30, 45))

    def _axis(self, p: QPainter):
        span = self.v1 - self.v0
        step = next((s for s in (1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 1800) if span / s <= 12), 3600)
        t = (self.v0 // step) * step
        while t <= self.v1:
            x = self.x(t)
            if x >= GUTTER:
                p.setPen(theme.GRID)
                p.drawLine(QPointF(x, AXIS_H), QPointF(x, self.height()))
                p.setPen(theme.DIM)
                p.drawText(QPointF(x + 3, AXIS_H - 7), f"{int(t // 60)}:{int(t % 60):02d}")
            t += step

    def _span(self, p, r: QRectF, a: float, b: float, color: QColor, inset: float = 0, min_w: float = 1.0):
        if b < self.v0 or a > self.v1:
            return
        x0, x1 = self.x(a), self.x(b)
        p.fillRect(QRectF(x0, r.top() + inset, max(min_w, x1 - x0), r.height() - 2 * inset), color)

    def _draw_pulls(self, p, ln, r):
        for pl in self.D.pulls:
            boss = pl.fight.boss is not None
            self._span(p, r, pl.start, pl.fight.end, theme.BOSS if boss else theme.COMBAT)
            for pk in pl.packs[1:]:   # extra packs: a bright tick where they joined
                x = self.x(pk.start)
                p.fillRect(QRectF(x - 1, r.top(), 3, r.height()), theme.FAIL)
            x0, x1 = self.x(pl.start), self.x(pl.fight.end)
            if x1 - x0 > 40:
                p.setPen(theme.TEXT)
                n = len(pl.enemies)
                label = pl.fight.label + (f" ({n})" if n and not boss else "")
                p.drawText(QRectF(x0 + 3, r.top(), x1 - x0 - 6, r.height()), Qt.AlignmentFlag.AlignVCenter, label)

    def _draw_deaths(self, p, ln, r):
        cy = r.center().y()
        for d in self.D.deaths:
            x = self.x(d.t)
            p.setPen(QPen(player_color(self.D.roster.get(d.guid)), 2))
            p.drawLine(QPointF(x - 5, cy - 5), QPointF(x + 5, cy + 5))
            p.drawLine(QPointF(x - 5, cy + 5), QPointF(x + 5, cy - 5))
            if self.v1 - self.v0 < 600:
                p.drawText(QPointF(x + 8, cy + 4), d.name.split(" ")[0])

    def _draw_response(self, p, ln, r):
        for d in self.D.dips:
            end = d.start + (d.response if d.response is not None else RESPONSE_CAP)
            self._span(p, r, d.start, end, _dip_color(d), inset=4, min_w=3)
            x = self.x(d.start)
            p.fillRect(QRectF(x - 1, r.top() + 1, 2, r.height() - 2), theme.TEXT)

    def _draw_activity(self, p, ln, r):
        for a, b in self.D.busy:
            self._span(p, r, a, b, theme.BUSY, inset=6)
        for a, b in self.D.idle:
            self._span(p, r, a, b, theme.IDLE, inset=3)

    def _draw_casts(self, p, ln, r):
        colors = {"ok": theme.CAST_OK, "interrupted": theme.CAST_BAD, "failed": theme.FAIL}
        for c in self.D.casts:
            if c.result == "instant":
                p.fillRect(QRectF(self.x(c.start) - 1, r.top() + 4, 3, r.height() - 8), theme.CAST)
            else:
                self._span(p, r, c.start, c.end, colors[c.result], inset=4)
        p.setPen(QPen(theme.FAIL, 1))
        for t, _ in self.D.fails:
            x = self.x(t)
            p.drawLine(QPointF(x, r.top()), QPointF(x, r.top() + 5))

    def _draw_presses(self, p, ln, r):
        for t, src, burst, _ in self.D.presses:
            x = self.x(t)
            p.setPen(QPen(theme.CLICK if src == "C" else theme.KEY, 1))
            p.drawLine(QPointF(x, r.top() + 3), QPointF(x, r.bottom() - 5))
            if burst:
                p.fillRect(QRectF(x - 1, r.bottom() - 4, 3, 3), theme.SPAM)

    def _draw_moving(self, p, ln, r):
        for a, b in self.D.moving:
            self._span(p, r, a, b, theme.MOVE, inset=6)

    def _draw_spells(self, p, ln, r):
        active = self.hl_spell is not None
        px_per_s = (self.width() - GUTTER - 8) / max(0.001, self.v1 - self.v0)
        show_icons = px_per_s >= 12          # about 1.5 s per icon: room to tell them apart
        for c in self.D.player_casts.get(ln.guid, []):
            if c.t < self.v0 - 10 or (c.began or c.t) > self.v1:
                continue
            color = QColor(spell_color(c.spell))
            if not c.ok:
                color = QColor(theme.FAIL)
            if active and not (ln.guid == self.hl_guid and c.spell == self.hl_spell):
                color.setAlpha(35)
            pm = assets.spell_pixmap(c.spell_id) if show_icons and not c.auto else None
            if c.began is not None and c.ok:
                self._span(p, r, c.began, c.t, color, inset=4, min_w=2)
            if pm is not None:
                size = r.height() - 2
                if active and not (ln.guid == self.hl_guid and c.spell == self.hl_spell):
                    p.setOpacity(0.25)
                p.drawPixmap(QRectF(self.x(c.t) - size / 2, r.top() + 1, size, size).toRect(), pm)
                p.setOpacity(1.0)
            elif c.began is None or not c.ok:
                h = r.height() - 6 if not c.auto else r.height() - 12
                p.fillRect(QRectF(self.x(c.t) - 1, r.bottom() - 3 - h, 2 if c.auto else 3, h), color)

    def _draw_health(self, p, ln, r):
        y = lambda pct: r.bottom() - 2 - pct * (r.height() - 4)  # noqa: E731
        for frac in (0.35, 0.60):
            p.setPen(QPen(QColor(255, 255, 255, 22), 1, Qt.PenStyle.DashLine))
            p.drawLine(QPointF(r.left(), y(frac)), QPointF(r.right(), y(frac)))
        series = [(t, v) for t, v in self.D.hp.get(ln.guid, []) if self.v0 - 10 <= t <= self.v1 + 10]
        if not series:
            return
        path, fill = QPainterPath(), QPainterPath()
        fill.moveTo(QPointF(self.x(series[0][0]), r.bottom()))
        for i, (t, v) in enumerate(series):
            pt = QPointF(self.x(t), y(v))
            (path.moveTo if i == 0 else path.lineTo)(pt)
            fill.lineTo(pt)
        fill.lineTo(QPointF(self.x(series[-1][0]), r.bottom()))
        fill.closeSubpath()
        c = QColor(ln.color)
        c.setAlpha(40)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.fillPath(fill, c)
        p.setPen(QPen(ln.color, 1.3))
        p.drawPath(path)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        p.setPen(QPen(theme.DEATH, 2))
        for d in self.D.deaths:
            if d.guid == ln.guid:
                x, cy = self.x(d.t), r.center().y()
                p.drawLine(QPointF(x - 5, cy - 5), QPointF(x + 5, cy + 5))
                p.drawLine(QPointF(x - 5, cy + 5), QPointF(x + 5, cy - 5))
