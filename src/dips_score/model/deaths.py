"""Deaths and wipes.

A death is a UNIT_DIED for a group member. Each comes with a recap: the hits and heals they took in
the RECAP seconds before, and the blow that killed them. This client also logs Feign Death as
UNIT_DIED, with its last field set; without that field those are told apart by the player acting again soon
after without a resurrect.

Someone counts as dead from their death until they next do anything in the log (a resurrect, or
just acting again after running back). A wipe is the moment the whole group is dead at once; its
deaths are the ones since the group was last all alive. A failed boss attempt (ENCOUNTER_END
with success 0) is also a wipe, even if someone survived it (a hunter feigning, say).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .roster import Player, clean_name
from .run import RunData

RECAP = 10.0
FEIGN_WINDOW = 20.0  # a real death can't act again this soon without a resurrect
# things only a living player does (buffs falling off at death name the player too, so not those)
_ACTING = {"SPELL_CAST_SUCCESS", "SPELL_CAST_START", "SWING_DAMAGE", "SWING_MISSED", "SPELL_DAMAGE", "RANGE_DAMAGE"}


@dataclass
class RecapLine:
    t: float               # seconds before the death (negative)
    kind: str              # "hit" or "heal"
    source: str
    spell: str
    amount: int
    hp: float | None       # their health after it, when known


@dataclass
class Death:
    t: float
    guid: str
    name: str
    recap: list[RecapLine] = field(default_factory=list)
    killed_by: str = ""     # "Rending Whirl (Twilight Commander Zarmok)"


@dataclass
class Wipe:
    t: float                # when the last one died (or the boss attempt ended)
    deaths: list[Death]
    boss: str | None = None
    fight: int | None = None


def feigns(ev: list, guids) -> set[int]:
    """Indexes of UNIT_DIED events of guids that weren't deaths: Feign Death is one with Event.feign set. Where the log
    doesn't say, a player who acts again within FEIGN_WINDOW seconds without being resurrected was feigning (someone
    who released and hearthed acts that soon too)."""
    out: set[int] = set()
    for i, e in enumerate(ev):
        if e.event != "UNIT_DIED" or e.dst not in guids:
            continue
        if e.feign is not None:
            out.update([i] if e.feign else [])
            continue
        t0 = e.ts
        for f in ev[i + 1:]:
            dt = (f.ts - t0).total_seconds()
            if dt > FEIGN_WINDOW:
                break
            if f.event == "SPELL_RESURRECT" and f.dst == e.dst:
                break
            if f.src == e.dst and f.event in _ACTING:
                out.add(i)
                break
    return out


def find_deaths(rd: RunData, roster: dict[str, Player]) -> tuple[list[Death], list[Wipe]]:
    deaths: list[Death] = []
    recent: dict[str, list] = {g: [] for g in roster}     # events on each player, last RECAP seconds
    hp: dict[str, float] = {}
    dead: set[str] = set()
    died_at: dict[str, float] = {}
    since_alive: list[Death] = []
    wipes: list[Wipe] = []
    feigned = feigns(rd.events, roster)

    for i, e in enumerate(rd.events):
        if i in feigned:
            continue
        t = rd.rel(e.ts)
        if e.info and e.info.guid in roster and e.info.max_hp:
            hp[e.info.guid] = e.info.hp_pct
        back = None
        if e.event == "SPELL_RESURRECT" and e.dst in dead:
            back = e.dst
        elif e.src in dead and e.event in _ACTING and t - died_at[e.src] > 2:
            back = e.src                                 # acting again: alive (ran back, or got a res)
        if back:
            dead.discard(back)
            if not dead:
                since_alive = []
        if e.dst in roster:
            who = clean_name(e.src_name) if e.src.startswith("Player-") else (e.src_name or "?")
            if e.event.endswith("_DAMAGE") and not e.event.endswith("_LANDED") and e.amount:
                recent[e.dst].append((t, "hit", who, e.spell_name or "Melee", e.amount, hp.get(e.dst)))
            elif e.event.endswith("_HEAL") and e.amount - e.overheal > 0:
                recent[e.dst].append((t, "heal", who, e.spell_name, e.amount - e.overheal, hp.get(e.dst)))
            recent[e.dst] = [r for r in recent[e.dst] if t - r[0] <= RECAP]
        if e.event == "UNIT_DIED" and e.dst in roster and e.dst not in dead:
            p = roster[e.dst]
            d = Death(t, e.dst, p.name)
            for rt, kind, src, spell, amount, h in recent[e.dst]:
                d.recap.append(RecapLine(rt - t, kind, src, spell, amount, h))
            hits = [r for r in recent[e.dst] if r[1] == "hit"]
            if hits:
                last = hits[-1]
                d.killed_by = f"{last[3]} ({last[2]})"
            deaths.append(d)
            dead.add(e.dst)
            died_at[e.dst] = t
            since_alive.append(d)
            if dead >= set(roster):
                wipes.append(Wipe(t, list(since_alive)))
                since_alive = []

    # failed boss attempts
    for i, f in enumerate(rd.fights):
        if f.boss and f.killed is False and not any(f.start - 5 <= w.t <= f.end + 30 for w in wipes):
            ds = [d for d in deaths if f.start <= d.t <= f.end + 30]
            wipes.append(Wipe(f.end, ds))
    for w in wipes:
        for i, f in enumerate(rd.fights):
            if f.start - 5 <= w.t <= f.end + 30:
                w.fight, w.boss = i, f.boss
                break
    wipes.sort(key=lambda w: w.t)
    return deaths, wipes
