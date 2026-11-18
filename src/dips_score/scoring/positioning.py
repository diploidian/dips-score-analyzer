"""Positioning (info only by default): where you stood. Needs Advanced Combat Logging.

A unit's position is only known at moments it is the unit described by an event's advanced block
(its source on some lines, its destination on others). So "where was U at time t" is the nearest
reading of U within NEAR seconds, else unknown. Each figure below says how many cases it could
judge out of how many there were; the unjudged ones are left out, never guessed.

    behind     your melee swings (SWING_DAMAGE / SWING_MISSED on an enemy) where you were behind it:
               the angle between its facing and the direction from it to you is over 90 degrees.
    range      your casts refused as "Out of range": the log has no target on a refusal, so it is the
               distance to the nearest enemy with a known position. Median over the judged ones.
    tank       hits an enemy landed on you: the distance to the group's tank (skipped when you are
               the tank, or there is none), as a median and the share more than FAR yards away.
Distances are plain x/y distance (log units are yards); units on different maps are skipped.

Facing convention ASSUMED (WoW's): radians, 0 = north = +x, growing counter-clockwise, so the
direction is (cos f, sin f) in (x, y). UNCONFIRMED for this client's log: if "behind" comes out
inverted on real data, change `faces` below, it is the only place that depends on it.
"""
from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass, field
from math import cos, hypot, sin
from statistics import median

from ..model.run import RunData
from ..sources.combatlog import is_enemy
from .metrics import Interval, inside, union

NEAR = 1.0      # a reading counts for this many seconds either side
FAR = 15.0      # yards from the tank that count as too far

Reading = tuple[float, float, float, float, int]   # t, x, y, facing, map id


@dataclass
class PositionMetrics:
    swings: int = 0                 # your melee swings on enemies
    behind_judged: int = 0
    behind: int = 0
    refused: int = 0                # casts refused for range
    range_dists: list[float] = field(default_factory=list)   # yards, the judged ones
    hits: int = 0                   # enemy hits on you (0 when there is no other tank)
    tank_dists: list[float] = field(default_factory=list)

    @property
    def behind_share(self) -> float:
        return self.behind / self.behind_judged if self.behind_judged else 0.0

    @property
    def median_range(self) -> float:
        return median(self.range_dists) if self.range_dists else 0.0

    @property
    def median_tank(self) -> float:
        return median(self.tank_dists) if self.tank_dists else 0.0

    @property
    def far_share(self) -> float:
        return sum(d > FAR for d in self.tank_dists) / len(self.tank_dists) if self.tank_dists else 0.0


@dataclass
class PositionBase:
    readings: dict[str, list[Reading]] = field(default_factory=dict)   # you, the tank, enemies; by time
    swings: list[tuple[float, str]] = field(default_factory=list)      # (time, enemy guid)
    refusals: list[float] = field(default_factory=list)
    hits: list[float] = field(default_factory=list)
    tank: str | None = None


def faces(ex: float, ey: float, facing: float, x: float, y: float) -> bool:
    """is (x, y) in front of the unit at (ex, ey) looking at `facing` (the convention in the docstring)"""
    return (x - ex) * cos(facing) + (y - ey) * sin(facing) >= 0


def position_base(rd: RunData, tank: str | None = None) -> PositionBase:
    me = rd.player_guid
    b = PositionBase(tank=tank)
    for e in rd.events:
        t = rd.rel(e.ts)
        if i := e.info:
            flags = e.src_flags if i.guid == e.src else e.dst_flags
            if i.guid in (me, tank) or is_enemy(i.guid, flags):
                b.readings.setdefault(i.guid, []).append((t, i.x, i.y, i.facing, i.map_id))
        ev = e.event
        if ev in ("SWING_DAMAGE", "SWING_MISSED") and e.src == me and is_enemy(e.dst, e.dst_flags):
            b.swings.append((t, e.dst))
        elif ev == "SPELL_CAST_FAILED" and e.src == me and e.reason == "Out of range":
            b.refusals.append(t)
        elif ev.endswith("_DAMAGE") and e.dst == me and is_enemy(e.src, e.src_flags):
            b.hits.append(t)
    return b


def _at(b: PositionBase, guid: str | None, t: float) -> Reading | None:
    rs = b.readings.get(guid or "")
    if not rs:
        return None
    i = bisect_left(rs, t, key=lambda r: r[0])
    near = [r for r in rs[max(0, i - 1):i + 1] if abs(r[0] - t) <= NEAR]
    return min(near, key=lambda r: abs(r[0] - t)) if near else None


def _dist(a: Reading | None, c: Reading | None) -> float | None:
    if a is None or c is None or a[4] != c[4]:
        return None
    return hypot(a[1] - c[1], a[2] - c[2])


def measure_positioning(rd: RunData, windows: list[Interval] | None = None,
                        base: PositionBase | None = None, tank: str | None = None) -> PositionMetrics:
    if windows is None:
        windows = [(f.start, f.end) for f in rd.fights]
    windows = union(windows)
    b = base if base is not None else position_base(rd, tank)
    me = rd.player_guid
    pm = PositionMetrics()
    for t, mob in b.swings:
        if not inside(t, windows):
            continue
        pm.swings += 1
        mine, theirs = _at(b, me, t), _at(b, mob, t)
        if mine and theirs and mine[4] == theirs[4]:
            pm.behind_judged += 1
            pm.behind += not faces(theirs[1], theirs[2], theirs[3], mine[1], mine[2])
    for t in b.refusals:
        if not inside(t, windows):
            continue
        pm.refused += 1
        mine = _at(b, me, t)
        ds = [d for g in b.readings if g not in (me, b.tank)
              if (d := _dist(mine, _at(b, g, t))) is not None]
        if ds:
            pm.range_dists.append(min(ds))
    if b.tank and b.tank != me:
        for t in b.hits:
            if inside(t, windows):
                pm.hits += 1
                if (d := _dist(_at(b, me, t), _at(b, b.tank, t))) is not None:
                    pm.tank_dists.append(d)
    return pm
