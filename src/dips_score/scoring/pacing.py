"""Pacing: the share of pulls you went into safely and on time. Needs Advanced Combat Logging (your
health and mana are only in its advanced block). The thresholds are pace_* in score.TUNING.

    safe      your health at least pace_hp and, for mana users, mana at least pace_mana, from your last
              readings LEAD seconds before the pull starts (the same reading the Pulls page shows).
    on time   your first press (an A or CS line) within pace_late_s of your own combat beginning (or of
              the pull's start, if that's later). Not from the group's first touch: a pack pulled from range
              takes seconds to reach you, and on real runs that wait was most of what counted as late.
              A pull you started yourself (you pulled its first pack) is always on time.
A pull is judged only when there's a health reading above 0 going in: one entered dead isn't counted.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

LEAD = 0.5          # health and mana are read this long before a pull starts


@dataclass
class PacingMetrics:
    pulls: int = 0
    judged: int = 0
    unsafe: list[tuple[float, str]] = field(default_factory=list)   # (pull start, "health" or "mana"), one per pull
    late: list[tuple[float, float]] = field(default_factory=list)   # (pull start, seconds in combat before a press)

    @property
    def good(self) -> int:
        """judged pulls entered safely and on time"""
        return self.judged - len({t for t, _ in self.unsafe} | {t for t, _ in self.late})


def resource_at(events, guid, t) -> tuple[float | None, float | None]:
    """(health, mana) fractions from guid's last samples at or before t (events in time order, t on their clock);
    None where there is none. Mana counts only from a mana bar (power type 0)."""
    hp = mana = None
    for e in events:
        if e.ts > t:
            break
        i = e.info
        if i is None or i.guid != guid or not i.max_hp:
            continue
        hp = i.hp_pct
        if i.power_type == 0 and i.max_power > 0:
            mana = i.power / i.max_power
    return hp, mana


def measure_pacing(rd, pulls, me) -> PacingMetrics:
    from .score import TUNING as T   # here, not at the top: score.py imports this module
    mine = [e for e in rd.events if e.info and e.info.guid == me]     # one pass, not one per pull
    pc = PacingMetrics(pulls=len(pulls))
    for p in pulls:
        hp, mana = resource_at(mine, me, rd.start + timedelta(seconds=p.start - LEAD))
        if not hp:      # no reading, or dead
            continue
        pc.judged += 1
        if hp < T["pace_hp"]:
            pc.unsafe.append((p.start, "health"))
        elif mana is not None and mana < T["pace_mana"]:
            pc.unsafe.append((p.start, "mana"))
        if p.packs and p.packs[0].puller == me:
            continue    # you started it: on time
        first = next((ln.t for ln in rd.lines if ln.code in ("A", "CS") and p.start <= ln.t <= p.fight.end), None)
        # from your own combat, not the group's first touch: mobs pulled from range take seconds to reach you
        begun = max(p.start, p.fight.start)
        # shortcut: a pull you sat out isn't counted as late, upgrade when we can tell sitting out from being dead
        if first is not None and first - begun > T["pace_late_s"]:
            pc.late.append((p.start, first - begun))
    return pc
