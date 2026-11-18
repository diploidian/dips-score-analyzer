"""Everyone in the group, scored and ranked from the combat log alone.

The add-on only records *your* presses and movement, so to rank the whole group fairly every
player (you included) is judged on what the combat log shows, by role:

    TANK     Holding mobs 40 (share of mobs whose first hit went to them), Survival 35, Damage 25
    HEALER   Group health, Response, Efficiency (as on your own scorecard) + the hybrid bonus
    DPS      Damage 60 (against an even split of the group's damage), Survival 25, Utility 15
             (interrupts and dispels)

Placing = that score + 2 points per good award (at most +6), - 2 per roast (most deaths, most
overhealing, ...). Highest placing is 1st, and MVP. Utility only counts for classes that can
interrupt or dispel.
"""
from __future__ import annotations

import statistics
from bisect import bisect_left, bisect_right
from dataclasses import dataclass, field

from ..sources.combatlog import is_enemy
from .healer import HealerBase, healer_base, measure_healer
from .metrics import Interval, union
from .score import Category, Scorecard, _card, healer_categories, hybrid_bonus, ramp

AWARD_POINTS, AWARD_CAP = 2.0, 6.0
# who can interrupt or dispel at all (a hunter can't, so Utility doesn't count for one)
CAN_UTILITY = {"WARRIOR", "ROGUE", "MAGE", "SHAMAN", "WARLOCK", "PRIEST", "PALADIN", "DRUID"}
ORDINAL = {1: "1st", 2: "2nd", 3: "3rd"}


def ordinal(n: int) -> str:
    return ORDINAL.get(n, f"{n}th")


@dataclass
class GroupData:
    """per-player event times, sorted, gathered once per run (each window then just slices them)"""
    damage: dict[str, list[tuple[float, int]]] = field(default_factory=dict)
    taken: dict[str, list[tuple[float, int]]] = field(default_factory=dict)
    utility: dict[str, list[float]] = field(default_factory=dict)       # interrupts and dispels
    deaths: dict[str, list[float]] = field(default_factory=dict)
    first_hits: list[tuple[float, str]] = field(default_factory=list)   # (time, player) per enemy
    healer_bases: dict[str, HealerBase] = field(default_factory=dict)


@dataclass
class Placing:
    guid: str
    card: Scorecard
    points: float
    rank: int = 0
    awards: list = field(default_factory=list)          # model.summary.Award
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)

    @property
    def mvp(self) -> bool:
        return self.rank == 1


def group_data(a) -> GroupData:
    rd, roster = a.data, a.roster
    g = GroupData()
    owner = {pet: o for o, pets in a.pets.items() for pet in pets}
    for guid in roster:
        g.damage[guid], g.taken[guid], g.utility[guid], g.deaths[guid] = [], [], [], []
    for e in rd.events:
        ev = e.event
        src = e.src if e.src in roster else owner.get(e.src)
        t = rd.rel(e.ts)
        if src and ev.endswith("_DAMAGE") and not ev.endswith("_LANDED") and is_enemy(e.dst, e.dst_flags):
            g.damage[src].append((t, e.amount))
        elif src == e.src and src and (ev.endswith("_INTERRUPT") or ev.endswith("_DISPEL")):
            g.utility[src].append(t)
        if e.dst in roster and ev.endswith("_DAMAGE") and not ev.endswith("_LANDED"):
            g.taken[e.dst].append((t, e.amount))
    for d in a.deaths:
        g.deaths.setdefault(d.guid, []).append(d.t)
    for pl in a.pulls:
        for en in pl.enemies:
            if en.first_target in roster:
                g.first_hits.append((en.first_seen, en.first_target))
    g.first_hits.sort()
    deaths = [(d.t, d.name) for d in a.deaths]
    for guid, p in roster.items():
        if p.role == "HEALER":
            g.healer_bases[guid] = healer_base(rd, deaths, guid)
    return g


def _sum(series: list[tuple[float, int]], windows: list[Interval]) -> int:
    times = [t for t, _ in series]
    total = 0
    for a, b in windows:
        i, j = bisect_left(times, a), bisect_right(times, b)
        total += sum(v for _, v in series[i:j])
    return total


def _count(times: list[float], windows: list[Interval]) -> int:
    return sum(bisect_right(times, b) - bisect_left(times, a) for a, b in windows)


