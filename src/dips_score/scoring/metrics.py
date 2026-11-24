"""What happened in a run (or one fight), measured. Only measuring here; score.py judges it.

Everything is measured over combat time: the windows the player was in combat (the addon's R
lines), so walking between pulls doesn't count against you.

Busy time is casting, channeling, the GCD (1.0 s for energy users, else 1.5 s), and auto-attack running:
melee swings and ranged shots (Auto Shot, wand Shoot; each keeps you busy until the next one, at most one
swing or shot). Swinging or shooting with no ability is busy, not idle ("swinging_time" says how much: the
auto-attack inside gaps of IDLE_GAP+ between abilities, as the live fight counts it).
A next-swing ability (NEXT_SWING: Heroic Strike...) takes the place of the swing it replaces, so that swing
is not lost. Shots lost are measured like swings lost, but a gap while moving doesn't count, and a shot
clipped by a cast (a hard cast; for a wand, any cast, since casting stops the wand) is counted apart, and
a gap with no enemy alive (each enemy from its first to its last event in the log) doesn't count either. For rage and
energy users (Advanced Combat Logging), time you couldn't afford your cheapest ability is
"starved": not busy, but not held against you either. The other side is "capped": time your rage
or energy sat at its maximum (more coming in was lost), counted from the same readings.
"""
from __future__ import annotations

import statistics
from collections import Counter
from dataclasses import dataclass, field

from ..model.run import AUTO_REPEAT, RunData, TLine
from ..sources.combatlog import is_enemy

GCD = 1.5               # seconds; this client's global cooldown
ENERGY_GCD = 1.0        # energy users (rogues, cat druids) have a shorter one
RAGE, ENERGY = 1, 3     # UnitInfo.power_type (0 is mana)
POWER_HOLD = 5.0        # a power reading stands until the next one, at most this long
ENERGY_HOLD = 2.0       # ...but energy refills quickly, so an energy reading stands at most this long
SWING_SLACK = 0.6       # a swing gap counts a swing lost once it's longer than 1.6 swings
AUTO_GAP = 2.0          # a wand shot keeps you "busy" this long (or until the next shot)
IDLE_GAP = 2.5          # gaps in activity at least this long are listed
MOVE_INTERRUPT_S = 0.6  # an interrupted cast this soon after you started moving was cut by moving
SPAM_WINDOW = 1.0       # the same button this many times inside this many seconds is a burst
SPAM_COUNT = 3
LOW_HP = 0.35
WAND = 5019             # Shoot (wands): any cast stops it, so any cast clips a shot
# next-swing abilities, by name: they replace your next swing (SPELL_DAMAGE instead of SWING_DAMAGE), so
# their cast fills that swing's slot in the lost-swing count
NEXT_SWING = frozenset({"Heroic Strike", "Cleave", "Raptor Strike", "Maul"})

Interval = tuple[float, float]


# ----------------------------------------------------------------------------- intervals
def union(iv: list[Interval]) -> list[Interval]:
    out: list[Interval] = []
    for a, b in sorted(iv):
        if b <= a:
            continue
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def clip(iv: list[Interval], windows: list[Interval]) -> list[Interval]:
    out = []
    for a, b in union(iv):
        for wa, wb in windows:
            lo, hi = max(a, wa), min(b, wb)
            if hi > lo:
                out.append((lo, hi))
    return union(out)


def total(iv: list[Interval]) -> float:
    return sum(b - a for a, b in iv)


def gaps(iv: list[Interval], windows: list[Interval], min_len: float) -> list[Interval]:
    """Parts of the windows not covered by iv, at least min_len long."""
    out = []
    busy = union(iv)
    for wa, wb in windows:
        cur = wa
        for a, b in busy:
            if b <= wa or a >= wb:
                continue
            if a - cur >= min_len:
                out.append((cur, a))
            cur = max(cur, b)
        if wb - cur >= min_len:
            out.append((cur, wb))
    return out


def inside(t: float, windows: list[Interval]) -> bool:
    return any(a <= t <= b for a, b in windows)


