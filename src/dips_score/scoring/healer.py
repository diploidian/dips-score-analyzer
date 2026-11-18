"""Healer measurements: how your group fared and how you responded. All from the combat log
(needs Advanced Combat Logging for health).

Your heals are split by what you did:
    cast heals   spells you hard-cast that heal (Heal, Flash Heal, Greater Heal, Prayer of Healing)
    HoTs         your periodic heals (Renew)
    shields      buffs you put on the group with "Shield" in the name (Power Word: Shield)
    passive      everything else that heals (Vampiric Embrace, Devouring Plague, Touch of the Grave,
                 potions) - not judged: you don't choose when those land
Overhealing is judged on cast heals and HoTs only.

A dip is a party member dropping below DIP_HP while taking damage (so trading health for mana,
like Dark Sacrifice, isn't a dip). Your response is when you *started* the first cast heal, HoT
or shield of yours that reached them (a heal already being cast when they dipped counts as 0 s). No response within RESPONSE_CAP seconds is a miss - unless they were back
above DIP_HP by then without you (someone else covered it), which doesn't count either way.
"""
from __future__ import annotations

import statistics
from bisect import bisect_left
from dataclasses import dataclass, field

from ..model.run import RunData
from ..sources.combatlog import is_enemy
from .metrics import Interval, clip, inside, total, union

DIP_HP = 0.60
DANGER_HP = 0.35
RESPONSE_CAP = 6.0
DAMAGE_BEFORE = 3.0   # a dip needs a hit on them this soon before it
HOLD = 5.0
SAFE_HP = 0.80        # everyone above this: nobody needs you, so damage then is "spare time" damage            # a health reading stands for at most this long


@dataclass
class Dip:
    guid: str
    name: str
    start: float
    hp: float                       # health when it crossed the line
    response: float | None = None   # seconds until your heal reached them
    spell: str = ""
    covered: bool = False           # back up without you

    @property
    def missed(self) -> bool:
        return self.response is None and not self.covered


@dataclass
class HealerMetrics:
    party: dict[str, str] = field(default_factory=dict)          # guid -> short name
    hp: dict[str, list[tuple[float, float]]] = field(default_factory=dict)
    dips: list[Dip] = field(default_factory=list)
    deaths: list[tuple[float, str]] = field(default_factory=list)
    danger_time: float = 0.0       # someone under DANGER_HP
    combat_time: float = 0.0
    cast_heal: int = 0             # effective healing from cast heals and HoTs
    cast_overheal: int = 0
    passive_heal: int = 0
    lowest_mana: float | None = None
    oom_refusals: int = 0
    heal_spells: set[str] = field(default_factory=set)
    # for the hybrid bonus
    my_damage: int = 0             # your damage to enemies
    free_damage: int = 0           # of that, done while everyone was above SAFE_HP (your spare time)
    group_damage: int = 0          # the whole group's damage to enemies
    group_size: int = 0
    has_advanced: bool = True      # health readings exist (Advanced Combat Logging)

    @property
    def even_share(self) -> float:
        """the damage each player would have done if the group's damage were split evenly"""
        return self.group_damage / self.group_size if self.group_size else 0.0

    @property
    def judged(self) -> list[Dip]:
        return [d for d in self.dips if not d.covered]

    @property
    def median_response(self) -> float | None:
        r = [d.response if d.response is not None else RESPONSE_CAP for d in self.judged]
        return statistics.median(r) if r else None

    @property
    def missed(self) -> int:
        return sum(1 for d in self.dips if d.missed)

    @property
    def missed_share(self) -> float:
        j = self.judged
        return self.missed / len(j) if j else 0.0

    @property
    def overheal_share(self) -> float:
        n = self.cast_heal + self.cast_overheal
        return self.cast_overheal / n if n else 0.0

    @property
    def danger_share(self) -> float:
        return self.danger_time / self.combat_time if self.combat_time else 0.0


