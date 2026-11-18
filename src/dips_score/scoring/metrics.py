"""What happened in a run (or one fight), measured. Only measuring here; score.py judges it.

Everything is measured over combat time: the windows the player was in combat (the addon's R
lines), so walking between pulls doesn't count against you.
"""
from __future__ import annotations

import statistics
from collections import Counter
from dataclasses import dataclass, field

from ..model.run import AUTO_REPEAT, RunData, TLine

GCD = 1.5               # seconds; this client's global cooldown
AUTO_GAP = 2.0          # a wand shot keeps you "busy" this long (or until the next shot)
IDLE_GAP = 2.5          # gaps in activity at least this long are listed
MOVE_INTERRUPT_S = 0.6  # an interrupted cast this soon after you started moving was cut by moving
SPAM_WINDOW = 1.0       # the same button this many times inside this many seconds is a burst
SPAM_COUNT = 3
LOW_HP = 0.35

Interval = tuple[float, float]


# ----------------------------------------------------------------------------- intervals
def union(iv: list[Interval]) -> list[Interval]:
    out: list[Interval] = []
    for a, b in sorted(iv):
        if b <= a:
            continue
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def clip(iv: list[Interval], windows: list[Interval]) -> list[Interval]:
    out = []
    for a, b in union(iv):
        for wa, wb in windows:
            lo, hi = max(a, wa), min(b, wb)
            if hi > lo:
                out.append((lo, hi))
    return union(out)


def total(iv: list[Interval]) -> float:
    return sum(b - a for a, b in iv)


def gaps(iv: list[Interval], windows: list[Interval], min_len: float) -> list[Interval]:
    """Parts of the windows not covered by iv, at least min_len long."""
    out = []
    busy = union(iv)
    for wa, wb in windows:
        cur = wa
        for a, b in busy:
            if b <= wa or a >= wb:
                continue
            if a - cur >= min_len:
                out.append((cur, a))
            cur = max(cur, b)
        if wb - cur >= min_len:
            out.append((cur, wb))
    return out


def inside(t: float, windows: list[Interval]) -> bool:
    return any(a <= t <= b for a, b in windows)


# ----------------------------------------------------------------------------- the pieces
def busy_intervals(lines: list[TLine]) -> tuple[list[Interval], list[Interval]]:
    """(busy, wasted): when you were casting, channeling, on the GCD or wanding; and the cast
    time thrown away by casts that got interrupted."""
    busy: list[Interval] = []
    wasted: list[Interval] = []
    casting: tuple[int | None, float] | None = None
    channel: float | None = None
    shots: list[float] = []
    seg = None
    for ln in lines:
        if ln.seg != seg:
            casting, channel, seg = None, None, ln.seg
        c = ln.code
        sid = ln.num(0)
        if c == "CB":
            casting = (sid, ln.t)
        elif c in ("CK", "CF", "CI") and casting and casting[0] == sid:
            start = casting[1]
            if c == "CK":
                busy.append((start, max(ln.t, start + GCD)))
            else:
                busy.append((start, ln.t))
                if c == "CI":
                    wasted.append((start, ln.t))
            casting = None
        elif c == "CK":
            if sid in AUTO_REPEAT:
                shots.append(ln.t)
            else:
                busy.append((ln.t, ln.t + GCD))  # an instant: the GCD
        elif c == "CC":
            channel = ln.t
            busy.append((ln.t, ln.t + GCD))
        elif c == "CE" and channel is not None:
            busy.append((channel, ln.t))
            channel = None
    for i, t in enumerate(shots):
        nxt = shots[i + 1] if i + 1 < len(shots) else t + AUTO_GAP
        busy.append((t, t + min(AUTO_GAP, max(0.0, nxt - t))))
    return union(busy), wasted


def moving_intervals(lines: list[TLine], spans: list[Interval]) -> list[Interval]:
    out, start, seg = [], None, None
    for ln in lines:
        if ln.seg != seg:
            if start is not None and seg is not None:
                out.append((start, spans[seg][1]))
            start, seg = None, ln.seg
        if ln.code == "M":
            if ln.f(0) == "1" and start is None:
                start = ln.t
            elif ln.f(0) == "0" and start is not None:
                out.append((start, ln.t))
                start = None
    if start is not None and seg is not None:
        out.append((start, spans[seg][1]))
    return union(out)


# ----------------------------------------------------------------------------- metrics
@dataclass
class Metrics:
    combat_time: float = 0.0
    fights: int = 0
    # activity
    busy_time: float = 0.0
    idle_gaps: list[Interval] = field(default_factory=list)
    # casting
    casts: int = 0             # successful casts (not wand shots)
    failed: int = 0            # presses the game refused (not wand toggles)
    fail_reasons: Counter = field(default_factory=Counter)
    interrupted: int = 0
    move_interrupts: int = 0   # of those, cut by starting to move
    wasted_cast_time: float = 0.0
    # movement
    moving_time: float = 0.0
    # input
    presses: int = 0
    by_key: int = 0
    by_click: int = 0
    spam_bursts: int = 0
    hold_ms: list[float] = field(default_factory=list)
    first_press_delays: list[float] = field(default_factory=list)
    # survival
    deaths: int = 0
    lowest_hp: float | None = None
    low_hp_time: float = 0.0
    damage_taken: int = 0
    # output
    damage: int = 0
    healing: int = 0
    overheal: int = 0
    kills: int = 0
    has_log: bool = False

    @property
    def uptime(self) -> float:
        return self.busy_time / self.combat_time if self.combat_time else 0.0

    @property
    def per_min(self) -> float:
        """multiply a count by this for per-minute-of-combat"""
        return 60 / self.combat_time if self.combat_time else 0.0

    @property
    def fail_rate(self) -> float:
        n = self.casts + self.failed
        return self.failed / n if n else 0.0

    @property
    def presses_per_cast(self) -> float:
        return self.presses / self.casts if self.casts else 0.0

    @property
    def click_share(self) -> float:
        n = self.by_key + self.by_click
        return self.by_click / n if n else 0.0

    @property
    def moving_share(self) -> float:
        return self.moving_time / self.combat_time if self.combat_time else 0.0

    @property
    def dps(self) -> float:
        return self.damage / self.combat_time if self.combat_time else 0.0

    @property
    def hps(self) -> float:
        return self.healing / self.combat_time if self.combat_time else 0.0

    @property
    def overheal_share(self) -> float:
        n = self.healing + self.overheal
        return self.overheal / n if n else 0.0

    @property
    def median_first_press(self) -> float | None:
        return statistics.median(self.first_press_delays) if self.first_press_delays else None

    @property
    def median_hold_ms(self) -> float | None:
        return statistics.median(self.hold_ms) if self.hold_ms else None


