"""Reads WoWCombatLog-*.txt.

Each line: "11/16/2026 20:57:09.225-8  EVENT,field,field,...". The time is local (the "-8" is
the PC's UTC offset in hours), so it's kept as a naive local datetime, the same as the addon's
anchors.

Standard events have 8 base fields (source GUID, name, flags, raid flags, then the same for the
destination), then prefix fields (SPELL_* has spell id, name, school), then - with Advanced
Combat Logging on - a block about one unit, then suffix fields (amount, ...).

This client (COMBAT_LOG_VERSION 22, project 18) writes a 19-field advanced block:
    guid, ownerGUID, hp, maxHP, attackPower, spellPower, armor, absorb, ?, ?,
    powerType, power, maxPower, powerCost, x, y, uiMapID, facing, level (a player's: the average item level)
The block says which unit it describes (its first field) - sometimes the source, sometimes the
destination - so always check `info.guid`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterator

_HEAD = re.compile(r"(\d+)/(\d+)/(\d+) (\d+):(\d+):(\d+)\.(\d+)(?:[-+]\d+)?\s\s(\w+),?(.*)")
_GUID = re.compile(r"^(?:Player|Creature|Pet|Vehicle|GameObject|Vignette|Item)-|^0000000000000000$")

ADV_LEN = 19

# raid target icons, by their bit in a unit's raid flags
MARKERS = {0x01: "Star", 0x02: "Circle", 0x04: "Diamond", 0x08: "Triangle",
           0x10: "Moon", 0x20: "Square", 0x40: "Cross", 0x80: "Skull"}

# unit flags
REACTION_HOSTILE = 0x40
REACTION_FRIENDLY = 0x10
TYPE_PLAYER, TYPE_NPC, TYPE_PET, TYPE_GUARDIAN = 0x400, 0x800, 0x1000, 0x2000
AFFILIATION_OUTSIDER = 0x8


def marker(bits: int) -> str | None:
    return MARKERS.get(bits & 0xFF)


def is_enemy(guid: str, flags: int) -> bool:
    """a hostile NPC that isn't anyone's pet or guardian"""
    return (guid.startswith(("Creature-", "Vehicle-")) and bool(flags & REACTION_HOSTILE)
            and not flags & (TYPE_PET | TYPE_GUARDIAN))


def npc_id(guid: str) -> int | None:
    parts = guid.split("-")
    try:
        return int(parts[5]) if len(parts) > 5 else None
    except ValueError:
        return None

# events that aren't in the source/destination shape
SPECIAL = {
    "COMBAT_LOG_VERSION", "ZONE_CHANGE", "MAP_CHANGE", "ENCOUNTER_START", "ENCOUNTER_END",
    "COMBATANT_INFO", "CHALLENGE_MODE_START", "CHALLENGE_MODE_END", "WORLD_MARKER_PLACED",
    "WORLD_MARKER_REMOVED", "EMOTE", "ARENA_MATCH_START", "ARENA_MATCH_END",
}


@dataclass(slots=True)
class UnitInfo:
    guid: str
    hp: int
    max_hp: int
    power_type: int
    power: int
    max_power: int
    x: float
    y: float
    map_id: int
    facing: float
    level: int
    cost: int = 0          # power the cast cost (on SPELL_CAST_SUCCESS)
    absorb: int = 0        # damage absorbing shields on the unit
    ap: int = 0            # the log's own attack power: another number than the game's (see live/worth.py)
    sp: int = 0            # the game's spell power
    armor: int = 0

    @property
    def hp_pct(self) -> float:
        return min(1.0, self.hp / self.max_hp) if self.max_hp else 1.0   # buffs can push it past max


@dataclass(slots=True)
class Event:
    ts: datetime
    event: str
    src: str = ""
    src_name: str = ""
    src_flags: int = 0
    dst: str = ""
    dst_name: str = ""
    dst_flags: int = 0
    src_raid: int = 0        # raid target icon bits (see MARKERS)
    dst_raid: int = 0
    spell_id: int | None = None
    spell_name: str = ""
    info: UnitInfo | None = None
    amount: int = 0
    base: int = 0            # _DAMAGE: before armor, a crit or a glancing blow
    overkill: int = 0
    overheal: int = 0
    absorbed: int = 0
    crit: bool = False
    resisted: int = 0        # _DAMAGE: the part resisted / blocked
    blocked: int = 0
    glancing: bool = False   # _DAMAGE (melee): a glancing or crushing blow
    crushing: bool = False
    miss_type: str = ""      # _MISSED: MISS, DODGE, PARRY, ABSORB, ...
    missed_amount: int = 0   # _MISSED: the amount blocked, absorbed or resisted, if any
    extra_count: int = 0     # SPELL_EXTRA_ATTACKS: how many extra swings
    # _MISSED only: this client marks off-hand on misses but not on _DAMAGE lines, so swings stay one stream
    off_hand: bool = False
    reason: str = ""         # SPELL_CAST_FAILED: "Not yet recovered", ...
    extra_spell_id: int | None = None  # _INTERRUPT, _DISPEL: the spell it hit
    raw: list[str] | None = None       # special events: their fields
    aura_type: str = ""                # SPELL_AURA_APPLIED: BUFF or DEBUFF
    feign: bool | None = None          # UNIT_DIED: the log's unconscious flag, set on a Feign Death; None without it


def split_fields(s: str) -> list[str]:
    """Commas split fields, except inside "quotes" and (), [] (COMBATANT_INFO nests them)."""
    out, cur, depth, quoted = [], [], 0, False
    for c in s:
        if quoted:
            if c == '"':
                quoted = False
            else:
                cur.append(c)
        elif c == '"':
            quoted = True
        elif c in "([":
            depth += 1
            cur.append(c)
        elif c in ")]":
            depth -= 1
            cur.append(c)
        elif c == "," and depth == 0:
            out.append("".join(cur))
            cur = []
        else:
            cur.append(c)
    out.append("".join(cur))
    return out


def _int(s: str) -> int:
    try:
        return int(s, 16) if s.startswith("0x") else int(float(s))
    except ValueError:
        return 0


def _prefix_len(ev: str) -> int:
    if ev.startswith("SWING_"):
        return 0
    if ev.startswith(("SPELL_", "RANGE_", "DAMAGE_SHIELD", "DAMAGE_SPLIT")):
        return 3
    return 0


def parse_time(m: re.Match) -> datetime:
    mo, d, y, h, mi, s, frac = (m.group(i) for i in range(1, 8))
    return datetime(int(y), int(mo), int(d), int(h), int(mi), int(s), int(frac.ljust(6, "0")[:6]))


def parse_line(line: str) -> Event | None:
    m = _HEAD.match(line)
    if not m:
        return None
    ts, ev = parse_time(m), m.group(8)
    f = split_fields(m.group(9))
    if ev in SPECIAL or len(f) < 8:
        return Event(ts, ev, raw=f)
    e = Event(ts, ev, f[0], f[1], _int(f[2]), f[4], f[5], _int(f[6]), _int(f[3]) & 0xFF, _int(f[7]) & 0xFF)
    p = 8
    n = _prefix_len(ev)
    if n == 3 and len(f) >= 11:
        e.spell_id, e.spell_name = _int(f[8]), f[9]
    p += n
    if len(f) >= p + ADV_LEN and _GUID.match(f[p]) and _GUID.match(f[p + 1]):
        try:
            e.info = UnitInfo(f[p], _int(f[p + 2]), _int(f[p + 3]), _int(f[p + 10]), _int(f[p + 11]),
                              _int(f[p + 12]), float(f[p + 14]), float(f[p + 15]), _int(f[p + 16]),
                              float(f[p + 17]), _int(f[p + 18]), _int(f[p + 13]), _int(f[p + 7]),
                              _int(f[p + 4]), _int(f[p + 5]), _int(f[p + 6]))
            p += ADV_LEN
        except ValueError:
            e.info = None
    if ev.startswith("ENVIRONMENTAL_") and len(f) > p:      # its type ("Falling", "Lava") comes after the block
        e.spell_name, p = f[p], p + 1
    s = f[p:]
    if ev.endswith(("_DAMAGE", "_DAMAGE_LANDED")) and len(s) >= 8:
        # amount, base amount, overkill, school, resisted, blocked, absorbed, critical, glancing, crushing
        e.amount, e.base, e.overkill, e.absorbed, e.crit = _int(s[0]), _int(s[1]), _int(s[2]), _int(s[6]), s[7] == "1"
        e.resisted, e.blocked = _int(s[4]), _int(s[5])
        e.glancing, e.crushing = len(s) > 9 and s[8] == "1", len(s) > 9 and s[9] == "1"
    elif ev.endswith("_HEAL") and len(s) >= 5:
        # amount, base amount, overhealing, absorbed, critical
        e.amount, e.overheal, e.absorbed, e.crit = _int(s[0]), _int(s[2]), _int(s[3]), s[4] == "1"
    elif ev.endswith("_MISSED") and s:
        # miss type, is off-hand, amount missed (BLOCK, ABSORB, RESIST), critical
        e.miss_type, e.off_hand = s[0], len(s) > 1 and s[1] == "1"
        e.missed_amount = _int(s[2]) if len(s) > 2 else 0
    elif ev == "SPELL_EXTRA_ATTACKS" and s:
        e.extra_count = _int(s[0])
    elif ev == "SPELL_CAST_FAILED" and s:
        e.reason = s[0]
    elif ev.endswith(("_INTERRUPT", "_DISPEL", "_STOLEN", "_AURA_BROKEN_SPELL")) and s:
        e.extra_spell_id = _int(s[0])
    elif ev == "SPELL_AURA_APPLIED" and s:
        e.aura_type = s[0]
    elif ev == "UNIT_DIED" and s:
        e.feign = s[-1] == "1"
    return e


def find_logs(logs_dir: Path) -> list[Path]:
    """Combat log files, oldest first."""
    return sorted(logs_dir.glob("WoWCombatLog*.txt"), key=lambda p: p.stat().st_mtime)


def log_span(path: Path) -> tuple[datetime, datetime] | None:
    """First and last timestamps in a log, read from its ends."""
    first = last = None
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = _HEAD.match(line)
            if m:
                first = parse_time(m)
                break
        if first is None:
            return None
        fh.seek(0, 2)
        size = fh.tell()
        fh.seek(max(0, size - 65536))
        for line in fh.read().splitlines():
            m = _HEAD.match(line)
            if m:
                last = parse_time(m)
    return first, last or first


def read_events(path: Path, start: datetime | None = None, end: datetime | None = None,
                margin: float = 5.0) -> Iterator[Event]:
    """Events between start and end (plus a margin either side). Lines outside are skipped
    after reading only their time, so a long log is quick to search."""
    lo = start - timedelta(seconds=margin) if start else None
    hi = end + timedelta(seconds=margin) if end else None
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if lo or hi:
                m = _HEAD.match(line)
                if not m:
                    continue
                ts = parse_time(m)
                if (lo and ts < lo) or (hi and ts > hi):
                    if hi and ts > hi:
                        break
                    continue
            e = parse_line(line)
            if e:
                yield e