# ----------------------------------------------------------------------------- the pieces
def swing_stats(swings: list[float], casting: list[Interval],
                windows: list[Interval] | None = None, excused: list[Interval] = ()) -> tuple[float, int, int]:
    """(swing speed, swings lost while casting, swings lost otherwise) from your sorted melee swing
    (or shot) times. Speed is the median gap between swings; a gap of n speeds loses int(n - 0.6)
    swings, put down to casting when a hard cast (casting) overlaps it. With windows, only gaps inside
    one window count (the time between two fights isn't a lost swing); time in `excused` (moving, no
    enemy alive) is taken off each gap first."""
    pairs = [(a, b) for a, b in zip(swings, swings[1:])
             if windows is None or any(wa <= a and b <= wb for wa, wb in windows)]
    speed = statistics.median([b - a for a, b in pairs]) if pairs else 0.0
    lost_casting = lost_other = 0
    for a, b in pairs:
        n_lost = int((b - a - total(clip(excused, [(a, b)]))) / speed - SWING_SLACK) if speed else 0
        if n_lost > 0:
            if any(s <= b and e >= a for s, e in casting):
                lost_casting += n_lost
            else:
                lost_other += n_lost
    return speed, lost_casting, lost_other


def auto_running(times: list[float], speed: float) -> list[Interval]:
    """when auto-attack was running: each swing or shot (sorted times) until the next, at most one speed"""
    ends = times[1:] + [times[-1] + speed] if times else []
    return [(t, t + min(speed, max(0.0, nxt - t))) for t, nxt in zip(times, ends)]


def hit_table() -> dict:
    """plain counts of auto attacks (swings or shots): landed, crits, glancing, crushing, blocked (a
    landed hit partly blocked), misses by type ("miss", "dodge", "parry", "block", "immune", ...),
    how many misses the log marked off-hand, and the damage the landed ones did"""
    return {"landed": 0, "crits": 0, "glancing": 0, "crushing": 0, "blocked": 0, "misses": {},
            "offhand_misses": 0, "damage": 0}


def count_hit(table: dict, e) -> None:
    """add one SWING_/RANGE_ DAMAGE or MISSED event to a hit_table()"""
    if e.event.endswith("_MISSED"):
        kind = e.miss_type.lower() or "?"
        table["misses"][kind] = table["misses"].get(kind, 0) + 1
        table["offhand_misses"] += e.off_hand
    else:
        table["landed"] += 1
        table["damage"] = table.get("damage", 0) + e.amount
        table["crits"] += e.crit
        table["glancing"] += e.glancing
        table["crushing"] += e.crushing
        table["blocked"] += e.blocked > 0


def busy_intervals(lines: list[TLine], gcd: float = GCD) -> tuple[list[Interval], list[Interval]]:
    """(busy, wasted): when you were casting, channeling, on the GCD or wanding; and the cast
    time thrown away by casts that got interrupted."""
    busy: list[Interval] = []
    wasted: list[Interval] = []
    casting: tuple[int | None, float] | None = None
    channel: float | None = None
    shots: list[float] = []
    seg = None
    for ln in lines:
        if ln.seg != seg:
            casting, channel, seg = None, None, ln.seg
        c = ln.code
        sid = ln.num(0)
        if c == "CB":
            casting = (sid, ln.t)
        elif c in ("CK", "CF", "CI") and casting and casting[0] == sid:
            start = casting[1]
            if c == "CK":
                busy.append((start, max(ln.t, start + gcd)))
            else:
                busy.append((start, ln.t))
                if c == "CI":
                    wasted.append((start, ln.t))
            casting = None
        elif c == "CK":
            if sid in AUTO_REPEAT:
                shots.append(ln.t)
            else:
                busy.append((ln.t, ln.t + gcd))  # an instant: the GCD
        elif c == "CC":
            channel = ln.t
            busy.append((ln.t, ln.t + gcd))
        elif c == "CE" and channel is not None:
            busy.append((channel, ln.t))
            channel = None
    for i, t in enumerate(shots):
        nxt = shots[i + 1] if i + 1 < len(shots) else t + AUTO_GAP
        busy.append((t, t + min(AUTO_GAP, max(0.0, nxt - t))))
    return union(busy), wasted


def moving_intervals(lines: list[TLine], spans: list[Interval]) -> list[Interval]:
    out, start, seg = [], None, None
    for ln in lines:
        if ln.seg != seg:
            if start is not None and seg is not None:
                out.append((start, spans[seg][1]))
            start, seg = None, ln.seg
        if ln.code == "M":
            if ln.f(0) == "1" and start is None:
                start = ln.t
            elif ln.f(0) == "0" and start is not None:
                out.append((start, ln.t))
                start = None
    if start is not None and seg is not None:
        out.append((start, spans[seg][1]))
    return union(out)