def player_card(a, guid: str, windows: list[Interval] | None = None) -> Scorecard:
    """A log-only scorecard for any player in the group."""
    rd, g, p = a.data, a.group, a.roster[guid]
    if windows is None:
        windows = [(f.start, f.end) for f in rd.fights]
    windows = union(windows)
    combat = sum(b - c for c, b in windows)
    if combat <= 0 or not rd.has_combat_log:
        return Scorecard(0.0, "-", (p.role or "dps").lower(), note="nothing to score here")
    # deaths count a little past a window's end (dying as the fight ends)
    late = [(c, b + 10) for c, b in windows]
    dmg = {x: _sum(g.damage[x], windows) for x in a.roster}
    even = sum(dmg.values()) / len(dmg) if dmg else 0
    mine = dmg[guid]
    deaths = _count(g.deaths.get(guid, []), late)
    surv_txt = f"{deaths} death{'s' if deaths != 1 else ''}"
    role = p.role or "DPS"
    cats: list[Category] = []

    if role == "HEALER" and guid in g.healer_bases:
        hm = measure_healer(rd, windows, g.healer_bases[guid])
        cats = healer_categories(hm, you=p.is_me)
        bonus, note = hybrid_bonus(hm, cats)
        return _card(cats, "healer", bonus, note)

    if role == "TANK":
        firsts = [(t, who) for t, who in g.first_hits if any(c - 20 <= t <= b for c, b in windows)]
        held = sum(1 for _, who in firsts if who == guid)
        share = held / len(firsts) if firsts else 1.0
        cats.append(Category("Holding mobs", ramp(share, 0.4, 0.9), 40,
                             f"{held} of {len(firsts)} mobs went for them first ({share:.0%})",
                             "Mobs went for other players first: pick them up faster (taunt, or tag every mob)."
                             if share < 0.8 else None))
        cats.append(Category("Survival", max(0.0, 100 - 40 * deaths), 35, surv_txt,
                             "Died: look at the hits before it, and use cooldowns earlier." if deaths else None))
        rel = mine / even if even else 0
        cats.append(Category("Damage", ramp(rel, 0.3, 1.0), 25,
                             f"{mine:,} damage ({rel:.0%} of an even share)", None))
        return _card(cats, "tank")

    rel = mine / even if even else 0
    cats.append(Category("Damage", ramp(rel, 0.5, 1.3), 60, f"{mine:,} damage ({rel:.0%} of an even share, "
                         f"{mine / combat:.0f}/s)", "Damage was low: keep casting through the whole pull." if rel < 0.9 else None))
    taken = _sum(g.taken[guid], windows)
    dps_taken = [_sum(g.taken[x], windows) for x, q in a.roster.items() if (q.role or "DPS") == "DPS"]
    median = statistics.median(dps_taken) if dps_taken else 0
    taken_rel = taken / median if median else 1.0
    surv = max(0.0, 100 - 40 * deaths) * (0.6 + 0.4 * ramp(taken_rel, 2.5, 1.0) / 100)
    cats.append(Category("Survival", surv, 25, f"{surv_txt}; took {taken:,} damage "
                         f"({taken_rel:.1f}x the damage dealers' middle)",
                         "Took more hits than the other damage dealers: step out of cleaves and AoE."
                         if taken_rel > 1.5 or deaths else None))
    util = _count(g.utility[guid], windows)
    per10 = util * 600 / combat
    can = p.cls in CAN_UTILITY if p.cls else True
    cats.append(Category("Utility", ramp(per10, 0, 4), 15 if can else 0,
                         f"{util} interrupts and dispels ({per10:.1f} per 10 min)"
                         + ("" if can else f" - a {p.cls.title()} can't, so it doesn't count"), None))
    return _card(cats, "dps")


def rank_group(a) -> list[Placing]:
    """everyone, best placing first"""
    awards: dict[str, list] = {}
    for aw in (a.summary.awards if a.summary else []):
        awards.setdefault(aw.guid, []).append(aw)
    out = []
    for guid in a.roster:
        card = player_card(a, guid)
        perks = awards.get(guid, [])
        pts = card.total + award_points(perks)
        pl = Placing(guid, card, pts, awards=perks)
        counted = [c for c in card.categories if not c.info_only]
        # what mattered most: a strong score in a heavily weighted category leads
        good = sorted((c for c in counted if c.score >= 75), key=lambda c: c.score * c.weight, reverse=True)
        bad = sorted((c for c in counted if c.score < 60), key=lambda c: (100 - c.score) * c.weight, reverse=True)
        pl.strengths = [f"{c.name}: {c.summary}" for c in good][:2]
        pl.weaknesses = [f"{c.name}: {c.summary}" for c in bad][:2]
        if card.bonus:
            pl.strengths.append(f"Hybrid bonus +{card.bonus:.1f}: {card.bonus_note}")
        out.append(pl)
    stats = a.summary.stats if a.summary else {}
    out.sort(key=lambda pl: (pl.points, (stats[pl.guid].damage + stats[pl.guid].healing) if pl.guid in stats else 0),
             reverse=True)
    for i, pl in enumerate(out, 1):
        pl.rank = i
    return out


def award_points(awards) -> float:
    good = sum(1 for aw in awards if aw.good)
    bad = sum(1 for aw in awards if not aw.good)
    return min(AWARD_CAP, AWARD_POINTS * good) - AWARD_POINTS * bad


def placing_reason(pl: Placing, a) -> str:
    """one line on why they placed where they did"""
    p = a.roster[pl.guid]
    pts = award_points(pl.awards)
    perks = f", {pts:+g} from awards" if pl.awards else ""
    best = pl.strengths[0].split(":")[0].lower() if pl.strengths else None
    worst = pl.weaknesses[0].split(":")[0].lower() if pl.weaknesses else None
    why = []
    if best:
        why.append(f"strongest at {best}")
    if worst:
        why.append(f"held back by {worst}")
    role = (p.role or "DPS").lower() if p.role != "DPS" else "damage dealer"
    return (f"{ordinal(pl.rank)}: {pl.card.total:.0f} as a {role}{perks}"
            + (f" - {', '.join(why)}" if why else ""))