def _is_group(flags: int) -> bool:
    return flags & 0x7 in (0x1, 0x2, 0x4)   # affiliation: mine, party, raid


@dataclass
class HealerBase:
    """Everything measure_healer needs from the whole run, gathered in one pass (then each fight
    only slices its window)."""
    party: dict[str, str] = field(default_factory=dict)
    heal_spells: set[str] = field(default_factory=set)
    hp: dict[str, list[tuple[float, float]]] = field(default_factory=dict)
    hits: dict[str, list[float]] = field(default_factory=dict)
    helps: dict[str, list[tuple[float, float, str]]] = field(default_factory=dict)  # landed, began, spell
    heals: list[tuple[float, int, int, bool]] = field(default_factory=list)          # t, effective, overheal, active
    mana: list[tuple[float, float]] = field(default_factory=list)
    oom: list[float] = field(default_factory=list)
    deaths: list[tuple[float, str]] = field(default_factory=list)
    damage: list[tuple[float, str, int]] = field(default_factory=list)   # t, group member, amount to an enemy
    who: str | None = None         # the healer measured


def healer_base(rd: RunData, deaths: list[tuple[float, str]] | None = None, who: str | None = None) -> HealerBase:
    """deaths: (time, name) of real deaths (feigns taken out); default: every UNIT_DIED"""
    from ..model.roster import clean_name
    b = HealerBase()
    me = who or rd.player_guid      # whose healing: you, unless asked about someone else
    b.who = me
    if not me:
        return b
    # who's in the group, and what your healing spells are
    cast_started, periodic, shields, healed = set(), set(), set(), set()
    for e in rd.events:
        for g, n, fl in ((e.src, e.src_name, e.src_flags), (e.dst, e.dst_name, e.dst_flags)):
            if g.startswith("Player-") and g not in b.party and _is_group(fl):
                b.party[g] = clean_name(n)
        if e.src == me and e.spell_id:
            if e.event == "SPELL_CAST_START":
                cast_started.add(e.spell_id)
            elif e.event == "SPELL_PERIODIC_HEAL":
                periodic.add(e.spell_id)
            elif e.event == "SPELL_HEAL":
                healed.add(e.spell_id)
            elif e.event == "SPELL_AURA_APPLIED" and "Shield" in e.spell_name and e.dst.startswith("Player-"):
                shields.add(e.spell_id)
    cast_heals = cast_started & healed
    active = cast_heals | periodic | shields
    b.heal_spells = {e.spell_name for e in rd.events if e.spell_id in active and e.src == me}

    # when each of your casts began: a heal that lands at t began at the last start of it before t
    starts: dict[int, list[float]] = {}
    for e in rd.events:
        if e.src == me and e.event == "SPELL_CAST_START" and e.spell_id in cast_heals:
            starts.setdefault(e.spell_id, []).append(rd.rel(e.ts))

    def began(sid: int, t: float) -> float:
        s = starts.get(sid, [])
        i = bisect_left(s, t + 0.01)
        return s[i - 1] if i and t - s[i - 1] <= 5.0 else t

    for e in rd.events:
        t = rd.rel(e.ts)
        if e.info and e.info.guid in b.party and e.info.max_hp:
            b.hp.setdefault(e.info.guid, []).append((t, e.info.hp_pct))
            if e.info.guid == me and e.info.power_type == 0 and e.info.max_power:
                b.mana.append((t, e.info.power / e.info.max_power))
        if e.dst in b.party and e.event.endswith("_DAMAGE") and e.amount > 0:
            b.hits.setdefault(e.dst, []).append(t)
        if e.src == me:
            if e.spell_id in active and e.dst in b.party and                     e.event in ("SPELL_CAST_SUCCESS", "SPELL_HEAL", "SPELL_AURA_APPLIED"):
                b.helps.setdefault(e.dst, []).append((t, began(e.spell_id, t), e.spell_name))
            if e.event.endswith("_HEAL"):
                b.heals.append((t, max(0, e.amount - e.overheal), e.overheal, e.spell_id in active))
            if e.event == "SPELL_CAST_FAILED" and e.reason == "Not enough mana":
                b.oom.append(t)
        if e.src in b.party and e.event.endswith("_DAMAGE") and not e.event.endswith("_LANDED")                 and e.amount and is_enemy(e.dst, e.dst_flags):
            b.damage.append((t, e.src, e.amount))
        if deaths is None and e.event == "UNIT_DIED" and e.dst in b.party:
            b.deaths.append((t, b.party[e.dst]))
    if deaths is not None:
        b.deaths = list(deaths)
    for v in b.helps.values():
        v.sort()
    return b


