"""One fight, summed up from the combat log: your numbers, what went well, what cost you damage, and
(in a group) your share of it.

Everything is about you (and your pets). Damage you could have done is only counted where there was no good
reason not to (see readiness.py):
    cooldowns sat ready    time a damage cooldown was ready while you were free to use it - not moving
                           (cast-time spells), not out of mana, not stunned, the target not nearly dead,
                           not healing someone who was low. Every damage cooldown in your spell book that
                           you cast in the last RECENT days gets a row, pressed in this fight or not, with
                           the casts that would have fit (possible) and the ones you didn't make (missed).
                           One of HELD seconds or more only counts against you on a boss. A spell's value
                           is its damage per cast, counting damage under a longer name that starts with it
                           and has no casts of its own ("Judgement" owns "Judgement of Command"). A miss
                           is counted only when the spell sat ready 2 s or more with no excuse.
                           A spell that only works on some targets or after a dodge, block or parry
                           (scoring/usable.py) is excused while it couldn't be used; its row says its
                           chances, and possible counts only the casts that fit in those chances.
    melee swings lost      gaps in your auto-attacks longer than 1.6 swings, while you weren't casting; a
                           next-swing ability (Heroic Strike, metrics.NEXT_SWING) fills the swing it replaces
    shots lost             the same for Auto Shot and wand Shoot, less time moving or with no enemy alive;
                           shots clipped by a cast (a hard cast; any cast for a wand) are counted apart;
                           a wand's shots in a priced idle gap aren't lost again
    idle time              gaps of 2.5 s+ with no ability used, while you weren't moving or stunned and had
                           the resource to cast (half counted: not every gap is a mistake). Of that, the
                           part with auto-attack running is "no ability used while swinging" (or shooting),
                           the rest is idle; both cost the ability damage you could have added. Only if you
                           have a filler: a damage spell you cast back to back (twice within SPAM seconds,
                           or a confirmed cooldown under MIN_COOLDOWN). Without one there was nothing to
                           press, and a ready cooldown is already counted by its own row.
Danger is your lowest health under 35%, with the hits that put you there and the defensives (classes.py, any
class: only names in your spell book count) that sat ready and unused: off cooldown at that moment (your death,
if you died). None sat unused when you answered it: cast one on yourself within DEFENSIVE_WINDOW seconds before or
after that moment (your health is lowest just before the one that saves you). Forbearance rules out the paladin's
shields (60 s of it: a missed removal does not keep them out), and one that stops your own attacks or takes you out of the fight (HALTS) counts only when you died.
The verdict is one sentence about the fight: how you died, else (healing) what went well, else "no damage
done", else the biggest finding when it cost VERDICT_SHARE of your damage (or anything, below CLEAN of what
was possible), else how close you came to the most you could have done.

Your spell book (one per character, kept by history.py) is learned from your casts, by spell name since
every rank of a spell has its own id: the 10 shortest gaps of SPAM seconds or more between two casts. A
spell's cooldown is the shortest of those that two others agree with (within AGREE above it), so one quick
cast after a cooldown reset can't set it; a spell ever cast twice within SPAM seconds has none. Procs (a
Seal of Command hit, which the log writes as your cast) are not casts, here or in the fight's numbers.

A death is one the game means: Feign Death is logged as one too, told apart as in model/deaths.py.
healing_others, dispels_others: what went to a friendly unit other than you, a pet or a guardian (whose it is, the log
doesn't always say; a dispel of an enemy is a purge, not help). The group members' healing_others is theirs the same way.
helped: others than your group (players, their pets, friendly NPCs) did more than HELPED of your damage to your enemies,
or players outside it (or their pets) healed you for more than HELPED of the damage you took.

The result is a plain dict, so it can be saved as JSON and shown later.
"""
from __future__ import annotations

import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from ..model.deaths import feigns
from ..model.roster import clean_name
from ..scoring import usable
from ..scoring.classes import DEFENSIVES
from ..scoring.metrics import NEXT_SWING, WAND, auto_running, clip, count_hit, gaps, hit_table, swing_stats, \
    total, union
from ..sources.combatlog import TYPE_GUARDIAN, TYPE_PET, Event
from . import readiness
from .tracker import NOT_HOSTILE as NOT_FIGHTING
from .tracker import FightData, affiliation, is_foe, is_group

GCD = 1.5
AUTO = {5019, 75}                      # wand Shoot, Auto Shot
IDLE_GAP = 2.5
MIN_COOLDOWN = 4.0                     # shorter "cooldowns" are just how often you cast it
SPAM = 2.0                             # two casts closer than this: the spell has no cooldown
GAPS = 10                              # shortest gaps kept per spell
# gaps within this much above the shortest agree with it: a real cooldown is a hard floor many casts sit
# on (within about 2%), while a habit like re-sealing after each Judgement is spread out
AGREE = 0.05
RECENT = timedelta(days=7)             # a cooldown not cast for longer than this is dropped from the rows
HELD = 60.0                            # cooldowns this long are saved for bosses
VERDICT_SHARE = 0.03
CLEAN = 0.90                           # efficiency from which a fight is called clean
DEFENSIVE_WINDOW = 10.0                # a defensive cast this long before or after your lowest moment answered it
DEFENSIVE_CD = 300.0                   # a defensive's cooldown when the spell book doesn't know it
FORBEARANCE_LASTS = 60.0
HELPED = 0.10                          # of your damage done, or of the damage you took healed, by outsiders: more is help
NOBODY = ("", "0000000000000000")
FORBEARANCE = ("Divine Protection", "Divine Shield", "Blessing of Protection")      # not castable under it
# not pressing one of these in a fight you lived through is no mistake: you can't attack under it, or it ends the fight
HALTS = ("Divine Protection", "Blessing of Protection", "Ice Block", "Feign Death", "Vanish")
MASHING = {"Not yet recovered", "Another action is in progress", "Interrupted", "Spell not ready yet",
           "Item is not ready yet", "Can't do that while moving", "Your target is dead", "No target"}


