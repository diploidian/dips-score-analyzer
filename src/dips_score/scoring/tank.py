"""Tank measurements: holding mobs, picking them back up, and staying alive. All from the basic
combat log (no Advanced Combat Logging needed), so they work for any tank in the group.

Holding mobs: of the mobs pulled, how many went for the tank first (model/pulls.py first_target).

Only an enemy's melee swings (a hit, or a miss/dodge/parry) say who it is attacking: a spell can
hit anyone (an AoE on the healer isn't the mob turning to them), so caster mobs that never swing
are simply not judged. A loss is a swing landing on a group member who isn't the tank, when that
enemy's previous swing was on the tank or it is its first swing at all. The pickup is the seconds
until that same enemy's next swing on the tank. None within PICKUP_CAP is a miss - unless the
enemy died, the fight ended, or the tank was dead before the cap, which doesn't count either way
(like a dip someone else covered). Swings on pets and guardians are ignored.
"""
from __future__ import annotations

import statistics
from bisect import bisect_left
from dataclasses import dataclass, field

from ..model.run import RunData
from ..sources.combatlog import is_enemy
from .healer import _is_group
from .metrics import Interval, union

PICKUP_CAP = 6.0
FIRST_LEAD = 20.0     # a mob first seen this long before a fight still belongs to it (pulls.LEAD_IN)
LATE_DEATH = 10.0     # deaths count a little past a fight's end (dying as the fight ends)


@dataclass
class Loss:
    enemy: str
    name: str             # the enemy's
    start: float
    to: str               # who it went to
    to_name: str
    response: float | None = None   # seconds until it was back on the tank
    left_out: bool = False          # died, fight ended or the tank was dead before the cap

    @property
    def missed(self) -> bool:
        return self.response is None and not self.left_out


@dataclass
class TankMetrics:
    losses: list[Loss] = field(default_factory=list)
    held: int = 0          # mobs whose first target was the tank
    mobs: int = 0          # mobs pulled
    deaths: int = 0        # the tank's

    @property
    def judged(self) -> list[Loss]:
        return [x for x in self.losses if not x.left_out]

    @property
    def median_pickup(self) -> float | None:
        r = [x.response if x.response is not None else PICKUP_CAP for x in self.judged]
        return statistics.median(r) if r else None

    @property
    def missed(self) -> int:
        return sum(1 for x in self.losses if x.missed)

    @property
    def missed_share(self) -> float:
        j = self.judged
        return self.missed / len(j) if j else 0.0


@dataclass
class TankBase:
    """Everything measure_tank needs from the whole run, gathered in one pass (then each fight only
    slices its window)."""
    losses: list[tuple[float, str, str, str, str]] = field(default_factory=list)   # t, enemy, name, to, to name
    on_tank: dict[str, list[float]] = field(default_factory=dict)   # enemy -> its swings on the tank
    died: dict[str, float] = field(default_factory=dict)            # enemy -> when it died
    dead: list[Interval] = field(default_factory=list)              # the tank dead
    deaths: list[float] = field(default_factory=list)
    first_hits: list[tuple[float, str]] = field(default_factory=list)   # (time, first target) per mob
    who: str | None = None


def tank_base(rd: RunData, pulls, deaths: list[float], who: str | None = None) -> TankBase:
    """pulls: model.pulls.Pull list; deaths: times of the tank's real deaths (feigns taken out)"""
    from ..model.roster import clean_name
    b = TankBase(deaths=sorted(deaths), who=who or rd.player_guid)
    b.first_hits = sorted((en.first_seen, en.first_target) for pl in pulls for en in pl.enemies if en.first_target)
    me = b.who
    if not me:
        return b
    last: dict[str, str] = {}      # enemy -> who its last attack was on
    acts: list[float] = []         # the tank doing anything (alive again after a death)
    for e in rd.events:
        t = rd.rel(e.ts)
        if e.src == me:
            acts.append(t)
        if e.event == "UNIT_DIED" and is_enemy(e.dst, e.dst_flags):
            b.died.setdefault(e.dst, t)
            continue
        if e.event not in ("SWING_DAMAGE", "SWING_MISSED"):
            continue
        if not is_enemy(e.src, e.src_flags) or not e.dst.startswith("Player-"):
            continue
        if e.dst == me:
            b.on_tank.setdefault(e.src, []).append(t)
        elif _is_group(e.dst_flags):
            if last.get(e.src, me) == me:
                b.losses.append((t, e.src, e.src_name, e.dst, clean_name(e.dst_name)))
        else:
            continue
        last[e.src] = e.dst
    for d in b.deaths:
        i = bisect_left(acts, d + 2)   # dead until they next act (the death line itself names them)
        b.dead.append((d, acts[i] if i < len(acts) else float("inf")))
    return b


def measure_tank(rd: RunData, windows: list[Interval] | None = None, base: TankBase | None = None) -> TankMetrics:
    if windows is None:
        windows = [(f.start, f.end) for f in rd.fights]
    windows = union(windows)
    tm = TankMetrics()
    b = base or tank_base(rd, [], [])
    firsts = [who for t, who in b.first_hits if any(c - FIRST_LEAD <= t <= e for c, e in windows)]
    tm.mobs, tm.held = len(firsts), sum(1 for who in firsts if who == b.who)
    tm.deaths = sum(1 for d in b.deaths if any(c <= d <= e + LATE_DEATH for c, e in windows))
    for t, enemy, name, to, to_name in b.losses:
        end = next((e for c, e in windows if c <= t <= e), None)
        if end is None:
            continue
        x = Loss(enemy, name, t, to, to_name)
        hits = b.on_tank.get(enemy, [])
        i = bisect_left(hits, t)
        if i < len(hits) and hits[i] - t <= PICKUP_CAP:
            x.response = hits[i] - t
        else:
            cap = t + PICKUP_CAP
            x.left_out = (b.died.get(enemy, float("inf")) <= cap or end < cap
                          or any(d <= cap and t <= back for d, back in b.dead))
        tm.losses.append(x)
    return tm
