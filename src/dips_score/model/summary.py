"""End-of-dungeon summary: everyone's numbers, and a few awards.

Awards go to whoever stands out on one number; each has a one-line reason. A player can get more
than one. Awards that nobody earned (no interrupts in the run, say) are left out.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..sources.combatlog import is_enemy
from .deaths import Death
from .pulls import Pull
from .roster import Player
from .run import RunData


@dataclass
class PlayerStats:
    player: Player
    damage: int = 0
    boss_damage: int = 0
    trash_damage: int = 0
    healing: int = 0             # effective
    overheal: int = 0
    taken: int = 0
    deaths: int = 0
    interrupts: int = 0
    dispels: int = 0
    killing_blows: int = 0
    pulls_started: int = 0
    casts: int = 0
    active_time: float = 0.0     # combat time the run covered (same for everyone)

    @property
    def dps(self) -> float:
        return self.damage / self.active_time if self.active_time else 0.0

    @property
    def hps(self) -> float:
        return self.healing / self.active_time if self.active_time else 0.0

    @property
    def overheal_share(self) -> float:
        n = self.healing + self.overheal
        return self.overheal / n if n else 0.0


@dataclass
class Award:
    title: str
    blurb: str
    guid: str
    stat: str
    good: bool = True       # False: a roast - it costs placing points instead of adding them


@dataclass
class Summary:
    stats: dict[str, PlayerStats] = field(default_factory=dict)
    awards: list[Award] = field(default_factory=list)
    combat_time: float = 0.0
    bosses_killed: int = 0
    bosses: int = 0
    trash_killed: int = 0
    wipes: int = 0


def _fmt(n: float) -> str:
    if n >= 1e6:
        return f"{n / 1e6:.1f}M"
    if n >= 1e4:
        return f"{n / 1e3:.0f}K"
    if n >= 1e3:
        return f"{n / 1e3:.1f}K"
    return f"{n:.0f}"


def summarize(rd: RunData, roster: dict[str, Player], pulls: list[Pull], deaths: list[Death],
              pets: dict[str, set[str]], wipes: int = 0) -> Summary:
    s = Summary(combat_time=sum(f.duration for f in rd.fights), wipes=wipes)
    s.stats = {g: PlayerStats(p, active_time=s.combat_time) for g, p in roster.items()}
    owner = {pet: g for g, ps in pets.items() for pet in ps}
    boss_windows = [(f.start - 2, f.end + 2) for f in rd.fights if f.boss]

    def who(guid: str) -> str | None:
        return guid if guid in s.stats else owner.get(guid)

    for e in rd.events:
        g = who(e.src)
        ev = e.event
        if g:
            st = s.stats[g]
            if ev.endswith("_DAMAGE") and not ev.endswith("_LANDED") and is_enemy(e.dst, e.dst_flags):
                st.damage += e.amount
                t = rd.rel(e.ts)
                if any(a <= t <= b for a, b in boss_windows):
                    st.boss_damage += e.amount
                else:
                    st.trash_damage += e.amount
            elif ev.endswith("_HEAL"):
                st.healing += max(0, e.amount - e.overheal)
                st.overheal += e.overheal
            elif ev.endswith("_INTERRUPT"):
                st.interrupts += 1
            elif ev.endswith("_DISPEL"):
                st.dispels += 1
            elif ev == "PARTY_KILL":
                st.killing_blows += 1
            elif ev == "SPELL_CAST_SUCCESS" and g == e.src:
                st.casts += 1
        if e.dst in s.stats and ev.endswith("_DAMAGE") and not ev.endswith("_LANDED"):
            s.stats[e.dst].taken += e.amount
    for d in deaths:
        if d.guid in s.stats:
            s.stats[d.guid].deaths += 1
    for pl in pulls:
        for pk in pl.packs:
            if pk.puller in s.stats:
                s.stats[pk.puller].pulls_started += 1
            s.trash_killed += sum(1 for en in pk.enemies if en.died is not None and not pl.fight.boss)
    s.bosses = sum(1 for f in rd.fights if f.boss)
    s.bosses_killed = sum(1 for f in rd.fights if f.boss and f.killed)
    s.awards = _awards(s)
    return s


def _best(stats: list[PlayerStats], key, min_value: float = 1, low: bool = False):
    vals = [(key(st), st) for st in stats]
    vals = [v for v in vals if (v[0] >= min_value if not low else True)]
    if not vals:
        return None
    return (min if low else max)(vals, key=lambda v: v[0])


def _awards(s: Summary) -> list[Award]:
    """good awards (perks) and a few roasts (good=False). Awards a role gets anyway (the tank taking the
    most hits, the healer doing the most healing) only go to someone outside that role."""
    stats = list(s.stats.values())
    out: list[Award] = []

    def give(title, blurb, found, stat, good=True):
        if found:
            out.append(Award(title, blurb, found[1].player.guid, stat(found[0], found[1]), good))

    def role(*roles):
        return [st for st in stats if (st.player.role or "DPS") in roles]

    give("Wrecking Ball", "Most damage done.", _best(stats, lambda st: st.damage),
         lambda v, st: f"{_fmt(v)} damage ({st.dps:.0f}/s)")
    give("Boss Bane", "Most damage to bosses.", _best(stats, lambda st: st.boss_damage),
         lambda v, st: f"{_fmt(v)} on bosses")
    give("Janitor", "Most damage to trash.", _best(stats, lambda st: st.trash_damage),
         lambda v, st: f"{_fmt(v)} on trash")
    give("Patch Kit", "Most healing by someone who isn't the healer.",
         _best(role("TANK", "DPS"), lambda st: st.healing, min_value=500), lambda v, st: f"{_fmt(v)} healing")
    give("Punching Bag", "Took the most hits without being the tank.",
         _best(role("HEALER", "DPS"), lambda st: st.taken), lambda v, st: f"{_fmt(v)} damage taken", good=False)
    give("Shush", "Most interrupts.", _best(stats, lambda st: st.interrupts),
         lambda v, st: f"{v} interrupts")
    give("Scrubber", "Most dispels.", _best(stats, lambda st: st.dispels),
         lambda v, st: f"{v} dispels")
    give("Last Word", "Most killing blows.", _best(stats, lambda st: st.killing_blows),
         lambda v, st: f"{v} killing blows")
    give("Untouchable", "Damage dealer who took the fewest hits.",
         _best([st for st in role("DPS") if st.damage > 0], lambda st: st.taken, low=True),
         lambda v, st: f"only {_fmt(v)} damage taken")
    give("Spare Hands", "Healer who still found time to hurt things.", _best(role("HEALER"), lambda st: st.damage),
         lambda v, st: f"{_fmt(v)} damage on top of {_fmt(st.healing)} healing")
    give("Carpet Sampler", "Spent the most time lying down.", _best(stats, lambda st: st.deaths),
         lambda v, st: f"{v} death{'s' if v != 1 else ''}", good=False)
    give("Eager Beaver", "Started the most pulls without being the tank.",
         _best(role("HEALER", "DPS"), lambda st: st.pulls_started, min_value=2),
         lambda v, st: f"{v} pulls started", good=False)
    give("Overflowing Cup", "Most overhealing.", _best(stats, lambda st: st.overheal, min_value=1000),
         lambda v, st: f"{st.overheal_share:.0%} of their healing", good=False)
    return out