def _rel(ts: datetime, start: datetime) -> float:
    return (ts - start).total_seconds()


def _fmt(n: float) -> str:
    return f"{n:,.0f}"


def new_entry() -> dict:
    """a spell book entry with nothing learned yet (code reads every key directly)"""
    return {"gaps": [], "spam": False, "last": None, "avg": 0, "cast": False, "cost": 0, "game_cd": None}


NO_GEAR_LEVEL = (4, 19)        # shirt and tabard say nothing about how strong you are


def gear_level(char: dict | None) -> int | None:
    """the mean item level over the slots that have one"""
    levels = [v for k, v in ((char or {}).get("gear") or {}).items() if v is not None and k not in NO_GEAR_LEVEL]
    return round(sum(levels) / len(levels)) if levels else None


def cooldown(entry: dict) -> float | None:
    """a spell book entry's cooldown in seconds: the shortest gap two others agree with; None if it has none"""
    if entry.get("spam") or entry.get("game_cd") == 0:      # game_cd 0: the game says it has none
        return None
    g = sorted(entry.get("gaps") or [])
    cd = next((x for i, x in enumerate(g) if sum(y <= x * (1 + AGREE) for y in g[i + 1:]) >= 2), None)
    game = entry.get("game_cd")
    if game and game > 0:
        return min(cd, game) if cd else game
    return cd


def owned(name: str, damage: dict[str, float], cast: set[str]) -> float:
    """the damage that belongs to a cast of `name`: its own, plus longer names starting with it that are never
    cast themselves ("Judgement" owns "Judgement of Command")"""
    return damage.get(name, 0) + sum(v for n, v in damage.items() if n.startswith(name + " ") and n not in cast
                                     and not n.endswith(" (pet)"))


def _spans(marks: list[float], at_pull: bool, dur: float) -> list[tuple[float, float]]:
    """when an aura was on you, from its applied (t) / removed (-t) marks; at_pull: on when the fight began"""
    out, since = [], (0.0 if at_pull else None)
    for m in marks:
        if m >= 0:
            since = m if since is None else since
        elif since is not None:
            out.append((since, -m))
            since = None
    return out + ([(since, dur)] if since is not None else [])


def filler(entry: dict) -> bool:
    """a damage spell you cast back to back, so there's always something to press"""
    cd = cooldown(entry)
    return entry.get("avg", 0) > 0 and (bool(entry.get("spam")) or (cd is not None and cd < MIN_COOLDOWN))


def procs(f: FightData, me: str) -> set[int]:
    """id() of each of your casts in the fight that is really a proc (the log writes a Seal of Command hit as
    your cast): it cost nothing, and an aura of that name is on you under another spell id (a real seal cast
    logs its own aura, same id, just before it; Seal of Command 20375, its proc 20424)"""
    # without Advanced Combat Logging every cost reads 0, so only the aura and the id tell them apart
    on: dict[str, int | None] = {n: None for n in f.buffs_at_pull}     # id unknown for those
    out = set()
    for e in f.events:
        if e.dst == me and e.spell_name and e.event in ("SPELL_AURA_APPLIED", "SPELL_AURA_REFRESH"):
            on[e.spell_name] = e.spell_id
        elif e.dst == me and e.event == "SPELL_AURA_REMOVED":
            on.pop(e.spell_name, None)
        elif e.event == "SPELL_CAST_SUCCESS" and e.src == me and e.spell_name in on \
                and on[e.spell_name] != e.spell_id and not (e.info and e.info.cost > 0):
            out.add(id(e))
    return out


def unused_defensives(at: float, casts: list[tuple], book: dict[str, dict], f: FightData, died: bool,
                      forbearance: list[tuple[float, float]]) -> list[str]:
    """defensives in your spell book that were off cooldown at `at` (seconds into the fight), could be cast and
    were worth it (see Danger in the module docstring)"""
    out = []
    for name in dict.fromkeys(n for names in DEFENSIVES.values() for n in names):
        if name not in book or (name in HALTS and not died) or (
                name in FORBEARANCE and any(a <= at <= b for a, b in forbearance)):
            continue
        times = [t for t, _, n, _, _ in casts if n == name and t <= at]
        before = f.cast_before.get(name)
        last = times[-1] if times else (_rel(before, f.start) if before else None)
        if last is None or last + (cooldown(book[name]) or DEFENSIVE_CD) <= at:
            out.append(name)
    return out


def idle_words(free: float, swinging: float | None, shooting: bool = False) -> str:
    """the free time with no ability used, split: "No ability used for 8.0 s while swinging and 3.0 s idle"; a
    fight saved before the split (swinging None) is all idle"""
    if not swinging or swinging < 0.05:
        return f"{free:.1f} s idle"
    said = f"No ability used for {swinging:.1f} s while {'shooting' if shooting else 'swinging'}"
    return said + (f" and {free - swinging:.1f} s idle" if free - swinging >= 0.05 else "")


