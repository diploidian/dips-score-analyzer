"""One run with both data streams merged on one clock: the addon's lines and the combat log's
events, in seconds since the run started."""
from __future__ import annotations

from bisect import bisect_left
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from ..sources import combatlog
from ..sources.combatlog import Event
from ..sources.savedvars import Run
from .sync import SegmentClock, SyncReport, refine

# spells that repeat by themselves once started: each shot is a "cast", but not a press or a GCD
AUTO_REPEAT = frozenset({5019, 75})  # Shoot (wands), Auto Shot


@dataclass(slots=True)
class TLine:
    t: float          # seconds since the run started
    code: str
    fields: list[str]
    seg: int          # which segment

    def f(self, i: int, default: str = "") -> str:
        return self.fields[i] if i < len(self.fields) else default

    def num(self, i: int) -> int | None:
        try:
            return int(self.f(i))
        except ValueError:
            return None


@dataclass
class Fight:
    start: float
    end: float
    boss: str | None = None
    encounter_id: int | None = None
    killed: bool | None = None

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)

    @property
    def label(self) -> str:
        return self.boss or "Trash"


@dataclass
class RunData:
    run: Run
    start: datetime
    end: datetime
    lines: list[TLine]
    events: list[Event]
    player_guid: str | None
    sync: list[SyncReport]
    fights: list[Fight] = field(default_factory=list)
    segment_spans: list[tuple[float, float]] = field(default_factory=list)
    log_files: list[Path] = field(default_factory=list)

    def rel(self, ts: datetime) -> float:
        return (ts - self.start) / timedelta(seconds=1)

    @property
    def duration(self) -> float:
        return self.rel(self.end)

    @property
    def combat_time(self) -> float:
        return sum(f.duration for f in self.fights)

    @property
    def has_combat_log(self) -> bool:
        return bool(self.events)

    @property
    def has_advanced(self) -> bool:
        """the log has the Advanced Combat Logging block (health, power, position)"""
        return any(e.info for e in self.events)

    def mine(self, e: Event) -> bool:
        return bool(self.player_guid) and e.src == self.player_guid

    def to_me(self, e: Event) -> bool:
        return bool(self.player_guid) and e.dst == self.player_guid

    def event_times(self) -> list[float]:
        return [self.rel(e.ts) for e in self.events]

    def events_between(self, a: float, b: float) -> list[Event]:
        times = self._times()
        return self.events[bisect_left(times, a):bisect_left(times, b)]

    def _times(self) -> list[float]:
        if not hasattr(self, "_tcache") or len(self._tcache) != len(self.events):
            self._tcache = self.event_times()
        return self._tcache


def _find_player(events: list[Event], name: str) -> str | None:
    """The player's GUID: the Player- GUID casting most under the character's name."""
    counts = Counter(e.src for e in events
                     if e.src.startswith("Player-") and (e.src_name == name or e.src_name.startswith(name + "-")))
    return counts.most_common(1)[0][0] if counts else None


def _fights(lines: list[TLine], spans: list[tuple[float, float]], events: list[Event], rd: RunData) -> list[Fight]:
    fights: list[Fight] = []
    cur: float | None = None
    seg = 0
    for ln in lines:
        if ln.seg != seg:  # a new segment: a fight open across a /reload ends at the old segment's end
            if cur is not None:
                fights.append(Fight(cur, spans[seg][1]))
                cur = None
            seg = ln.seg
        if ln.code == "R":
            if ln.f(0) == "1" and cur is None:
                cur = ln.t
            elif ln.f(0) == "0" and cur is not None:
                fights.append(Fight(cur, ln.t))
                cur = None
    if cur is not None:
        fights.append(Fight(cur, spans[seg][1]))
    # bosses: the addon's E lines, named from the combat log
    names = {}
    for e in events:
        if e.event == "ENCOUNTER_START" and e.raw and len(e.raw) > 1:
            names[combatlog._int(e.raw[0])] = e.raw[1]
    for ln in lines:
        if ln.code != "E":
            continue
        for f in fights:
            if f.start - 2 <= ln.t <= f.end + 2:
                eid = ln.num(1)
                f.encounter_id = eid
                f.boss = names.get(eid, f"Boss {eid}")
                if ln.f(0) == "0":
                    f.killed = ln.f(2) == "1"
                break
    return fights


def build(run: Run, log_files: list[Path]) -> RunData:
    clocks = [SegmentClock(s, datetime.fromtimestamp(run.started)) for s in run.segments]
    # rough window first (before the cast-matching correction) to know what to read from the log
    walls = [(c.wall(s.lines[0].t), c.wall(s.lines[-1].t)) for c, s in zip(clocks, run.segments) if s.lines]
    if not walls:
        start = end = datetime.fromtimestamp(run.started)
    else:
        start, end = walls[0][0], walls[-1][1]

    events: list[Event] = []
    used: list[Path] = []
    for p in log_files:
        span = combatlog.log_span(p)
        if not span or span[1] < start - timedelta(seconds=10) or span[0] > end + timedelta(seconds=10):
            continue
        used.append(p)
        events.extend(combatlog.read_events(p, start, end, margin=10))
    events.sort(key=lambda e: e.ts)

    guid = _find_player(events, run.player_name)
    casts: dict[int, list[datetime]] = {}
    for e in events:
        if e.event == "SPELL_CAST_SUCCESS" and e.src == guid and e.spell_id:
            casts.setdefault(e.spell_id, []).append(e.ts)
    sync = [refine(c, s, casts, AUTO_REPEAT) for c, s in zip(clocks, run.segments)]

    walls = [(c.wall(s.lines[0].t), c.wall(s.lines[-1].t)) for c, s in zip(clocks, run.segments) if s.lines]
    if walls:
        start, end = walls[0][0], walls[-1][1]
    rd = RunData(run, start, end, [], [], guid, sync, log_files=used)
    lines: list[TLine] = []
    spans: list[tuple[float, float]] = []
    for i, (c, s) in enumerate(zip(clocks, run.segments)):
        if not s.lines:
            spans.append((rd.rel(c.wall(0)), rd.rel(c.wall(0))))
            continue
        spans.append((rd.rel(c.wall(s.lines[0].t)), rd.rel(c.wall(s.lines[-1].t))))
        for ln in s.lines:
            lines.append(TLine(rd.rel(c.wall(ln.t)), ln.code, ln.fields, i))
    lines.sort(key=lambda x: x.t)
    rd.lines = lines
    rd.segment_spans = spans
    lo, hi = start - timedelta(seconds=2), end + timedelta(seconds=2)
    rd.events = [e for e in events if lo <= e.ts <= hi]
    rd.fights = _fights(lines, spans, rd.events, rd)
    return rd