# ----------------------------------------------------------------------------- metrics
@dataclass
class Metrics:
    combat_time: float = 0.0
    fights: int = 0
    # activity
    busy_time: float = 0.0
    idle_gaps: list[Interval] = field(default_factory=list)
    starved_time: float = 0.0  # not busy, and couldn't afford anything (rage/energy only)
    capped_time: float = 0.0   # power at its maximum, so income was being wasted (rage/energy only)
    swings: int = 0            # your melee swings (hits and misses)
    swings_lost: int = 0       # swings lost while not casting
    swing_speed: float = 0.0
    swinging_time: float | None = None  # auto-attack running (swings or shots) with no ability: busy, not idle
    shots: int = 0             # your ranged auto shots (Auto Shot, wand Shoot, Throw), hits and misses
    # None in analyses saved before shots were measured
    shots_lost: int | None = None      # lost while not casting, not moving
    shots_clipped: int | None = None   # lost to a cast
    shot_speed: float | None = None
    # hit tables (see hit_table); None in analyses saved before they were counted
    melee: dict | None = None          # your swings
    ranged: dict | None = None         # your Auto Shot / Shoot / Throw (RANGE_ events)
    swings_taken: dict | None = None   # enemies' swings at you
    extra_attacks: dict | None = None  # extra swings by the spell that gave them (Windfury, ...)
    hard_casts: int = 0        # casts with a cast bar (from the combat log)
    power_type: int | None = None   # 0 mana, 1 rage, 3 energy; None without Advanced Combat Logging
    # casting
    casts: int = 0             # successful casts (not wand shots)
    failed: int = 0            # presses the game refused (not wand toggles)
    fail_reasons: Counter = field(default_factory=Counter)
    interrupted: int = 0
    move_interrupts: int = 0   # of those, cut by starting to move
    wasted_cast_time: float = 0.0
    # movement
    moving_time: float = 0.0
    # input
    presses: int = 0
    by_key: int = 0
    by_click: int = 0
    spam_bursts: int = 0
    hold_ms: list[float] = field(default_factory=list)
    first_press_delays: list[float] = field(default_factory=list)
    # survival
    deaths: int = 0
    lowest_hp: float | None = None
    low_hp_time: float = 0.0
    damage_taken: int = 0
    # output
    damage: int = 0
    healing: int = 0
    overheal: int = 0
    kills: int = 0
    has_log: bool = False
    has_advanced: bool = False

    @property
    def uptime(self) -> float:
        """busy, or starved (waiting for rage/energy isn't idling)"""
        return (self.busy_time + self.starved_time) / self.combat_time if self.combat_time else 0.0

    @property
    def per_min(self) -> float:
        """multiply a count by this for per-minute-of-combat"""
        return 60 / self.combat_time if self.combat_time else 0.0

    @property
    def fail_rate(self) -> float:
        n = self.casts + self.failed
        return self.failed / n if n else 0.0

    @property
    def presses_per_cast(self) -> float:
        return self.presses / self.casts if self.casts else 0.0

    @property
    def click_share(self) -> float:
        n = self.by_key + self.by_click
        return self.by_click / n if n else 0.0

    @property
    def moving_share(self) -> float:
        return self.moving_time / self.combat_time if self.combat_time else 0.0

    @property
    def dps(self) -> float:
        return self.damage / self.combat_time if self.combat_time else 0.0

    @property
    def hps(self) -> float:
        return self.healing / self.combat_time if self.combat_time else 0.0

    @property
    def overheal_share(self) -> float:
        n = self.healing + self.overheal
        return self.overheal / n if n else 0.0

    @property
    def median_first_press(self) -> float | None:
        return statistics.median(self.first_press_delays) if self.first_press_delays else None

    @property
    def median_hold_ms(self) -> float | None:
        return statistics.median(self.hold_ms) if self.hold_ms else None


