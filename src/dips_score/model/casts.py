"""Every group member's casts from the combat log, and a per-spell breakdown.

A cast is a SPELL_CAST_SUCCESS (instants and finished casts) or a SPELL_CAST_FAILED; a cast with a
cast time also gets the SPELL_CAST_START it began with, so its bar can be drawn.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .roster import Player, clean_name
from .run import AUTO_REPEAT, RunData

MAX_CAST = 10.0     # a start this long before a success isn't the same cast


@dataclass
class CastEvent:
    t: float                  # when it finished (or failed)
    guid: str
    spell_id: int | None
    spell: str
    target: str               # a clean name, or "" for no target
    began: float | None       # when its cast bar started, if it had one
    ok: bool = True
    reason: str = ""          # why it failed

    @property
    def auto(self) -> bool:   # wand shots and Auto Shot
        return self.spell_id in AUTO_REPEAT


@dataclass
class SpellRow:
    spell_id: int | None
    spell: str
    casts: int = 0
    failed: int = 0
    damage: int = 0
    healing: int = 0          # effective
    overheal: int = 0
    hits: int = 0
    crits: int = 0

    @property
    def overheal_share(self) -> float:
        n = self.healing + self.overheal
        return self.overheal / n if n else 0.0

    @property
    def crit_share(self) -> float:
        return self.crits / self.hits if self.hits else 0.0


def player_casts(rd: RunData, roster: dict[str, Player]) -> dict[str, list[CastEvent]]:
    out: dict[str, list[CastEvent]] = defaultdict(list)
    started: dict[tuple[str, int | None], float] = {}
    for e in rd.events:
        if e.src not in roster or not e.event.startswith("SPELL_CAST_"):
            continue
        t = rd.rel(e.ts)
        key = (e.src, e.spell_id)
        if e.event == "SPELL_CAST_START":
            started[key] = t
            continue
        began = started.pop(key, None)
        if began is not None and t - began > MAX_CAST:
            began = None
        target = ""
        if e.dst and e.dst != "0000000000000000":
            target = clean_name(e.dst_name) if e.dst.startswith("Player-") else e.dst_name
        out[e.src].append(CastEvent(t, e.src, e.spell_id, e.spell_name, target, began,
                                    e.event == "SPELL_CAST_SUCCESS", e.reason))
    return dict(out)


def spell_table(rd: RunData, guid: str, windows: list[tuple[float, float]] | None = None,
                owned: set[str] | None = None) -> list[SpellRow]:
    """Per-spell totals for one player (and their pets, `owned`), biggest first."""
    who = {guid} | (owned or set())

    def keep(t: float) -> bool:
        return windows is None or any(a <= t <= b for a, b in windows)

    rows: dict[int | None, SpellRow] = {}

    def row(e) -> SpellRow:
        sid = e.spell_id if e.spell_id else -1 if e.event.startswith("SWING") else None
        name = e.spell_name or ("Melee" if e.event.startswith("SWING") else "?")
        if e.src != guid and e.src in who:
            name = f"{name} (pet)"
            sid = (sid or 0) + 10_000_000
        if sid not in rows:
            rows[sid] = SpellRow(sid, name)
        return rows[sid]

    for e in rd.events:
        if e.src not in who or not keep(rd.rel(e.ts)):
            continue
        ev = e.event
        if ev == "SPELL_CAST_SUCCESS" and e.src == guid:
            row(e).casts += 1
        elif ev == "SPELL_CAST_FAILED" and e.src == guid:
            row(e).failed += 1
        elif ev.endswith("_DAMAGE") and not ev.endswith("_LANDED"):
            r = row(e)
            r.damage += e.amount
            r.hits += 1
            r.crits += e.crit
        elif ev.endswith("_HEAL"):
            r = row(e)
            r.healing += max(0, e.amount - e.overheal)
            r.overheal += e.overheal
            r.hits += 1
            r.crits += e.crit
    return sorted(rows.values(), key=lambda r: (r.damage + r.healing, r.casts), reverse=True)


def pets_of(rd: RunData, roster: dict[str, Player]) -> dict[str, set[str]]:
    """owner GUID -> the GUIDs of pets and guardians they summoned"""
    out: dict[str, set[str]] = defaultdict(set)
    for e in rd.events:
        if e.event == "SPELL_SUMMON" and e.src in roster:
            out[e.src].add(e.dst)
    return dict(out)
