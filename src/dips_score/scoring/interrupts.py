"""Interrupts and dispels: an enemy starts a cast, or puts a harmful aura on someone in the group,
and you stop it or take it off - or you don't. All from the basic combat log.

Interrupts. A chance is an enemy starting a cast (SPELL_CAST_START) during a fight. Its outcome is
the first of these for that enemy before it starts its next cast:
    your interrupt (yours or your pet's)   answered: seconds from the cast start to your interrupt
    someone else's interrupt               left out (it was stopped, just not by you)
    the enemy died                         left out
    the cast completed (SPELL_CAST_SUCCESS of that spell)   a miss
If none of these comes (stunned, feared, out of sight), it's left out too.

The log doesn't say which spells can be interrupted, so that's learned from the run: a spell counts
only if someone interrupted it at least once in this run. So a spell nobody ever kicked is never
held against you. And you're only judged at all if you interrupted at least once this run: the log
can't tell whether your class, level and talents give you an interrupt (group.py CAN_UTILITY mixes
in dispels, so it can't say either).

Dispels, the same shape. A chance is an enemy putting a harmful aura (SPELL_AURA_APPLIED, DEBUFF)
on a group member, of an aura someone dispelled from a group member at least once this run. Your
SPELL_DISPEL of it from that player within DISPEL_CAP answers it; someone else's dispel, the aura
ending by itself (or with them dying), or the fight ending before the cap leaves it out; anything
else is a miss. Only judged if you dispelled someone at least once this run.
"""
from __future__ import annotations

import statistics
from bisect import bisect_left
from dataclasses import dataclass, field

from ..model.run import RunData
from ..sources.combatlog import is_enemy
from .healer import _is_group
from .metrics import Interval, union

DISPEL_CAP = 8.0


@dataclass
class Chance:
    who: str              # the enemy casting (interrupts), or the player with the aura (dispels)
    name: str             # theirs
    spell: str            # the cast, or the aura
    start: float
    response: float | None = None   # seconds until you stopped it
    left_out: bool = False          # someone else stopped it, or it ended some other way

    @property
    def missed(self) -> bool:
        return self.response is None and not self.left_out


@dataclass
class InterruptMetrics:
    chances: list[Chance] = field(default_factory=list)
    used: bool = False                       # you interrupted at least once this run (else not judged)
    dispel: InterruptMetrics | None = None   # the same for dispels; None when you dispelled nobody this run

    @property
    def judged(self) -> list[Chance]:
        return [x for x in self.chances if not x.left_out]

    @property
    def median_response(self) -> float | None:
        """of the ones you got (the ones you didn't count in missed_share)"""
        r = [x.response for x in self.chances if x.response is not None]
        return statistics.median(r) if r else None

    @property
    def missed(self) -> int:
        return sum(1 for x in self.chances if x.missed)

    @property
    def missed_share(self) -> float:
        j = self.judged
        return self.missed / len(j) if j else 0.0


@dataclass
class InterruptBase:
    """Everything measure_interrupts needs from the whole run, gathered in one pass."""
    casts: list[tuple[float, str, str, int, str, int]] = field(default_factory=list)  # t, enemy, name, spell id, spell, i
    after: dict[str, list[tuple[float, str, int | None]]] = field(default_factory=dict)  # enemy -> (t, what, spell id)
    kickable: set[int] = field(default_factory=set)   # spell ids someone interrupted
    kicked: bool = False                               # you did
    debuffs: list[tuple[float, str, str, int, str]] = field(default_factory=list)   # t, player, name, aura id, aura
    cleared: dict[tuple[str, int], list[tuple[float, str]]] = field(default_factory=dict)  # (player, aura) -> (t, how)
    cleansable: set[int] = field(default_factory=set)  # aura ids someone dispelled from a group member
    dispelled: bool = False                            # you did


def interrupt_base(rd: RunData, mine: set[str]) -> InterruptBase:
    """mine: your GUID and your pets'"""
    from ..model.roster import clean_name
    b = InterruptBase()
    seen: set[tuple[str, int]] = set()   # debuffs put on the group so far
    for e in rd.events:
        ev = e.event
        t = rd.rel(e.ts)
        if ev == "SPELL_CAST_START" and is_enemy(e.src, e.src_flags):
            seq = b.after.setdefault(e.src, [])
            b.casts.append((t, e.src, e.src_name, e.spell_id, e.spell_name, len(seq)))
            seq.append((t, "start", e.spell_id))
        elif ev == "SPELL_CAST_SUCCESS" and e.src in b.after:
            b.after[e.src].append((t, "done", e.spell_id))
        elif ev == "UNIT_DIED" and e.dst in b.after:
            b.after[e.dst].append((t, "died", None))
        elif ev == "SPELL_INTERRUPT" and is_enemy(e.dst, e.dst_flags):
            me = e.src in mine
            b.kickable.add(e.extra_spell_id)
            b.kicked |= me
            if e.dst in b.after:
                b.after[e.dst].append((t, "mine" if me else "other", None))
        elif ev == "SPELL_AURA_APPLIED" and e.aura_type == "DEBUFF" and is_enemy(e.src, e.src_flags) \
                and e.dst.startswith("Player-") and _is_group(e.dst_flags):
            b.debuffs.append((t, e.dst, clean_name(e.dst_name), e.spell_id, e.spell_name))
            seen.add((e.dst, e.spell_id))
        elif ev == "SPELL_DISPEL" and e.dst.startswith("Player-") and _is_group(e.dst_flags):
            me = e.src in mine
            b.cleansable.add(e.extra_spell_id)
            b.dispelled |= me
            b.cleared.setdefault((e.dst, e.extra_spell_id), []).append((t, "mine" if me else "other"))
        elif ev == "SPELL_AURA_REMOVED" and (e.dst, e.spell_id) in seen:
            b.cleared.setdefault((e.dst, e.spell_id), []).append((t, "removed"))
    return b


def measure_interrupts(rd: RunData, windows: list[Interval] | None = None,
                       base: InterruptBase | None = None) -> InterruptMetrics:
    if windows is None:
        windows = [(f.start, f.end) for f in rd.fights]
    windows = union(windows)
    b = base or interrupt_base(rd, {rd.player_guid})

    def end_of(t: float) -> float | None:
        return next((e for c, e in windows if c <= t <= e), None)

    im = InterruptMetrics(used=b.kicked)
    for t, enemy, name, sid, spell, i in b.casts:
        if sid not in b.kickable or end_of(t) is None:
            continue
        x = Chance(enemy, name, spell, t, left_out=True)   # until something ends the cast
        seq = b.after[enemy]
        for k in range(i + 1, len(seq)):
            t2, what, sid2 = seq[k]
            if what == "done" and sid2 != sid:
                continue          # an instant of something else: not this cast's end
            if what == "mine":
                x.response, x.left_out = t2 - t, False
            elif what == "done":
                x.left_out = False   # it went off: a miss
            break
        im.chances.append(x)

    if b.dispelled:
        d = im.dispel = InterruptMetrics(used=True)
        for t, who, name, aid, aura in b.debuffs:
            end = end_of(t)
            if aid not in b.cleansable or end is None:
                continue
            x = Chance(who, name, aura, t)
            seq = b.cleared.get((who, aid), [])
            k = bisect_left(seq, (t,))
            if k < len(seq) and seq[k][0] - t <= DISPEL_CAP:
                if seq[k][1] == "mine":
                    x.response = seq[k][0] - t
                else:
                    x.left_out = True
            else:
                x.left_out = end < t + DISPEL_CAP
            d.chances.append(x)
    return im
