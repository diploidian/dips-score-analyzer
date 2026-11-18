"""One fight, summed up from the combat log: your numbers, what went well, what cost you damage, and
(in a group) your share of it.

Everything is about you (and your pets). Damage you could have done is only counted where there was no good
reason not to (see readiness.py):
    cooldowns sat ready    time a damage cooldown was ready while you were free to use it - not moving
                           (cast-time spells), not out of mana, not stunned, the target not nearly dead,
                           not healing someone who was low
    melee swings lost      gaps in your auto-attacks longer than 1.6 swings, while you weren't casting
    idle time              gaps of 2.5 s+ with nothing cast, while you weren't moving or stunned and had
                           the resource to cast (half counted: not every gap is a mistake)
The result is a plain dict, so it can be saved as JSON and shown later.
"""
from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from datetime import datetime

from ..model.roster import clean_name
from ..sources.combatlog import Event
from . import readiness
from .tracker import NOT_HOSTILE as NOT_FIGHTING
from .tracker import FightData, is_foe, is_group

GCD = 1.5
AUTO = {5019, 75}                      # wand Shoot, Auto Shot
IDLE_GAP = 2.5
MIN_COOLDOWN = 4.0                     # shorter "cooldowns" are just how often you cast it
MASHING = {"Not yet recovered", "Another action is in progress", "Interrupted", "Spell not ready yet",
           "Item is not ready yet", "Can't do that while moving", "Your target is dead", "No target"}


def _rel(ts: datetime, start: datetime) -> float:
    return (ts - start).total_seconds()


def _fmt(n: float) -> str:
    return f"{n:,.0f}"


