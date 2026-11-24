"""Cooldowns: damage cooldowns that sat ready while you were free to use them.

This is the after-fight view's measurement (live/summary.py) run on a saved run: the run's combat-log
events go through the same Tracker that follows the log live, each fight it finds is summed up with the
same `summarize`, and its cooldown rows are used here. Which ready time is excused (moving, no mana,
target nearly dead, ...) is decided in live/readiness.py. How long each spell's cooldown is comes from
your character's spell book, which the live view learns from your casts (spells.json); this run's casts
add to a copy of it. Lost damage is the free seconds divided by the cooldown (the casts missed) times the
spell's average hit. A cooldown of a minute or more held outside a boss fight isn't counted. A spell that
only works on some targets or after an avoided attack (usable.py) is excused while it couldn't be used, the
enemy types coming from the add-on (types); its chances are summed over the fights that know them.
"""
from __future__ import annotations

import copy
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
    chances: int | None = None   # its chances (usable.py), None for a spell any target allows or unknown


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
            if r.get("held"):
                continue
            x = rows.setdefault(r["name"], CooldownRow(r["name"], 0.0, 0.0, 0.0))
            x.free += r["free"]
            x.missed += r["free"] / r["cd"]
            x.lost += r["lost"]
            if r.get("chances") is not None:
                x.chances = (x.chances or 0) + r["chances"]
    out = sorted(rows.values(), key=lambda r: -r.lost)
    return CooldownMetrics(sum(r.lost for r in out), sum(s["damage"] for s in parts), out)


def measure_cooldowns(rd: RunData, book: dict[str, dict],
                      types: dict | None = None) -> tuple[CooldownMetrics, list[CooldownMetrics]]:
    """(the whole run, each fight in rd.fights). book: your spell book (left as it was); types: enemy name ->
    creature type"""
    me = rd.player_guid
    tr = Tracker()
    tr.me = me
    found = [f for e in rd.events if (f := tr.feed(e))]
    if last := tr.flush():
        found.append(last)
    cds = copy.deepcopy(book)
    for f in found:
        learn_cooldowns(f, me, cds)
    per: list[list[dict]] = [[] for _ in rd.fights]
    for f in found:
        s = summarize(f, me, "", cds, [], types)
        t = rd.rel(f.start)
        i = next((i for i, w in enumerate(rd.fights) if w.start <= t <= w.end), None)
        if s and i is not None:
            per[i].append(s)
    return _sum([s for p in per for s in p]), [_sum(p) for p in per]
