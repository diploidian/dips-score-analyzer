"""Radar chart values: what each player brought to the group, on six axes everyone shares (so players
of different roles can be laid over each other).

    Damage      damage to enemies, inside the fights (as the group's cards are scored)
    Healing     healing that landed
    Tanking     damage taken, and mobs that went for them first (half each)
    Utility     interrupts and dispels
    Kills       killing blows
    Survival    staying alive: 100 with no deaths, 40 less for each

Every axis but Survival is scaled to the group: the player with the most gets 100, the rest a share
of that. So the shape shows where someone's contribution went, and how it compares.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .group import fight_damage

AXES = ["Damage", "Healing", "Tanking", "Utility", "Kills", "Survival"]


@dataclass
class Radar:
    guid: str
    values: list[float] = field(default_factory=list)     # 0-100, in AXES order
    details: list[str] = field(default_factory=list)      # what's behind each value


def _fmt(n: float) -> str:
    return f"{n / 1e3:.1f}K" if n >= 1e3 else f"{n:.0f}"


def radars(a) -> dict[str, Radar]:
    if not a.summary:
        return {}
    stats = a.summary.stats
    firsts: dict[str, int] = {}
    for _, who in (a.group.first_hits if a.group else []):
        firsts[who] = firsts.get(who, 0) + 1
    n_firsts = sum(firsts.values())

    # damage inside the fights, as the cards are scored (group.player_card), so a card's line and its map agree
    damage = (fight_damage(a.group, stats, [(f.start, f.end) for f in a.data.fights]) if a.group else
              {g: st.damage for g, st in stats.items()})

    def top(f) -> float:
        return max((f(st) for st in stats.values()), default=0) or 1

    best = {
        "damage": max(damage.values(), default=0) or 1, "healing": top(lambda st: st.healing),
        "taken": top(lambda st: st.taken), "utility": top(lambda st: st.interrupts + st.dispels),
        "kills": top(lambda st: st.killing_blows), "firsts": max(firsts.values(), default=0) or 1,
    }
    out: dict[str, Radar] = {}
    for g, st in stats.items():
        held = firsts.get(g, 0)
        tank = 50 * st.taken / best["taken"] + 50 * held / best["firsts"]
        util = st.interrupts + st.dispels
        surv = max(0.0, 100 - 40 * st.deaths)
        out[g] = Radar(g, [
            100 * damage[g] / best["damage"],
            100 * st.healing / best["healing"],
            tank,
            100 * util / best["utility"],
            100 * st.killing_blows / best["kills"],
            surv,
        ], [
            f"{_fmt(damage[g])} damage",
            f"{_fmt(st.healing)} healing",
            f"{_fmt(st.taken)} taken, {held} of {n_firsts} mobs went for them first",
            f"{st.interrupts} interrupts, {st.dispels} dispels",
            f"{st.killing_blows} killing blows",
            f"{st.deaths} death{'s' if st.deaths != 1 else ''}",
        ])
    return out


def average(rs: dict[str, Radar]) -> list[float]:
    """the group's average on each axis"""
    if not rs:
        return [0.0] * len(AXES)
    return [sum(r.values[i] for r in rs.values()) / len(rs) for i in range(len(AXES))]
