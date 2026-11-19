"""Telling fights apart in the combat log, as it's written: one fight per whole combat.

Who you are: the log marks your own character (a player with "mine" affiliation). Your pets count as you.

A fight starts with the first hostile event between your group (you, your pets, your party) and an enemy
(a hostile NPC, or a hostile player for PvP). It ends, counting in the log's own time, when
    every enemy engaged has died and QUIET_DEAD seconds pass without fighting, or
    QUIET_ALIVE seconds pass without fighting while an enemy is still alive (it ran, reset, or you did);
or, counting in real time (the game writes the log in batches, so its clock can stall), when nothing new
has come in for WALL_DEAD seconds and every enemy engaged has died, or for WALL_QUIET seconds if one is
still alive.

A closed fight is opened again - the same combat, carried on - when
    a new enemy joins within CHAIN seconds of it ending (the next one was already on its way), or
    fighting resumes with one of its enemies that hadn't died, within RESUME seconds, or
    it was closed on the real-time rule and the log shows the fighting never really stopped.
It's then handed out again when it ends, with the same start, so its card and saved summary are updated
instead of a second one being made.

Between fights the tracker keeps what it needs for the next one: the buffs on you, your latest health and
power, the zone, when the last fight ended, and when you last cast each spell, by name (for cooldowns).
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import datetime

from ..sources.combatlog import Event, is_enemy, parse_line

QUIET_DEAD = 2.0
QUIET_ALIVE = 15.0
WALL_QUIET = 10.0
WALL_DEAD = 2.0
CHAIN = 4.0
RESUME = 60.0
NOT_HOSTILE = {"SPELL_AURA_REMOVED", "SPELL_AURA_REMOVED_DOSE", "UNIT_DIED", "PARTY_KILL", "UNIT_DESTROYED",
               "SPELL_SUMMON", "SPELL_CREATE", "SPELL_AURA_REFRESH", "SPELL_CAST_FAILED"}
RESTING = re.compile(r"Drink|Food|First Aid|Refreshment", re.I)
KEEP_AFTER = 3000      # events kept after a fight closes, in case it's opened again


def affiliation(flags: int) -> int:
    return flags & 0xF


def is_group(guid: str, flags: int) -> bool:
    return bool(guid) and affiliation(flags) in (0x1, 0x2, 0x4) and not is_enemy(guid, flags)


def is_foe(guid: str, flags: int) -> bool:
    return is_enemy(guid, flags) or (guid.startswith("Player-") and bool(flags & 0x40))


@dataclass
class Foe:
    guid: str
    name: str
    first: datetime
    died: datetime | None = None
    player: bool = False


@dataclass
class FightData:
    start: datetime
    events: list[Event] = field(default_factory=list)
    foes: dict[str, Foe] = field(default_factory=dict)
    last_hostile: datetime | None = None
    end: datetime | None = None
    # what was true when it started
    zone: str = ""
    difficulty: int = 0
    instance: int = 0                          # 0 in the open world
    buffs_at_pull: list[str] = field(default_factory=list)
    since_last: float | None = None            # seconds since the previous fight ended
    own_buffs_at_pull: list[str] = field(default_factory=list)   # the ones you cast on yourself
    rest: float = 0.0                          # seconds eating or drinking since the previous fight
    start_hp: float | None = None
    start_power: float | None = None
    boss: str | None = None
    cast_before: dict[str, datetime] = field(default_factory=dict)   # your last cast of each spell (by name) before it
    reopened: int = 0                          # times it was opened again (a carried-on combat)
    closed_by_wall: bool = False


class Tracker:
    def __init__(self):
        self.me: str | None = None
        self.me_name = ""
        self.fight: FightData | None = None
        self.closed: FightData | None = None        # the last fight, kept in case it carries on
        self.after: list[Event] = []                # events since it closed
        self.last_end: datetime | None = None
        self.buffs: dict[str, tuple[str, datetime]] = {}   # spell name -> (caster, since) on you
        self.hp: float | None = None
        self.power: float | None = None
        self.zone, self.difficulty, self.instance = "", 0, 0
        self.log_now: datetime | None = None
        self.allies: set[str] = set()      # players seen in your group: never foes (a mind-controlled
                                            # party member shows up as a hostile player)
        self.last_cast: dict[str, datetime] = {}
        self._rest = 0.0                   # seconds resting since the last fight opened
        self._resting: dict[str, datetime] = {}   # eating/drinking auras running now
        self._wall_hostile = 0.0

    # ------------------------------------------------------------------ feeding
    def feed_lines(self, lines: list[str]) -> list[FightData]:
        out = []
        for ln in lines:
            e = parse_line(ln)
            if e:
                done = self.feed(e)
                if done:
                    out.append(done)
        return out

    def feed(self, e: Event) -> FightData | None:
        """takes one event; returns a fight if this event shows it's over"""
        finished = None
        self.log_now = e.ts
        if self.fight and self._over(e.ts):        # the log's own clock says it's over
            finished = self._close()
        self._context(e)
        side = self._hostile(e)
        if side is not None:
            if self.fight is None:
                if not self._carry_on(e, side):
                    self._open(e.ts)
            f = self.fight
            foe_guid, foe_name, _ = side
            if foe_guid not in f.foes:
                f.foes[foe_guid] = Foe(foe_guid, foe_name, e.ts, player=foe_guid.startswith("Player-"))
            f.last_hostile = e.ts
            self._wall_hostile = time.monotonic()
        if self.fight is not None:
            self.fight.events.append(e)
            if e.event == "UNIT_DIED" and e.dst in self.fight.foes and self.fight.foes[e.dst].died is None:
                self.fight.foes[e.dst].died = e.ts
            if e.event == "ENCOUNTER_START" and e.raw and len(e.raw) > 1:
                self.fight.boss = e.raw[1]
        elif self.closed is not None:
            if len(self.after) < KEEP_AFTER:
                self.after.append(e)
            if e.event == "UNIT_DIED" and e.dst in self.closed.foes and self.closed.foes[e.dst].died is None:
                self.closed.foes[e.dst].died = e.ts
        if e.event == "SPELL_CAST_SUCCESS" and self.me and e.src == self.me and e.spell_name:
            # procs land here too; harmless, since a spell whose only damage is its procs never gets a row
            self.last_cast[e.spell_name] = e.ts
        return finished

    def tick(self) -> FightData | None:
        """call regularly: closes a fight once the log has gone quiet (in real time)"""
        if self.fight and self.log_now and self._over(self.log_now, time.monotonic()):
            f = self._close()
            f.closed_by_wall = True
            return f
        return None

    def flush(self) -> FightData | None:
        """end any open fight now (end of a replayed file)"""
        return self._close() if self.fight else None

    # ------------------------------------------------------------------ inside
    def _hostile(self, e: Event):
        """(foe guid, name, flags) if the event is fighting between your group and a foe"""
        if e.event in NOT_HOSTILE or e.raw is not None:
            return None
        if e.event == "SPELL_AURA_APPLIED" and not (is_foe(e.src, e.src_flags) or is_foe(e.dst, e.dst_flags)):
            return None
        if is_group(e.src, e.src_flags) and is_foe(e.dst, e.dst_flags) and e.dst not in self.allies:
            return e.dst, e.dst_name, e.dst_flags
        if is_foe(e.src, e.src_flags) and is_group(e.dst, e.dst_flags) and e.src not in self.allies:
            return e.src, e.src_name, e.src_flags
        return None

    def _over(self, log_now: datetime, wall_now: float | None = None) -> bool:
        """over by the log's clock; with wall_now, also when nothing has come in for a while in real time"""
        f = self.fight
        if f is None or f.last_hostile is None:
            return False
        quiet = (log_now - f.last_hostile).total_seconds()
        all_dead = all(fo.died is not None for fo in f.foes.values()) if f.foes else False
        if (all_dead and quiet >= QUIET_DEAD) or quiet >= QUIET_ALIVE:
            return True
        if wall_now is None:
            return False
        return wall_now - self._wall_hostile >= (WALL_DEAD if all_dead else WALL_QUIET)

    def _carry_on(self, e: Event, side) -> bool:
        """open the last fight again if this is the same combat carrying on"""
        last = self.closed
        if last is None or last.last_hostile is None:
            return False
        gap = (e.ts - last.last_hostile).total_seconds()
        foe = last.foes.get(side[0])
        same_foe = foe is not None and foe.died is None
        if not (gap <= CHAIN or (same_foe and gap <= RESUME) or (last.closed_by_wall and gap < QUIET_ALIVE)):
            return False
        last.events.extend(self.after)
        last.end, last.closed_by_wall = None, False
        last.reopened += 1
        self.fight, self.closed, self.after = last, None, []
        return True

    def _context(self, e: Event):
        if e.raw is None:
            for g, fl in ((e.src, e.src_flags), (e.dst, e.dst_flags)):
                if g.startswith("Player-") and is_group(g, fl):
                    self.allies.add(g)
        if e.raw is not None:
            if e.event == "ZONE_CHANGE" and len(e.raw) >= 3:
                self.zone = e.raw[1]
                try:
                    self.instance, self.difficulty = int(e.raw[0]), int(e.raw[2])
                except ValueError:
                    self.instance = self.difficulty = 0
            return
        if self.me is None and e.src.startswith("Player-") and affiliation(e.src_flags) == 0x1:
            self.me, self.me_name = e.src, e.src_name
        me = self.me
        if not me:
            return
        if e.info and e.info.guid == me:
            self.hp = e.info.hp_pct
            if e.info.max_power:
                self.power = e.info.power / e.info.max_power
        if e.dst == me:
            if e.event in ("SPELL_AURA_APPLIED", "SPELL_AURA_REFRESH") and e.spell_name:
                self.buffs.setdefault(e.spell_name, (e.src, e.ts))
                if e.event == "SPELL_AURA_APPLIED" and RESTING.search(e.spell_name):
                    self._resting.setdefault(e.spell_name, e.ts)
            elif e.event == "SPELL_AURA_REMOVED":
                self.buffs.pop(e.spell_name, None)
                since = self._resting.pop(e.spell_name, None)
                if since:
                    self._rest += (e.ts - since).total_seconds()
            elif e.event == "UNIT_DIED":
                self.buffs.clear()
                self._resting.clear()

    def _open(self, ts: datetime):
        self.closed, self.after = None, []
        rest = self._rest + sum((ts - t).total_seconds() for t in self._resting.values())
        self._rest = 0.0
        self._resting = {n: ts for n in self._resting}
        self.fight = FightData(
            ts, zone=self.zone, difficulty=self.difficulty, instance=self.instance,
            buffs_at_pull=sorted(self.buffs), rest=rest,
            own_buffs_at_pull=sorted(n for n, (who, _) in self.buffs.items() if who == self.me),
            since_last=(ts - self.last_end).total_seconds() if self.last_end else None,
            start_hp=self.hp, start_power=self.power, cast_before=dict(self.last_cast))

    def _close(self) -> FightData:
        f = self.fight
        f.end = f.last_hostile or self.log_now
        self.last_end = f.end
        self.closed, self.after = f, []
        self.fight = None
        return f