def summarize(f: FightData, me: str, me_name: str, cooldowns: dict[int, float], history: list[dict]) -> dict | None:
    """the summary dict, or None for a fight that isn't worth one (a critter, a stray hit)"""
    start, end = f.start, f.end or f.start
    dur = max(0.1, _rel(end, start))
    pets = {e.dst for e in f.events if e.event == "SPELL_SUMMON" and e.src == me}

    def mine(guid: str) -> bool:
        return guid == me or guid in pets or (guid.startswith(("Pet-", "Creature-")) and guid in pets)

    dmg_by_foe: Counter = Counter()
    spells: dict[str, dict] = {}
    casts: list[tuple[float, int, str, float | None, int]] = []   # t, spell id, name, began, cost
    starts: dict[int, float] = {}
    swings: list[float] = []
    swing_dmg: list[int] = []
    taken: list[tuple[float, int, str, str]] = []
    hp: list[tuple[float, float]] = []
    power: list[tuple[float, float]] = []
    fails: Counter = Counter()
    heal = overheal = 0
    interrupts = dispels = 0
    auras: dict[str, list[float]] = defaultdict(list)            # buff name -> [applied, removed, ...] times
    own_auras: set[str] = set()                                  # the ones you put on yourself
    pos: list[tuple[float, float, float]] = []                   # your position (Advanced Combat Logging)
    power_abs: list[tuple[float, float]] = []
    foe_hp: dict[str, list[tuple[float, float]]] = defaultdict(list)
    cc: list[tuple[float, float]] = []
    costs: dict[int, list[int]] = defaultdict(list)
    # the group: other players with you, their pets, what they did
    party: dict[str, str] = {}
    owner: dict[str, str] = {}
    party_dmg: Counter = Counter()
    party_heal: Counter = Counter()
    party_deaths: list[tuple[float, str]] = []
    hurt: list[tuple[float, float]] = []
    fighting: list[float] = []                                   # moments of fighting between the group and foes

    def row(name: str) -> dict:
        return spells.setdefault(name, {"casts": 0, "hits": 0, "crits": 0, "miss": 0, "damage": 0})

    for e in f.events:
        t = _rel(e.ts, start)
        ev = e.event
        if e.info and e.info.guid == me:
            hp.append((t, e.info.hp_pct))
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
        if ev == "UNIT_DIED" and e.dst in party:
            party_deaths.append((t, party[e.dst]))
        if mine(e.src):
            name = e.spell_name or "Melee"
            if e.src != me:
                name += " (pet)"
            if ev.endswith("_DAMAGE") and not ev.endswith("_LANDED") and is_foe(e.dst, e.dst_flags):
                r = row(name)
                r["damage"] += e.amount
                r["hits"] += 1
                r["crits"] += e.crit
                dmg_by_foe[e.dst] += e.amount
                if ev.startswith("SWING") and e.src == me:
                    swings.append(t)
                    swing_dmg.append(e.amount)
            elif ev.endswith("_MISSED") and is_foe(e.dst, e.dst_flags):
                row(name)["miss"] += 1
                if ev.startswith("SWING") and e.src == me:
                    swings.append(t)
            elif ev.endswith("_HEAL") and e.src == me:
                heal += max(0, e.amount - e.overheal)
                overheal += e.overheal
            elif ev == "SPELL_CAST_START" and e.src == me:
                starts[e.spell_id] = t
            elif ev == "SPELL_CAST_SUCCESS" and e.src == me:
                row(name)["casts"] += 1
                began = starts.pop(e.spell_id, None)
                cost = e.info.cost if e.info and e.info.guid == me else 0
                if cost and e.spell_id:
                    costs[e.spell_id].append(cost)
                casts.append((t, e.spell_id or 0, name, began if began is not None and t - began < 10 else None, cost))
            elif ev == "SPELL_CAST_FAILED" and e.src == me:
                fails[(e.spell_name, e.reason or "unknown")] += 1
                if (e.reason or "").startswith("Can't do that while"):
                    cc.append((t - 1.0, t + 3.0))
            elif ev.endswith("_INTERRUPT"):
                interrupts += 1
            elif ev.endswith("_DISPEL"):
                dispels += 1
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
    foes = list(f.foes.values())
    main = max(foes, key=lambda fo: dmg_by_foe.get(fo.guid, 0)) if foes else None
    target = f.boss or (clean_name(main.name) if main and main.player else (main.name if main else "?"))
    extra = len({fo.name for fo in foes}) - 1
    pvp = any(fo.player for fo in foes)
    # an instance id means a dungeon (some report difficulty 0, like the open world does)
    kind = "PvP" if pvp else ("Boss" if f.boss else ("Dungeon" if f.instance or f.difficulty else "World"))
    i_died = any(e.event == "UNIT_DIED" and e.dst == me for e in f.events)
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

    # ---- cooldowns: when each damage cooldown sat ready while you were free to use it
    cd_rows, cd_lost = [], 0.0
    by_spell: dict[int, list[tuple[float, float]]] = defaultdict(list)
    names: dict[int, str] = {}
    cast_time: dict[int, bool] = {}
    for t, sid, name, began, _ in casts:
        if sid and sid not in AUTO:
            by_spell[sid].append((began if began is not None else t, t))
            names[sid] = name
            cast_time[sid] = cast_time.get(sid, False) or began is not None
    for sid, uses in by_spell.items():
        cd = cooldowns.get(sid)
        per_cast = spells.get(names[sid], {}).get("damage", 0) / len(uses)
        if not cd or cd < MIN_COOLDOWN or per_cast <= 0:
            continue                      # no cooldown, or not a damage spell (an unused shield costs nothing)
        before = f.cast_before.get(sid)
        ready0 = max(0.0, _rel(before, start) + cd) if before else 0.0
        windows = readiness.ready_windows(uses, cd, ready0, dur)
        cost = statistics.median(costs[sid]) if costs.get(sid) else 0
        free, why = readiness.judge(windows, ctx, cast_time.get(sid, False), cost)
        lost = free / cd * per_cast
        cd_lost += lost
        cd_rows.append({"name": names[sid], "cd": cd, "used": len(uses), "ready": sum(b - a for a, b in windows),
                        "free": free, "excused": {k: round(v, 1) for k, v in why.most_common() if v >= 0.05},
                        "lost": lost})
    cd_rows.sort(key=lambda r: -r["lost"])

    # ---- auto attacks
    auto = None
    swing_lost = 0.0
    if len(swings) >= 2:
        gaps = [b - a for a, b in zip(swings, swings[1:])]
        speed = statistics.median(gaps) if gaps else 0
        lost_while_casting = lost_other = 0
        bars = [(b, t) for t, _, _, b, _ in casts if b is not None]
        for a, b in zip(swings, swings[1:]):
            n_lost = int((b - a) / speed - 0.6) if speed else 0
            if n_lost > 0:
                if any(s <= b and e >= a for s, e in bars):
                    lost_while_casting += n_lost
                else:
                    lost_other += n_lost
        avg = statistics.mean(swing_dmg) if swing_dmg else 0
        swing_lost = lost_other * avg
        auto = {"swings": len(swings), "speed": speed, "lost": lost_while_casting + lost_other,
                "lost_casting": lost_while_casting, "lost_other": lost_other, "damage_lost": swing_lost}

    # ---- idle: gaps with no cast and no GCD running
    busy = []
    for t, sid, _, began, _ in casts:
        if sid in AUTO:
            continue
        a = began if began is not None else t
        busy.append((a, max(t, a + GCD)))
    busy.sort()
    idle_res = idle_out = 0.0
    typical_cost = statistics.median([c for *_, c in casts if c]) if any(c for *_, c in casts) else 0
    first_power = f.start_power
    cur = 0.0
    gaps_idle = []
    for a, b in busy + [(dur, dur)]:
        if a - cur >= IDLE_GAP:
            gaps_idle.append((cur, a))
        cur = max(cur, b)
    idle_moving = 0.0
    for a, b in gaps_idle:
        p_then = next((pw for t, pw in reversed(power) if t <= a), first_power)
        low = typical_cost and p_then is not None and p_then < 0.08
        if low:
            idle_out += b - a
            continue
        excused = sum(max(0.0, min(b, y) - max(a, x)) for x, y in ctx.moving + ctx.cc + ctx.lulls)
        idle_moving += min(b - a, excused)
        idle_res += max(0.0, b - a - excused)
    spell_dps = (damage - sum(swing_dmg)) / dur if dur else 0
    idle_lost = 0.5 * idle_res * spell_dps

    # ---- buffs on you: uptime over the fight
    buffs = []
    for name, marks in auras.items():
        up, since = 0.0, (0.0 if name in f.buffs_at_pull else None)
        for m in marks:
            if m >= 0:
                since = m if since is None else since
            else:
                if since is not None:
                    up += -m - since
                    since = None
        if since is not None:
            up += dur - since
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
                danger = {"t": t_low, "hp": low, "hits": [{"who": w, "spell": s, "amount": a} for _, a, s, w in hits]}

    failed = [{"spell": s, "reason": r, "count": n} for (s, r), n in fails.most_common()]
    # mostly healing: damage you "could have done" isn't the point, so it isn't counted against you
    healing_role = heal > damage
    if healing_role:
        cd_lost = swing_lost = idle_lost = 0.0
    potential = damage + cd_lost + swing_lost + idle_lost
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
            "members": [{"name": party[g], "damage": party_dmg[g], "healing": party_heal[g]} for g in active],
            "deaths": [n for _, n in party_deaths],
        }

    # ---- compared with you before
    same = [h for h in history if h.get("target") == target and h.get("kind") == kind and h.get("dps")]
    best = max((h["dps"] for h in same), default=None)

    good, improve = [], []
    if healing_role:
        oh = overheal / (heal + overheal) if heal + overheal else 0
        good.append(f"Healed {_fmt(heal)}" + (f" with only {oh:.0%} overhealing" if oh < 0.2 else ""))
    if best is not None and dps > best:
        good.append(f"Beat your best on {target}: {dps:.0f} DPS ({dps - best:+.0f})")
    if cd_rows and not healing_role and all(r["free"] < 2.0 for r in cd_rows):
        good.append("Used your cooldowns as they came up")
    if group and not healing_role and group["damage_rank"] == 1 and group["size"] > 1:
        good.append(f"Top damage in the group ({group['damage_share']:.0%})")
    if not gaps_idle and dur >= 6:
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

    for r in ([] if healing_role else cd_rows):
        if r["free"] >= 2.0 and r["lost"] >= 1:
            improve.append((r["lost"], f"{r['name']} sat ready {r['free']:.1f} s while you were free "
                                       f"≈ {_fmt(r['lost'])} damage"))
    if group and group["deaths"] and healing_role:
        improve.append((1e9, f"{', '.join(group['deaths'])} died"))
    if auto and auto["lost_other"] and not healing_role:
        improve.append((swing_lost, f"{auto['lost_other']} swing{'s' if auto['lost_other'] != 1 else ''} lost while "
                                    f"not attacking ≈ {_fmt(swing_lost)} damage"))
    if idle_res >= IDLE_GAP and not healing_role:
        improve.append((idle_lost, f"{idle_res:.1f} s idle with a target, standing, with resource to spare "
                                   f"≈ {_fmt(idle_lost)} damage"))
    for row_ in failed:
        if row_["reason"] not in MASHING and not row_["reason"].startswith("Can't do that while"):
            improve.append((0.1, f"{row_['spell']}: {row_['reason']} ×{row_['count']}"))
    if danger:
        top = danger["hits"][0] if danger["hits"] else None
        improve.append((0.2, f"Dropped to {danger['hp']:.0%} health" +
                        (f" ({top['who']}: {top['spell']} for {_fmt(top['amount'])})" if top else "")))
    if power and power[-1][1] < 0.1:
        improve.append((0.05, f"Ended on {power[-1][1]:.0%} power"))
    improve.sort(key=lambda v: -v[0])

    return {
        "id": f"{start:%Y%m%d%H%M%S%f}",           # the start: a combat that carries on keeps it
        "start": start.isoformat(), "end": end.isoformat(), "duration": dur,
        "me": me, "me_name": clean_name(me_name) if me_name else "",
        "kind": kind, "zone": f.zone, "target": target, "more": max(0, extra), "result": result,
        "damage": damage, "dps": dps, "healing": heal, "overheal": overheal, "taken": total_taken,
        "lowest_hp": min((p for _, p in hp), default=None),
        "potential": potential, "efficiency": damage / potential if potential else 1.0,
        "healing_role": healing_role,
        "best_before": best,
        "good": good[:4], "improve": [text for _, text in improve][:5],
        "danger": danger, "abilities": abilities, "cooldowns": cd_rows, "auto": auto,
        "idle": {"total": idle_res + idle_out + idle_moving, "with_resource": idle_res,
                 "out_of_resource": idle_out, "moving": idle_moving, "lost": idle_lost},
        "group": group,
        "buffs": buffs, "failed": failed,
        "resource": {"start": f.start_power, "end": power[-1][1] if power else None,
                     "start_hp": f.start_hp},
        "pull": {"since_last": f.since_last, "buffs": f.buffs_at_pull},
        "interrupts": interrupts, "dispels": dispels,
    }


def learn_cooldowns(f: FightData, me: str, cooldowns: dict[int, float]) -> bool:
    """update the shortest gap seen between two casts of each of your spells; True if anything changed"""
    last: dict[int, datetime] = {}
    changed = False
    for e in f.events:
        if e.event == "SPELL_CAST_SUCCESS" and e.src == me and e.spell_id and e.spell_id not in AUTO:
            if e.spell_id in last:
                gap = (e.ts - last[e.spell_id]).total_seconds()
                if gap > 0.5 and gap < cooldowns.get(e.spell_id, 1e9):
                    cooldowns[e.spell_id] = round(gap, 2)
                    changed = True
            last[e.spell_id] = e.ts
    return changed