def measure_healer(rd: RunData, windows: list[Interval] | None = None, base: HealerBase | None = None) -> HealerMetrics:
    if windows is None:
        windows = [(f.start, f.end) for f in rd.fights]
    windows = union(windows)
    hm = HealerMetrics(combat_time=total(windows), has_advanced=rd.has_advanced)
    b = base or healer_base(rd)
    if not b.who:
        return hm
    hm.party, hm.hp, hm.heal_spells = b.party, b.hp, b.heal_spells
    hits, helps = b.hits, b.helps
    for t, eff, over, active in b.heals:
        if inside(t, windows):
            if active:
                hm.cast_heal += eff
                hm.cast_overheal += over
            else:
                hm.passive_heal += eff
    lows = [pct for t, pct in b.mana if inside(t, windows)]
    hm.lowest_mana = min(lows) if lows else None
    hm.oom_refusals = sum(1 for t in b.oom if inside(t, windows))
    hm.deaths = [(t, n) for t, n in b.deaths if any(a - 5 <= t <= c + 15 for a, c in windows)]

    # damage: yours, yours in spare time (nobody under SAFE_HP), and the group's
    hurt: list[Interval] = []
    for series in b.hp.values():
        for (t1, p1), (t2, _) in zip(series, series[1:]):
            if p1 < SAFE_HP:
                hurt.append((t1, t1 + min(t2 - t1, HOLD)))
    hurt = union(hurt)
    hm.group_size = len(b.party)
    for t, who, amount in b.damage:
        if not inside(t, windows):
            continue
        hm.group_damage += amount
        if who == b.who:
            hm.my_damage += amount
            if not inside(t, hurt):
                hm.free_damage += amount

    # dips and how fast you answered them
    for guid, series in hm.hp.items():
        h = hits.get(guid, [])
        prev = 1.0
        for t, pct in series:
            crossed = prev >= DIP_HP > pct
            prev = pct
            if not crossed or not inside(t, windows):
                continue
            i = bisect_left(h, t - DAMAGE_BEFORE)
            if not (i < len(h) and h[i] <= t + 0.05):
                continue  # no damage before it: not a dip (health traded away, a bad reading)
            d = Dip(guid, hm.party[guid], t, pct)
            for landed, start, name in helps.get(guid, []):
                if landed < t - 0.05:
                    continue
                if start - t <= RESPONSE_CAP:
                    d.response, d.spell = max(0.0, start - t), name
                break
            if d.response is None:
                later = [p for tt, p in series if t < tt <= t + RESPONSE_CAP]
                died = any(n == d.name and t <= dt <= t + RESPONSE_CAP for dt, n in hm.deaths)
                d.covered = bool(later) and later[-1] >= DIP_HP and not died
            hm.dips.append(d)
    hm.dips.sort(key=lambda d: d.start)

    # time with someone in danger
    danger: list[Interval] = []
    for series in hm.hp.values():
        for (t1, p1), (t2, _) in zip(series, series[1:]):
            if p1 < DANGER_HP:
                danger.append((t1, t1 + min(t2 - t1, HOLD)))
    hm.danger_time = total(clip(danger, windows))
    return hm
