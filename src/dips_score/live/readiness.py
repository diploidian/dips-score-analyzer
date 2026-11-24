"""When a cooldown was ready and you didn't cast it: was there a good reason?

For each of your damage spells with a cooldown, the time it was ready is worked out from your casts (and
your last cast of it before the fight). Each moment of that ready time is either excused or counted:

    just came up      the reaction time after it came off cooldown (REACT), stretched to the end of a cast
                      you were already in the middle of
    moving            you were moving (spells with a cast time only: instants can be cast on the move)
    no mana           your power was below what the spell costs
    stunned/silenced  the game refused a cast because you were stunned, silenced, feared...
    target nearly dead every enemy still alive was under TARGET_LOW health (no point starting a big cast)
    fight ending      the last ENDING seconds of the fight
    healing           you heal, and someone in the group was under HURT health (heals come first)
    nothing to hit    a lull of LULL seconds or more with no fighting at all (an enemy ran off, or you
                      were between packs in one combat)
    no valid target,  the spell could not be used: no enemy of its creature types, no target under 20%,
    no enemy under 20%, no dodge, block or parry to answer (scoring/usable.py); the REACT seconds after a
    nothing to answer chance opens count as just came up

What's left is time the spell sat ready while you were free to use it: casting something else instead counts
here, because that's the choice that cost damage. Lost damage is that time divided by the cooldown (the casts
it was worth), times the spell's average damage.

Movement comes from your position in the combat log (Advanced Combat Logging): two readings close together
in time and far enough apart in space mean you were moving between them.
"""
from __future__ import annotations

import math
from bisect import bisect_right
from collections import Counter
from dataclasses import dataclass, field

REACT = 1.0
ENDING = 2.0
TARGET_LOW = 0.10
HURT = 0.50
STEP = 0.1
LULL = 3.0
MOVE_SPEED = 2.5        # yards a second: faster than this between two readings is moving
MOVE_GAP = 3.0          # readings further apart than this tell nothing about moving


@dataclass
class Context:
    dur: float
    moving: list[tuple[float, float]] = field(default_factory=list)
    power: list[tuple[float, float]] = field(default_factory=list)       # (t, power): your mana/rage/energy
    start_power: float | None = None
    cc: list[tuple[float, float]] = field(default_factory=list)
    bars: list[tuple[float, float]] = field(default_factory=list)        # your cast bars and GCDs
    foes: list[tuple[float, float | None, list[tuple[float, float]]]] = field(default_factory=list)
    hurt: list[tuple[float, float]] = field(default_factory=list)        # someone in the group low
    lulls: list[tuple[float, float]] = field(default_factory=list)       # no fighting at all
    you_heal: bool = False


def moving_intervals(pos: list[tuple[float, float, float]]) -> list[tuple[float, float]]:
    out = []
    for (t1, x1, y1), (t2, x2, y2) in zip(pos, pos[1:]):
        dt = t2 - t1
        if 0 < dt <= MOVE_GAP and math.hypot(x2 - x1, y2 - y1) / dt >= MOVE_SPEED:
            if out and t1 <= out[-1][1] + 0.05:
                out[-1] = (out[-1][0], t2)
            else:
                out.append((t1, t2))
    return out


def lulls(fighting: list[float], dur: float) -> list[tuple[float, float]]:
    """stretches of LULL seconds or more between moments of fighting"""
    out, last = [], 0.0
    for t in sorted(fighting) + [dur]:
        if t - last >= LULL:
            out.append((last, t))
        last = max(last, t)
    return out


def ready_windows(casts: list[tuple[float, float]], cd: float, ready0: float, dur: float) -> list[tuple[float, float]]:
    """casts: (started, finished) of the spell, in order. When it sat ready before each cast, and after the last."""
    out, ready = [], ready0
    for began, done in casts:
        if began > ready:
            out.append((ready, began))
        ready = done + cd
    if ready < dur:
        out.append((ready, dur))
    return out


def _inside(t: float, spans) -> bool:
    return any(a <= t <= b for a, b in spans)


def _value_at(series: list[tuple[float, float]], t: float, default: float | None) -> float | None:
    i = bisect_right([x for x, _ in series], t) - 1
    return series[i][1] if i >= 0 else default


def _target_low(ctx: Context, t: float) -> bool:
    alive = [hp for first, died, hp in ctx.foes if first <= t and (died is None or died > t)]
    if not alive:
        return True
    for hp in alive:
        v = _value_at(hp, t, 1.0)
        if v is None or v >= TARGET_LOW:
            return False
    return True


def judge(windows: list[tuple[float, float]], ctx: Context, has_cast_time: bool, cost: float,
          usable: list[tuple[float, float]] | None = None, unusable: str = "") -> tuple[float, Counter]:
    """(seconds ready while you were free, seconds excused by reason). usable: when the spell could be used at
    all (None: always), the rest excused as `unusable`"""
    excused: Counter = Counter()
    free = 0.0
    for a, b in windows:
        # the reaction time, stretched to the end of a cast you were in when it came up
        grace = a + REACT
        for s, e in ctx.bars:
            if s <= a < e:
                grace = max(grace, e + REACT * 0.5)
        t = a
        while t < b:
            if t < grace:
                excused["just came up"] += STEP
            elif usable is not None and not _inside(t, usable):
                excused[unusable] += STEP
            elif usable is not None and any(u <= t < u + REACT for u, _ in usable):
                excused["just came up"] += STEP
            elif _inside(t, ctx.lulls):
                excused["nothing to hit"] += STEP
            elif has_cast_time and _inside(t, ctx.moving):
                excused["moving"] += STEP
            elif cost and (_value_at(ctx.power, t, ctx.start_power) or 0) < cost:
                excused["no mana"] += STEP
            elif _inside(t, ctx.cc):
                excused["stunned/silenced"] += STEP
            elif t >= ctx.dur - ENDING:
                excused["fight ending"] += STEP
            elif _target_low(ctx, t):
                excused["target nearly dead"] += STEP
            elif ctx.you_heal and _inside(t, ctx.hurt):
                excused["healing"] += STEP
            else:
                free += STEP
            t += STEP
    return free, excused
