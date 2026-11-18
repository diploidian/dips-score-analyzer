"""Cooldowns: damage cooldowns that sat ready while you were free to use them.

This is the after-fight view's measurement (live/summary.py) run on a saved run: the run's combat-log
events go through the same Tracker that follows the log live, each fight it finds is summed up with the
same `summarize`, and its cooldown rows are used here. Which ready time is excused (moving, no mana,
target nearly dead, ...) is decided in live/readiness.py. How long each spell's cooldown is comes from
the table the live view learns from your casts (cooldowns.json); spells cast twice in this run add to it.
Lost damage is the free seconds divided by the cooldown (the casts missed) times the spell's average hit.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..live.summary import learn_cooldowns, summarize
from ..live.tracker import Tracker
from ..model.run import RunData


@dataclass
class CooldownRow:
    name: str
    free: float      # seconds it sat ready with no excuse
    missed: float    # casts that was worth
    lost: float      # damage that cost


@dataclass
class CooldownMetrics:
    lost: float = 0.0                    # damage lost to unused cooldowns
    damage: int = 0                      # your damage in the same fights
    rows: list[CooldownRow] = field(default_factory=list)   # worst first

    @property
    def lost_share(self) -> float:
        return self.lost / (self.damage + self.lost) if self.damage + self.lost else 0.0


def _sum(parts: list[dict]) -> CooldownMetrics:
    """the summaries of several fights, as one"""
    rows: dict[str, CooldownRow] = {}
    for s in parts:
        for r in s["cooldowns"]:
            x = rows.setdefault(r["name"], CooldownRow(r["name"], 0.0, 0.0, 0.0))
            x.free += r["free"]
            x.missed += r["free"] / r["cd"]
            x.lost += r["lost"]
    out = sorted(rows.values(), key=lambda r: -r.lost)
    return CooldownMetrics(sum(r.lost for r in out), sum(s["damage"] for s in parts), out)


def measure_cooldowns(rd: RunData, known: dict[int, float]) -> tuple[CooldownMetrics, list[CooldownMetrics]]:
    """(the whole run, each fight in rd.fights). known: the learned cooldown table (left as it was)."""
    me = rd.player_guid
    tr = Tracker()
    tr.me = me
    found = [f for e in rd.events if (f := tr.feed(e))]
    if last := tr.flush():
        found.append(last)
    cds = dict(known)
    for f in found:
        learn_cooldowns(f, me, cds)
    per: list[list[dict]] = [[] for _ in rd.fights]
    for f in found:
        s = summarize(f, me, "", cds, [])
        t = rd.rel(f.start)
        i = next((i for i, w in enumerate(rd.fights) if w.start <= t <= w.end), None)
        if s and i is not None:
            per[i].append(s)
    return _sum([s for p in per for s in p]), [_sum(p) for p in per]