def measure(rd: RunData, windows: list[Interval] | None = None) -> Metrics:
    """Metrics over the given windows (default: every fight in the run)."""
    if windows is None:
        windows = [(f.start, f.end) for f in rd.fights]
    windows = union(windows)
    m = Metrics(combat_time=total(windows), fights=len(windows), has_log=rd.has_combat_log,
                has_advanced=rd.has_advanced, melee=hit_table(), ranged=hit_table(),
                swings_taken=hit_table(), extra_attacks={})
    lines = rd.lines
    # only the stretch of the log these windows cover (a fight is a small slice of a long run)
    events = rd.events_between(windows[0][0] - 1, windows[-1][1] + 1) if windows else []

    me = rd.player_guid
    # your power type: the one most of your readings carry (a druid's forms: the main one wins)
    if m.has_advanced:
        types = Counter(e.info.power_type for e in rd.events if e.info and e.info.guid == me)
        m.power_type = types.most_common(1)[0][0] if types else None
    busy, wasted = busy_intervals(lines, ENERGY_GCD if m.power_type == ENERGY else GCD)
    m.wasted_cast_time = total(clip(wasted, windows))
    moving = moving_intervals(lines, rd.segment_spans)
    m.moving_time = total(clip(moving, windows))

    # failure reasons from the combat log: SPELL_CAST_FAILED by you, same spell, close in time
    fails_log: dict[int, list[tuple[float, str]]] = {}
    for e in events:
        if e.event == "SPELL_CAST_FAILED" and rd.mine(e) and e.spell_id:
            fails_log.setdefault(e.spell_id, []).append((rd.rel(e.ts), e.reason))

    last_move_start = -1e9
    recent: dict[str, list[float]] = {}
    down: dict[str, float] = {}
    for ln in lines:
        c, t = ln.code, ln.t
        if c == "M" and ln.f(0) == "1":
            last_move_start = t
        if c == "KD":
            down[ln.f(0) + ":" + ln.f(1)] = t
        elif c == "KU":
            k = ln.f(0) + ":" + ln.f(1)
            if k in down and inside(down[k], windows):
                m.hold_ms.append((t - down.pop(k)) * 1000)
        if not inside(t, windows):
            continue
        sid = ln.num(0)
        if c == "CK" and sid not in AUTO_REPEAT:
            m.casts += 1
        elif c == "CF" and sid not in AUTO_REPEAT:
            m.failed += 1
            reason = "unknown"
            for ft, r in fails_log.get(sid or -1, []):
                if abs(ft - t) < 0.3:
                    reason = r or "unknown"
                    break
            m.fail_reasons[reason] += 1
        elif c == "CI":
            m.interrupted += 1
            if 0 <= t - last_move_start <= MOVE_INTERRUPT_S or inside(t, moving):
                m.move_interrupts += 1
        elif c == "A":
            if ln.f(1) == "spell" and ln.num(2) in AUTO_REPEAT:
                continue  # turning the wand on isn't a press we judge
            m.presses += 1
            src = ln.fields[-1] if ln.fields else "?"
            if src == "K":
                m.by_key += 1
            elif src == "C":
                m.by_click += 1
            slot = ln.f(0)
            r = [x for x in recent.get(slot, []) if t - x <= SPAM_WINDOW] + [t]
            if len(r) == SPAM_COUNT:
                m.spam_bursts += 1
            recent[slot] = r
        elif c == "D":
            m.deaths += 1

    # how fast you got going: first press (or cast sent) after each fight started
    for a, b in windows:
        first = next((ln.t for ln in lines if a <= ln.t <= b and ln.code in ("A", "CS")), None)
        if first is not None:
            m.first_press_delays.append(first - a)

    # the combat log: what it did
    hp: list[tuple[float, float]] = []
    power: list[tuple[float, int]] = []
    full: list[bool] = []             # for each power reading: at its maximum
    swings: list[float] = []
    slots: list[float] = []           # next-swing ability casts: each takes a swing's place
    shots: list[float] = []
    shot_ids: Counter = Counter()
    casting: list[Interval] = []      # your hard casts: cast start to cast success
    bars: list[Interval] = []         # every cast (not auto): its cast time or GCD
    starts: dict[int, float] = {}
    alive: dict[str, list[float]] = {}    # enemy guid -> [first, last] event time
    for e in events:
        t = rd.rel(e.ts)
        if e.info and e.info.guid == me and e.info.power_type == m.power_type:
            power.append((t, e.info.power))   # readings just before a window still hold into it
            full.append(e.info.max_power > 0 and e.info.power >= e.info.max_power)
        if not inside(t, windows):
            continue
        ev = e.event
        for g, fl in ((e.src, e.src_flags), (e.dst, e.dst_flags)):
            if is_enemy(g, fl):
                span = alive.setdefault(g, [t, t])
                span[0], span[1] = min(span[0], t), max(span[1], t)
        if e.info and e.info.guid == rd.player_guid and e.info.max_hp:
            hp.append((t, e.info.hp_pct))
        if ev in ("SWING_DAMAGE", "SWING_MISSED") and e.src == me:
            swings.append(t)
            if is_enemy(e.dst, e.dst_flags):      # the hit table: enemies only, as the live summary keeps it
                count_hit(m.melee, e)
        elif ev in ("RANGE_DAMAGE", "RANGE_MISSED") and e.src == me:
            if is_enemy(e.dst, e.dst_flags):
                count_hit(m.ranged, e)
            shots.append(t)
            shot_ids[e.spell_id] += 1
        elif ev == "SPELL_EXTRA_ATTACKS" and e.src == me:
            m.extra_attacks[e.spell_name] = m.extra_attacks.get(e.spell_name, 0) + e.extra_count
        elif ev == "SPELL_CAST_START" and rd.mine(e):
            starts[e.spell_id] = t
        elif ev == "SPELL_CAST_SUCCESS" and rd.mine(e):
            began = starts.pop(e.spell_id, None)
            if began is not None and t - began < 10 and e.spell_id not in AUTO_REPEAT:
                casting.append((began, t))     # (the log gives wand Shoot a cast start too: not a hard cast)
            if e.src == me and e.spell_id not in AUTO_REPEAT:
                a = began if began is not None and t - began < 10 else t
                bars.append((a, max(t, a + GCD)))
            if e.src == me and e.spell_name in NEXT_SWING:
                slots.append(t)
        if ev in ("SWING_DAMAGE", "SWING_MISSED") and rd.to_me(e) and e.src != me:
            count_hit(m.swings_taken, e)
        if ev.endswith("_DAMAGE") and not ev.endswith("_LANDED"):
            if rd.mine(e):
                m.damage += e.amount
            if rd.to_me(e):
                m.damage_taken += e.amount
        elif ev.endswith("_HEAL") and rd.mine(e):
            m.healing += max(0, e.amount - e.overheal)
            m.overheal += e.overheal
        elif ev == "PARTY_KILL" and rd.mine(e):
            m.kills += 1
    if hp:
        m.lowest_hp = min(p for _, p in hp)
        for (t1, p1), (t2, _) in zip(hp, hp[1:]):
            if p1 < LOW_HP:
                m.low_hp_time += min(t2 - t1, 5.0)

    # auto-attack: each swing or shot keeps you busy until the next one, at most one swing or shot
    slots = sorted(swings + slots)
    m.swing_speed, _, m.swings_lost = swing_stats(slots, casting, windows)
    m.swings, m.hard_casts, m.shots = len(swings), len(casting), len(shots)
    wand = shot_ids.most_common(1)[0][0] == WAND if shot_ids else False
    no_enemy = gaps(list(map(tuple, alive.values())), windows, 0.0)
    m.shot_speed, m.shots_clipped, m.shots_lost = swing_stats(shots, bars if wand else casting, windows,
                                                              moving + no_enemy)
    running = auto_running(slots, m.swing_speed) + auto_running(shots, m.shot_speed)
    # ability time: the add-on's busy time less its wand / Auto Shot lines
    ability_busy, _ = busy_intervals([ln for ln in lines if not (ln.code in ("CB", "CK", "CF", "CI", "CC", "CE")
                                                                  and ln.num(0) in AUTO_REPEAT)],
                                     ENERGY_GCD if m.power_type == ENERGY else GCD)
    busy = union(busy + running)
    # as the live fight counts it: auto-attack inside the gaps of 2.5 s+ between abilities
    m.swinging_time = total(clip(busy, gaps(ability_busy, windows, IDLE_GAP)))

    # starved (rage/energy): your power below your cheapest ability's cost
    starved: list[Interval] = []
    capped: list[Interval] = []
    if m.power_type in (RAGE, ENERGY):
        cheapest = min((e.info.cost for e in rd.events if e.event == "SPELL_CAST_SUCCESS" and rd.mine(e)
                        and e.info and e.info.guid == me and e.info.power_type == m.power_type and e.info.cost),
                       default=0)
        hold = ENERGY_HOLD if m.power_type == ENERGY else POWER_HOLD
        for i, (t, p) in enumerate(power):
            if cheapest and p < cheapest:
                nxt = power[i + 1][0] if i + 1 < len(power) else t + hold
                starved.append((t, min(nxt, t + hold)))
            elif full[i]:   # (a reading under the cheapest cost isn't at max, so the two never overlap)
                nxt = power[i + 1][0] if i + 1 < len(power) else t + hold
                capped.append((t, min(nxt, t + hold)))
    m.capped_time = total(clip(capped, windows))
    m.busy_time = total(clip(busy, windows))
    m.starved_time = total(clip(busy + starved, windows)) - m.busy_time
    m.idle_gaps = gaps(busy + starved, windows, IDLE_GAP)
    return m
