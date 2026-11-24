"""Upkeep: how much of combat the buffs and DoTs your class is expected to keep up were up (the table
is classes.py). All from the basic combat log.

Your aura intervals: one starts at your SPELL_AURA_APPLIED of the spell (matched by name) and ends at
the matching SPELL_AURA_REMOVED on the same unit, that unit's death (a Feign Death is none), or the end
of the run; a REFRESH or a new stack keeps it up.
    self     the aura is on you: uptime is the share of combat time it was up.
    target   the aura is on an enemy: uptime is the share of combat time at least one enemy carried
             it (the union over enemies). In a dungeon you can't keep a DoT on everything, so "on
             something" is the fair measure.
Only effects you applied at least once this run are judged, so your level, talents and build never
count against you. A class that's unknown, or applied nothing, has nothing to judge.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..model.run import RunData
from ..sources.combatlog import is_enemy
from .classes import UPKEEP
from .metrics import Interval, clip, total, union


@dataclass
class UpkeepRow:
    name: str
    kind: str        # "self" or "target"
    uptime: float    # 0..1 of combat time
    up: float        # seconds up


@dataclass
class UpkeepMetrics:
    rows: list[UpkeepRow] = field(default_factory=list)

    @property
    def mean_uptime(self) -> float:
        return sum(r.uptime for r in self.rows) / len(self.rows) if self.rows else 0.0


# (spell name, kind) -> intervals it was up on you / on any enemy, for effects you applied this run
UpkeepBase = dict[tuple[str, str], list[Interval]]


def upkeep_base(rd: RunData, cls: str | None) -> UpkeepBase:
    want = {n: k for n, k in UPKEEP.get(cls or "", [])}
    out: UpkeepBase = {}
    if not want or not rd.player_guid:
        return out
    me = rd.player_guid
    open_: dict[tuple[str, str], float] = {}   # (spell name, unit) -> since

    def close(key, t):
        k = (key[0], want[key[0]])
        out[k].append((open_.pop(key), t))

    for e in rd.events:
        ev, t = e.event, rd.rel(e.ts)
        if ev == "SPELL_AURA_APPLIED" and e.src == me and (e.spell_name in want):
            k = want[e.spell_name]
            if (k == "self") == (e.dst == me) and (k == "self" or is_enemy(e.dst, e.dst_flags)):
                out.setdefault((e.spell_name, k), [])
                open_.setdefault((e.spell_name, e.dst), t)
        elif ev == "SPELL_AURA_REMOVED" and (e.spell_name, e.dst) in open_:
            close((e.spell_name, e.dst), t)
        elif ev == "UNIT_DIED" and not e.feign:
            for key in [k for k in open_ if k[1] == e.dst]:
                close(key, t)
    for key in list(open_):
        close(key, rd.duration)
    return out


def measure_upkeep(rd: RunData, windows: list[Interval] | None = None, base: UpkeepBase | None = None,
                   cls: str | None = None) -> UpkeepMetrics:
    if windows is None:
        windows = [(f.start, f.end) for f in rd.fights]
    windows = union(windows)
    b = base if base is not None else upkeep_base(rd, cls)
    span = total(windows)
    um = UpkeepMetrics()
    for (name, kind), iv in b.items():
        up = total(clip(iv, windows))
        um.rows.append(UpkeepRow(name, kind, up / span if span else 0.0, up))
    return um