def measure(rd: RunData, windows: list[Interval] | None = None) -> Metrics:
    """Metrics over the given windows (default: every fight in the run)."""
    if windows is None:
        windows = [(f.start, f.end) for f in rd.fights]
    windows = union(windows)
    m = Metrics(combat_time=total(windows), fights=len(windows), has_log=rd.has_combat_log)
    lines = rd.lines
    # only the stretch of the log these windows cover (a fight is a small slice of a long run)
    events = rd.events_between(windows[0][0] - 1, windows[-1][1] + 1) if windows else []

    busy, wasted = busy_intervals(lines)
    m.busy_time = total(clip(busy, windows))
    m.idle_gaps = gaps(busy, windows, IDLE_GAP)
    m.wasted_cast_time = total(clip(wasted, windows))
    moving = moving_intervals(lines, rd.segment_spans)
    m.moving_time = total(clip(moving, windows))

    # failure reasons from the combat log: SPELL_CAST_FAILED by you, same spell, close in time
    fails_log: dict[int, list[tuple[float, str]]] = {}
    for e in events:
        if e.event == "SPELL_CAST_FAILED" and rd.mine(e) and e.spell_id:
            fails_log.setdefault(e.spell_id, []).append((rd.rel(e.ts), e.reason))

    last_move_start = -1e9
    recent: dict[str, list[float]] = {}
    down: dict[str, float] = {}
    for ln in lines:
        c, t = ln.code, ln.t
        if c == "M" and ln.f(0) == "1":
            last_move_start = t
        if c == "KD":
            down[ln.f(0) + ":" + ln.f(1)] = t
        elif c == "KU":
            k = ln.f(0) + ":" + ln.f(1)
            if k in down and inside(down[k], windows):
                m.hold_ms.append((t - down.pop(k)) * 1000)
        if not inside(t, windows):
            continue
        sid = ln.num(0)
        if c == "CK" and sid not in AUTO_REPEAT:
            m.casts += 1
        elif c == "CF" and sid not in AUTO_REPEAT:
            m.failed += 1
            reason = "unknown"
            for ft, r in fails_log.get(sid or -1, []):
                if abs(ft - t) < 0.3:
                    reason = r or "unknown"
                    break
            m.fail_reasons[reason] += 1
        elif c == "CI":
            m.interrupted += 1
            if 0 <= t - last_move_start <= MOVE_INTERRUPT_S or inside(t, moving):
                m.move_interrupts += 1
        elif c == "A":
            if ln.f(1) == "spell" and ln.num(2) in AUTO_REPEAT:
                continue  # turning the wand on isn't a press we judge
            m.presses += 1
            src = ln.fields[-1] if ln.fields else "?"
            if src == "K":
                m.by_key += 1
            elif src == "C":
                m.by_click += 1
            slot = ln.f(0)
            r = [x for x in recent.get(slot, []) if t - x <= SPAM_WINDOW] + [t]
            if len(r) == SPAM_COUNT:
                m.spam_bursts += 1
            recent[slot] = r
        elif c == "D":
            m.deaths += 1

    # how fast you got going: first press (or cast sent) after each fight started
    for a, b in windows:
        first = next((ln.t for ln in lines if a <= ln.t <= b and ln.code in ("A", "CS")), None)
        if first is not None:
            m.first_press_delays.append(first - a)

    # the combat log: what it did
    hp: list[tuple[float, float]] = []
    for e in events:
        t = rd.rel(e.ts)
        if not inside(t, windows):
            continue
        ev = e.event
        if e.info and e.info.guid == rd.player_guid and e.info.max_hp:
            hp.append((t, e.info.hp_pct))
        if ev.endswith("_DAMAGE") and not ev.endswith("_LANDED"):
            if rd.mine(e):
                m.damage += e.amount
            if rd.to_me(e):
                m.damage_taken += e.amount
        elif ev.endswith("_HEAL") and rd.mine(e):
            m.healing += max(0, e.amount - e.overheal)
            m.overheal += e.overheal
        elif ev == "PARTY_KILL" and rd.mine(e):
            m.kills += 1
    if hp:
        m.lowest_hp = min(p for _, p in hp)
        for (t1, p1), (t2, _) in zip(hp, hp[1:]):
            if p1 < LOW_HP:
                m.low_hp_time += min(t2 - t1, 5.0)
    return m