def spoken(text: str) -> str:
    """a finding as a sentence a voice can read"""
    return text.replace(" ≈ ", ", about ") + "."


def summarize(f: FightData, me: str, me_name: str, book: dict[str, dict], history: list[dict],
              types: dict | None = None) -> dict | None:
    """the summary dict, or None for a fight that isn't worth one (a critter, a stray hit); "best before" only
    counts earlier fights within a level of this one. types: enemy name -> creature type (dipsScoreDB.types)"""
    start, end = f.start, f.end or f.start
    dur = max(0.1, _rel(end, start))
    pets = {e.dst for e in f.events if e.event == "SPELL_SUMMON" and e.src == me}

    def mine(guid: str) -> bool:
        return guid == me or guid in pets or (guid.startswith(("Pet-", "Creature-")) and guid in pets)

    def other(src: str, e: Event) -> bool:
        """the event's target is a friendly unit other than src, no pet or guardian, and not one of yours when src is you"""
        return e.dst != src and not is_foe(e.dst, e.dst_flags) and not e.dst_flags & (TYPE_PET | TYPE_GUARDIAN) \
            and not (src == me and affiliation(e.dst_flags) == 0x1)

    dmg_by_foe: Counter = Counter()
    spells: dict[str, dict] = {}
    casts: list[tuple[float, int, str, float | None, int]] = []   # t, spell id, name, began, cost
    starts: dict[int, float] = {}
    defended: list[float] = []                                   # defensives cast on yourself
    defensives = {n for names in DEFENSIVES.values() for n in names}
    swings: list[float] = []
    swing_dmg: list[int] = []
    slots: list[float] = []                                      # next-swing ability casts (Heroic Strike...)
    shots: list[float] = []
    shot_dmg: list[int] = []
    shot_ids: Counter = Counter()
    melee, ranged, taken_swings = hit_table(), hit_table(), hit_table()   # hit tables (see hit_table)
    avoided: dict[tuple[str, str], list[float]] = defaultdict(list)    # ("target"|"you", "dodge"...) -> times
    extra_hits: Counter = Counter()                              # extra swings by the spell that gave them
    taken: list[tuple[float, int, str, str]] = []
    hp: list[tuple[float, float]] = []
    power: list[tuple[float, float]] = []
    fails: Counter = Counter()
    heal = overheal = heal_others = 0
    interrupts = dispels = dispels_others = outside = outside_heal = 0
    auras: dict[str, list[float]] = defaultdict(list)            # buff name -> [applied, removed, ...] times
    own_auras: set[str] = set()                                  # the ones you put on yourself
    pos: list[tuple[float, float, float]] = []                   # your position (Advanced Combat Logging)
    power_abs: list[tuple[float, float]] = []
    power_type = level = None                                    # from the advanced log block
    foe_hp: dict[str, list[tuple[float, float]]] = defaultdict(list)
    cc: list[tuple[float, float]] = []
    costs: dict[str, list[int]] = defaultdict(list)
    # the group: other players with you, their pets, what they did
    party: dict[str, str] = {}
    owner: dict[str, str] = {}
    party_dmg: Counter = Counter()
    party_heal: Counter = Counter()
    party_heal_others: Counter = Counter()
    party_deaths: list[tuple[float, str]] = []
    hurt: list[tuple[float, float]] = []
    fighting: list[float] = []                                   # moments of fighting between the group and foes
    proc = procs(f, me)
    ranks: dict[str, set] = defaultdict(set)                     # the spell ids you cast, by name
    feigned = {id(f.events[i]) for i in feigns(f.events, {e.dst for e in f.events if e.dst.startswith("Player-")})}
    proc_ids = {e.spell_id for e in f.events if id(e) in proc}
    valued: Counter = Counter()                                  # your damage that values your casts (no procs)

    def row(name: str) -> dict:
        return spells.setdefault(name, {"casts": 0, "hits": 0, "crits": 0, "miss": 0, "damage": 0})

    for e in f.events:
        t = _rel(e.ts, start)
        ev = e.event
        if e.info and e.info.guid == me:
            hp.append((t, e.info.hp_pct))
            power_type, level = e.info.power_type, e.info.level
            pos.append((t, e.info.x, e.info.y))
            if e.info.max_power:
                power.append((t, e.info.power / e.info.max_power))
                power_abs.append((t, e.info.power))
        if e.info and e.info.guid in f.foes:
            foe_hp[e.info.guid].append((t, e.info.hp_pct))
        if e.info and e.info.guid.startswith("Player-") and e.info.max_hp and e.info.hp_pct < readiness.HURT \
                and (e.info.guid == me or e.info.guid in party):
            hurt.append((t, t + 2.0))
        if ev not in NOT_FIGHTING and ((is_group(e.src, e.src_flags) and is_foe(e.dst, e.dst_flags)) or
                                       (is_foe(e.src, e.src_flags) and is_group(e.dst, e.dst_flags))):
            fighting.append(t)
        for g, n, fl in ((e.src, e.src_name, e.src_flags), (e.dst, e.dst_name, e.dst_flags)):
            if g != me and g.startswith("Player-") and is_group(g, fl) and g not in party:
                party[g] = clean_name(n)
        if ev == "SPELL_SUMMON" and e.src in party:
            owner[e.dst] = e.src
        who_p = e.src if e.src in party else owner.get(e.src)
        if who_p:
            if ev.endswith("_DAMAGE") and not ev.endswith("_LANDED") and is_foe(e.dst, e.dst_flags):
                party_dmg[who_p] += e.amount
            elif ev.endswith("_HEAL") and e.src == who_p:
                party_heal[who_p] += max(0, e.amount - e.overheal)
                if other(who_p, e):
                    party_heal_others[who_p] += max(0, e.amount - e.overheal)
        elif e.dst in f.foes and e.src not in f.foes and not mine(e.src) and ev.endswith("_DAMAGE") \
                and not ev.endswith("_LANDED") and not is_group(e.src, e.src_flags) \
                and (e.src.startswith(("Player-", "Pet-")) or
                     e.src.startswith("Creature-") and not is_foe(e.src, e.src_flags)):
            outside += e.amount
        elif e.dst == me and ev.endswith("_HEAL") and not mine(e.src) and e.src.startswith(("Player-", "Pet-")) \
                and not is_group(e.src, e.src_flags):
            outside_heal += max(0, e.amount - e.overheal)
        if ev == "UNIT_DIED" and e.dst in party and id(e) not in feigned:
            party_deaths.append((t, party[e.dst]))
        if mine(e.src):
            name = e.spell_name or "Melee"
            if e.src != me:
                name += " (pet)"
            if ev.endswith("_DAMAGE") and not ev.endswith("_LANDED") and is_foe(e.dst, e.dst_flags):
                r = row(name)
                r["damage"] += e.amount
                r["hits"] += 1
                if e.src == me and e.spell_id not in proc_ids:
                    valued[name] += e.amount
                r["crits"] += e.crit
                dmg_by_foe[e.dst] += e.amount
                if ev.startswith("SWING") and e.src == me:
                    swings.append(t)
                    swing_dmg.append(e.amount)
            elif ev.endswith("_MISSED") and is_foe(e.dst, e.dst_flags):
                row(name)["miss"] += 1
                if ev.startswith("SWING") and e.src == me:
                    swings.append(t)
            elif ev == "SPELL_EXTRA_ATTACKS" and e.src == me:
                extra_hits[e.spell_name] += e.extra_count
            if ev in ("SWING_DAMAGE", "SWING_MISSED") and e.src == me and is_foe(e.dst, e.dst_flags):
                count_hit(melee, e)
            elif ev in ("RANGE_DAMAGE", "RANGE_MISSED") and e.src == me and is_foe(e.dst, e.dst_flags):
                count_hit(ranged, e)
                shots.append(t)
                shot_ids[e.spell_id] += 1
                if ev == "RANGE_DAMAGE":
                    shot_dmg.append(e.amount)
            elif ev.endswith("_HEAL") and e.src == me:
                heal += max(0, e.amount - e.overheal)
                overheal += e.overheal
                if other(me, e):
                    heal_others += max(0, e.amount - e.overheal)
            elif ev == "SPELL_CAST_START" and e.src == me:
                starts[e.spell_id] = t
            elif ev == "SPELL_CAST_SUCCESS" and e.src == me and id(e) not in proc:
                row(name)["casts"] += 1
                began = starts.pop(e.spell_id, None)
                cost = e.info.cost if e.info and e.info.guid == me else 0
                if cost and e.spell_id:
                    costs[name].append(cost)
                if e.spell_id:
                    ranks[name].add(e.spell_id)
                casts.append((t, e.spell_id or 0, name, began if began is not None and t - began < 10 else None, cost))
                if name in NEXT_SWING:
                    slots.append(t)
                if name in defensives and (e.dst == me or e.dst in NOBODY or is_foe(e.dst, e.dst_flags)):
                    defended.append(t)
            elif ev == "SPELL_CAST_FAILED" and e.src == me:
                fails[(e.spell_name, e.reason or "unknown")] += 1
                if (e.reason or "").startswith("Can't do that while"):
                    cc.append((t - 1.0, t + 3.0))
            elif ev.endswith("_INTERRUPT"):
                interrupts += 1
            elif ev.endswith("_DISPEL"):
                dispels += 1
                dispels_others += other(me, e)
        if e.dst == me and ev in ("SWING_DAMAGE", "SWING_MISSED") and is_foe(e.src, e.src_flags):
            count_hit(taken_swings, e)
        # avoided attacks, for the spells that answer them (usable.py): any attack, swing or spell
        if ev.endswith("_MISSED") and e.miss_type in ("DODGE", "PARRY", "BLOCK"):
            if e.src == me and is_foe(e.dst, e.dst_flags):
                avoided[("target", e.miss_type.lower())].append(t)
            elif e.dst == me and is_foe(e.src, e.src_flags):
                avoided[("you", e.miss_type.lower())].append(t)
        elif e.dst == me and ev.endswith("_DAMAGE") and e.blocked > 0 and is_foe(e.src, e.src_flags):
            avoided[("you", "block")].append(t)       # a partly blocked hit is a block
        if e.dst == me and ev.endswith("_DAMAGE") and not ev.endswith("_LANDED") and e.amount:
            who = clean_name(e.src_name) if e.src.startswith("Player-") else (e.src_name or "?")
            taken.append((t, e.amount, e.spell_name or "Melee", who))
        if e.dst == me and e.spell_name and ev in ("SPELL_AURA_APPLIED", "SPELL_AURA_REMOVED"):
            auras[e.spell_name].append(t if ev == "SPELL_AURA_APPLIED" else -t - 1e-9)
            if ev == "SPELL_AURA_APPLIED" and e.src == me:
                own_auras.add(e.spell_name)

    damage = sum(r["damage"] for r in spells.values())
    total_taken = sum(a for _, a, _, _ in taken)
    if damage == 0 and heal == 0 and total_taken == 0:
        return None
    if dur < 1.0 or (dur < 2.0 and damage < 50):
        return None                    # a one-hit "fight": nothing to judge

    # ---- who it was against
    # players first (a fight with one in it is named for them), then most damaged
    foes = sorted(f.foes.values(), key=lambda fo: (not fo.player, -dmg_by_foe.get(fo.guid, 0)))
    main = foes[0] if foes else None
    target = clean_name(main.name) if main and main.player else (f.boss or (main.name if main else "?"))
    extra = len({fo.name for fo in foes}) - 1
    # every enemy, in that order, as [name, how many]
    foe_names = Counter()
    for fo in foes:
        foe_names[clean_name(fo.name) if fo.player else fo.name] += 1
    pvp = any(fo.player for fo in foes)
    # an instance id means a dungeon (some report difficulty 0, like the open world does)
    kind = "PvP" if pvp else ("Boss" if f.boss else ("Dungeon" if f.instance or f.difficulty else "World"))
    died_at = next((_rel(e.ts, start) for e in f.events if e.event == "UNIT_DIED" and e.dst == me
                    and id(e) not in feigned), None)
    i_died = died_at is not None
    killed = bool(foes) and all(fo.died is not None for fo in foes)
    result = "you died" if i_died else ("killed" if killed else "they got away")

    # ---- abilities
    abilities = sorted(({"name": n, **r, "avg": (r["damage"] / r["hits"]) if r["hits"] else 0,
                         "share": r["damage"] / damage if damage else 0}
                        for n, r in spells.items() if r["damage"] or r["casts"]),
                       key=lambda r: r["damage"], reverse=True)

    # ---- what the excuses need (see readiness.py)
    bars = []
    for t, sid, _, began, _ in casts:
        if sid not in AUTO:
            a = began if began is not None else t
            bars.append((a, max(t, a + GCD)))
    ctx = readiness.Context(
        dur=dur, moving=readiness.moving_intervals(pos), power=power_abs,
        start_power=power_abs[0][1] if power_abs else None, cc=cc, bars=bars,
        foes=[(_rel(fo.first, start), _rel(fo.died, start) if fo.died else None, foe_hp.get(fo.guid, []))
              for fo in f.foes.values()],
        hurt=hurt, you_heal=heal > 0, lulls=readiness.lulls(fighting, dur))

    # ---- when the spells that need a target type, a low target or an avoided attack could be used
    foe_list = [(fo.name, _rel(fo.first, start), _rel(fo.died, start) if fo.died else None, foe_hp.get(fo.guid, []))
                for fo in f.foes.values()]
    # a stance first seen leaving was on from the pull
    stances = {n: _spans(auras.get(n, []), n in f.buffs_at_pull or auras[n][0] < 0, dur) for n in usable.STANCES
               if n in auras or n in f.buffs_at_pull}
    chances = {n: usable.fight_chances(r, dur, foe_list, types, avoided, stances) for n, r in usable.RULES.items()}

    # ---- cooldowns: when each damage cooldown sat ready while you were free to use it
    cd_rows, cd_lost = [], 0.0
    by_spell: dict[str, list[tuple[float, float]]] = defaultdict(list)
    cast_time: dict[str, bool] = {}
    for t, sid, name, began, _ in casts:
        if sid and sid not in AUTO:
            by_spell[name].append((began if began is not None else t, t))
            cast_time[name] = cast_time.get(name, False) or began is not None
    own_dmg = dict(valued)
    cast_names = {n for n, r in spells.items() if r["casts"]}
    for name, entry in book.items():
        cd, uses = cooldown(entry), by_spell.get(name, [])
        before = f.cast_before.get(name)
        if not cd or cd < MIN_COOLDOWN or not (uses or (before and start - before <= RECENT)):
            continue
        per_cast = (owned(name, own_dmg, cast_names) / len(uses) if uses else 0) or entry.get("avg", 0)
        if per_cast <= 0:
            continue                      # not a damage spell (an unused shield costs nothing)
        ready0 = max(0.0, _rel(before, start) + cd) if before else 0.0
        windows = readiness.ready_windows(uses, cd, ready0, dur)
        cost = statistics.median(costs[name]) if costs.get(name) else entry.get("cost", 0)
        rule = usable.rule(name)
        can, n_chances = chances.get(name, (None, None))
        free, why = readiness.judge(windows, ctx, cast_time.get(name, entry.get("cast", False)), cost,
                                    can, usable.reason(rule) if rule else "")
        limit = dur - GCD
        possible = int((limit - ready0) // cd) + 1 if ready0 <= limit else 0
        if can is not None:               # only the casts that fit in its chances
            possible = max(len(uses), min(possible, sum(math.ceil((b - a) / cd) for a, b in can)))
        held = cd >= HELD and kind != "Boss"
        lost = 0.0 if held else free / cd * per_cast
        cd_lost += lost
        missed = max(0, possible - len(uses))
        cd_rows.append({"name": name, "cd": cd, "used": len(uses), "ready": sum(b - a for a, b in windows),
                        "free": free, "excused": {k: round(v, 1) for k, v in why.most_common() if v >= 0.05},
                        "lost": lost, "possible": possible, "missed": missed,
                        "counted": 0 if free < 2.0 else min(missed, max(1, round(free / cd))),
                        **({"chances": n_chances} if n_chances is not None else {}),
                        **({"held": True} if held else {})})
    cd_rows.sort(key=lambda r: -r["lost"])

    # ---- idle: gaps with no cast and no GCD running (before auto attacks: a wand's shots skip the priced ones)
    busy = sorted(bars)
    idle_res = idle_out = idle_moving = 0.0
    typical_cost = statistics.median([c for *_, c in casts if c]) if any(c for *_, c in casts) else 0
    first_power = f.start_power
    cur = 0.0
    gaps_idle = []
    for a, b in busy + [(dur, dur)]:
        if a - cur >= IDLE_GAP:
            gaps_idle.append((cur, a))
        cur = max(cur, b)
    priced = []                   # per gap with resource, its time not excused (moving, cc, lull)
    for a, b in gaps_idle:
        p_then = next((pw for t, pw in reversed(power) if t <= a), first_power)
        low = typical_cost and p_then is not None and p_then < 0.08
        if low:
            idle_out += b - a
            continue
        excused = sum(max(0.0, min(b, y) - max(a, x)) for x, y in ctx.moving + ctx.cc + ctx.lulls)
        idle_moving += min(b - a, excused)
        idle_res += max(0.0, b - a - excused)
        priced.append(gaps(ctx.moving + ctx.cc + ctx.lulls, [(a, b)], 0.0))
    has_filler = any(filler(e) for e in book.values())

    # ---- auto attacks
    auto = None
    swing_lost = shot_lost = 0.0
    hard = [(b, t) for t, sid, _, b, _ in casts if b is not None and sid not in AUTO]   # Shoot has a cast start
    slots = sorted(swings + slots)
    speed = 0.0
    if len(swings) >= 2:
        speed, lost_while_casting, lost_other = swing_stats(slots, hard)
        avg = statistics.mean(swing_dmg) if swing_dmg else 0
        swing_lost = lost_other * avg
        auto = {"swings": len(swings), "speed": speed, "lost": lost_while_casting + lost_other,
                "lost_casting": lost_while_casting, "lost_other": lost_other, "damage_lost": swing_lost,
                **melee, "extra": dict(extra_hits)}
    shot_speed = 0.0
    if len(shots) >= 2:
        # moving, or no enemy alive, isn't a lost shot
        alive = union([(a, b if b is not None else dur) for a, b, _ in ctx.foes])
        wand = shot_ids.most_common(1)[0][0] == WAND
        # a wand stops for every cast: an idle gap priced as idle isn't charged again as lost shots
        idle_paid = [x for sp in priced for x in sp] if wand and has_filler else []
        shot_speed, clipped, n_lost = swing_stats(shots, ctx.bars if wand else hard, None,
                                                  ctx.moving + gaps(alive, [(0.0, dur)], 0.0) + idle_paid)
        shot_lost = n_lost * (statistics.mean(shot_dmg) if shot_dmg else 0)
        ranged.update(shots=len(shots), speed=shot_speed, shots_lost=n_lost, clipped=clipped, damage_lost=shot_lost)
    running = auto_running(slots, speed) + auto_running(shots, shot_speed)
    shooting = len(shots) > len(slots)          # the word: "while shooting" or "while swinging"

    swing_res = sum(total(clip(running, sp)) for sp in priced)
    swing_res = min(swing_res, idle_res)
    swinging = total(clip(running, gaps_idle))
    spell_dps = (damage - sum(swing_dmg) - sum(shot_dmg)) / dur if dur else 0      # ability damage only
    idle_lost = 0.5 * idle_res * spell_dps if has_filler else 0.0

    # ---- buffs on you: uptime over the fight
    buffs = []
    for name, marks in auras.items():
        up = total(_spans(marks, name in f.buffs_at_pull, dur))
        if up > 0:
            buffs.append({"name": name, "uptime": min(1.0, up / dur)})
    for name in f.buffs_at_pull:
        if name not in auras:
            buffs.append({"name": name, "uptime": 1.0})
    buffs.sort(key=lambda b: -b["uptime"])

    # ---- danger: your lowest health and what put you there
    danger = None
    if hp:
        t_low, low = min(hp, key=lambda v: v[1])
        if low < 0.35:
            hits = sorted((h for h in taken if t_low - 3 <= h[0] <= t_low), key=lambda h: -h[1])[:5]
            if hits:
                at = died_at if i_died else t_low
                answered = any(abs(t - at) <= DEFENSIVE_WINDOW for t in defended)
                old = f.forbearance is not None and _rel(f.forbearance, start) > -FORBEARANCE_LASTS     # else its removal was missed
                forbearance = _spans(auras.get("Forbearance", []), old, dur)
                if old:
                    forbearance[0] = (_rel(f.forbearance, start), forbearance[0][1])
                forbearance = [(a, min(b, a + FORBEARANCE_LASTS)) for a, b in forbearance]
                danger = {"t": t_low, "hp": low, "hits": [{"who": w, "spell": s, "amount": a} for _, a, s, w in hits],
                          "answered": answered, "unused": [] if answered else
                          unused_defensives(at, casts, book, f, i_died, forbearance)}

    failed = [{"spell": s, "reason": r, "count": n} for (s, r), n in fails.most_common()]
    # mostly healing, or no damage at all (a stray hit you never joined in): damage you "could have done"
    # isn't the point, so it isn't counted against you
    healing_role = heal > damage
    unjudged = healing_role or damage == 0
    if unjudged:
        cd_lost = swing_lost = shot_lost = idle_lost = 0.0
    if damage == 0:
        cd_rows = []                   # a healing fight keeps its rows to look at; with no damage they're noise
    potential = damage + cd_lost + swing_lost + shot_lost + idle_lost
    efficiency = damage / potential if potential else 1.0
    dps = damage / max(dur, 1.5)

    # ---- the group: who was with you, and your share
    group = None
    active = [g for g in party if party_dmg[g] or party_heal[g]]
    if active:
        everyone_dmg = {**{g: party_dmg[g] for g in active}, me: damage}
        everyone_heal = {**{g: party_heal[g] for g in active}, me: heal}
        total_dmg, total_heal = sum(everyone_dmg.values()), sum(everyone_heal.values())
        rank = lambda d: 1 + sum(1 for v in d.values() if v > d[me])  # noqa: E731
        group = {
            "size": len(active) + 1, "names": [party[g] for g in active],
            "damage_share": damage / total_dmg if total_dmg else 0, "damage_rank": rank(everyone_dmg),
            "heal_share": heal / total_heal if total_heal else 0, "heal_rank": rank(everyone_heal),
            "members": [{"name": party[g], "damage": party_dmg[g], "healing": party_heal[g],
                         "healing_others": party_heal_others[g]} for g in active],
            "deaths": [n for _, n in party_deaths],
        }

    # ---- compared with you before
    # a fight with no level on either side still compares (old history has none)
    same = [h for h in history if h.get("target") == target and h.get("kind") == kind and h.get("dps")
            and (level is None or h.get("level") is None or abs(h["level"] - level) <= 1)]
    best = max((h["dps"] for h in same), default=None)

    good, improve = [], []
    if healing_role:
        oh = overheal / (heal + overheal) if heal + overheal else 0
        good.append(f"Healed {_fmt(heal)}" + (f" with only {oh:.0%} overhealing" if oh < 0.2 else ""))
    if best is not None and dps > best:
        good.append(f"Beat your best on {target}: {dps:.0f} DPS ({dps - best:+.0f})")
    judged = [r for r in cd_rows if not r.get("held")]
    if judged and not healing_role and all(r["free"] < 2.0 for r in judged):
        good.append("Used your cooldowns as they came up")
    if group and not healing_role and group["damage_rank"] == 1 and group["size"] > 1:
        good.append(f"Top damage in the group ({group['damage_share']:.0%})")
    if has_filler and not gaps_idle and dur >= 6:
        good.append("No idle gaps")
    if interrupts:
        good.append(f"{interrupts} interrupt{'s' if interrupts != 1 else ''}")
    if dispels:
        good.append(f"{dispels} dispel{'s' if dispels != 1 else ''}")
    if hp and min(p for _, p in hp) >= 0.5 and total_taken:
        good.append(f"Never below {min(p for _, p in hp):.0%} health")
    kept = [b for b in buffs if b["uptime"] >= 0.85 and b["name"] in own_auras]
    if kept:
        good.append(f"Kept {kept[0]['name']} up {kept[0]['uptime']:.0%}")
    if not failed and casts:
        good.append("No failed casts")

    for r in ([] if healing_role else judged):
        if r["free"] >= 2.0 and r["lost"] >= 1:
            said = usable.across(r.get("chances"))
            improve.append((r["lost"], f"{r['name']} sat ready {r['free']:.1f} s{said} while you were free "
                                       f"≈ {_fmt(r['lost'])} damage"))
    if group and group["deaths"] and healing_role:
        improve.append((1e9, f"{', '.join(group['deaths'])} died"))
    if auto and auto["lost_other"] and not unjudged:
        improve.append((swing_lost, f"{auto['lost_other']} swing{'s' if auto['lost_other'] != 1 else ''} lost while "
                                    f"not attacking ≈ {_fmt(swing_lost)} damage"))
    if ranged.get("shots_lost") and not unjudged:
        n = ranged["shots_lost"]
        improve.append((shot_lost, f"{n} shot{'s' if n != 1 else ''} lost while not shooting "
                                   f"≈ {_fmt(shot_lost)} damage"))
    if has_filler and idle_res >= IDLE_GAP and not unjudged:
        improve.append((idle_lost, idle_words(idle_res, swing_res, shooting) +
                        f" with a target, standing, with resource to spare ≈ {_fmt(idle_lost)} damage"))
    for row_ in failed:
        if row_["reason"] not in MASHING and not row_["reason"].startswith("Can't do that while"):
            improve.append((0.1, f"{row_['spell']}: {row_['reason']} ×{row_['count']}"))
    if danger and danger["unused"]:
        improve.append((0.21, f"Dropped to {danger['hp']:.0%} health with {' and '.join(danger['unused'][:2])} ready"))
    elif danger:
        top = danger["hits"][0] if danger["hits"] else None
        improve.append((0.2, f"Dropped to {danger['hp']:.0%} health" +
                        (f" ({top['who']}: {top['spell']} for {_fmt(top['amount'])})" if top else "")))
    if power and power[-1][1] < 0.1:
        improve.append((0.05, f"Ended on {power[-1][1]:.0%} power"))
    improve.sort(key=lambda v: -v[0])

    if i_died:
        last = taken[-1] if taken else None
        verdict = f"Killed by {last[3]}: {last[2]} for {_fmt(last[1])}." if last else "You died."
    elif healing_role and good:
        verdict = good[0] + "."
    elif not healing_role and damage == 0:
        verdict = "No damage done this fight."
    elif improve and (improve[0][0] >= VERDICT_SHARE * damage or (efficiency < CLEAN and improve[0][0] > 0)):
        verdict = spoken(improve[0][1])
    else:
        verdict = ("Clean fight: " if efficiency >= CLEAN else "") + f"{efficiency:.0%} of the damage that was possible."

    return {
        "id": f"{start:%Y%m%d%H%M%S%f}",           # the start: a combat that carries on keeps it
        "start": start.isoformat(), "end": end.isoformat(), "duration": dur,
        "me": me, "me_name": clean_name(me_name) if me_name else "",
        "kind": kind, "difficulty": f.difficulty, "instance": f.instance, "zone": f.zone, "target": target, "more": max(0, extra), "result": result,
        "foes": [[n, c] for n, c in foe_names.items()],
        "damage": damage, "dps": dps, "healing": heal, "overheal": overheal, "taken": total_taken,
        "lowest_hp": min((p for _, p in hp), default=None),
        "potential": potential, "efficiency": efficiency,
        "healing_role": healing_role, "verdict": verdict,
        "opener": [c[2] for c in casts[:3]],       # your first three casts, in time order
        "best_before": best,
        "good": good[:4], "improve": [text for _, text in improve][:5],
        "cast_ids": {n: sorted(ids) for n, ids in ranks.items()},      # which rank of a spell, by id
        "danger": danger, "abilities": abilities, "cooldowns": cd_rows, "auto": auto,
        "ranged": ranged if ranged["landed"] or ranged["misses"] else None,
        "swings_taken": taken_swings if taken_swings["landed"] or taken_swings["misses"] else None,
        "idle": {"total": idle_res + idle_out + idle_moving, "with_resource": idle_res,
                 "out_of_resource": idle_out, "moving": idle_moving, "lost": idle_lost,
                 "filler": has_filler,
                 # of total, and of with_resource: auto-attack running ("no ability used while swinging")
                 "swinging": swinging, "swinging_free": swing_res, "shooting": shooting},
        "group": group,
        "buffs": buffs, "failed": failed,
        "resource": {"start": f.start_power, "end": power[-1][1] if power else None,
                     "start_hp": f.start_hp, "type": power_type},
        "level": level,
        "pull": {"since_last": f.since_last, "buffs": f.buffs_at_pull, "own": f.own_buffs_at_pull, "rest": f.rest},
        "interrupts": interrupts, "dispels": dispels,
        "healing_others": heal_others, "dispels_others": dispels_others,
        "helped": outside > HELPED * damage or outside_heal > HELPED * total_taken,
        # chances of the spells that answer health or avoided attacks (usable.py), where known; creature-type
        # chances are counted from "foes"
        "chances": {n: c for n, (_, c) in chances.items() if c is not None and "types" not in usable.RULES[n]},
    }


def learn_cooldowns(f: FightData, me: str, book: dict[str, dict]) -> bool:
    """add the fight's casts to your spell book (casts already learned are skipped); True if anything changed"""
    # this runs before summarize, and learning moves a spell's last cast into the fight: so first keep the
    # book's last casts from before it (the tracker's own list is empty after a restart)
    for name, entry in book.items():
        if entry["last"] and name not in f.cast_before and datetime.fromisoformat(entry["last"]) < f.start:
            f.cast_before[name] = datetime.fromisoformat(entry["last"])
    dmg: Counter = Counter()
    casts: Counter = Counter()
    began: dict[str, datetime] = {}
    new: set[str] = set()
    cast: set[str] = set()
    proc = procs(f, me)
    proc_ids = {e.spell_id for e in f.events if id(e) in proc}      # their damage is not a cast's value
    for e in f.events:
        name = e.spell_name
        if e.src != me or not name:
            continue
        if e.event.endswith("_DAMAGE") and not e.event.endswith("_LANDED") and is_foe(e.dst, e.dst_flags):
            if e.spell_id not in proc_ids:
                dmg[name] += e.amount
        elif e.event == "SPELL_CAST_START":
            began[name] = e.ts
        elif e.event == "SPELL_CAST_SUCCESS" and e.spell_id and e.spell_id not in AUTO and id(e) not in proc:
            casts[name] += 1
            cast.add(name)
            entry = book.setdefault(name, new_entry())
            start = began.pop(name, None)
            last = datetime.fromisoformat(entry["last"]) if entry["last"] else None
            if last and e.ts <= last:
                continue
            if last:
                gap = (e.ts - last).total_seconds()
                if gap < SPAM:
                    entry["spam"] = True
                else:
                    entry["gaps"] = sorted(entry["gaps"] + [round(gap, 2)])[:GAPS]
            entry["last"] = e.ts.isoformat()
            entry["cast"] = entry["cast"] or (start is not None and (e.ts - start).total_seconds() < 10)
            if e.info and e.info.guid == me:
                entry["cost"] = e.info.cost
            new.add(name)
    for name in new:
        if v := owned(name, dmg, cast):
            book[name]["avg"] = v / casts[name]
    return bool(new)
