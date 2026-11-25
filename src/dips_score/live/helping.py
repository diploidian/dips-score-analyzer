"""What you do for other players, in and out of fights: revives, and buffs, heals and dispels you cast on them. Pure data.

Watch reads the log's events and gives one act per thing done: {"id", "me", "t" (ISO, the log's time), "kind"
("revive", "buff", "heal" or "dispel"), "spell", "group" (they were in your group), "who" (a short hash, never a name)}.
The id comes from the log line, so the live log and a replay give the same one.

  revive   SPELL_RESURRECT on a player; the log does not say whether they took it
  others   the effect of a spell you cast on that very player, within NEAR seconds: so no aura that radiates, no buff
           the game logs again when somebody comes back into range, and only the target of a spell that reaches many
A heal that healed nothing, and heals and dispels on your own group (Mercy has those), are left out; so is anything on
yourself, a pet or a hostile player.
"""
from __future__ import annotations

import hashlib
from datetime import datetime

from ..sources.combatlog import REACTION_HOSTILE, Event

NEAR = 1.5
EFFECTS = {"SPELL_AURA_APPLIED": "buff", "SPELL_AURA_REFRESH": "buff", "SPELL_HEAL": "heal", "SPELL_DISPEL": "dispel"}


def _hash(text: str, n: int) -> str:
    return hashlib.sha1(text.encode()).hexdigest()[:n]


class Watch:
    def __init__(self):
        self.casts: dict[tuple[str, str], datetime] = {}       # (spell, player) -> your cast on them not yet counted
        self.buffs: dict[tuple[str, str], datetime] = {}       # the last buff per (spell, player): a refresh says no type

    def feed(self, e: Event, me: str | None) -> dict | None:
        if not me or e.src != me or e.dst == me or not e.dst.startswith("Player-") or e.dst_flags & REACTION_HOSTILE:
            return None
        key, group = (e.spell_name, e.dst), e.dst_flags & 0xF in (0x2, 0x4)
        if e.event == "SPELL_CAST_SUCCESS":
            self.casts[key] = e.ts
            return None
        if e.event == "SPELL_RESURRECT":
            return self._act(e, me, "revive", group)
        kind = EFFECTS.get(e.event)
        if kind == "buff" and e.event == "SPELL_AURA_APPLIED":
            if e.aura_type != "BUFF":
                return None
            self.buffs[key] = e.ts
        if kind is None or (kind == "buff" and key not in self.buffs) or (kind == "heal" and e.amount <= e.overheal):
            return None
        cast = self.casts.get(key)
        if cast is None or abs((e.ts - cast).total_seconds()) > NEAR:
            return None
        del self.casts[key]         # one act per cast, whatever it does
        return None if group and kind != "buff" else self._act(e, me, kind, group)

    @staticmethod
    def _act(e: Event, me: str, kind: str, group: bool) -> dict:
        t = e.ts.isoformat()
        return {"id": _hash(f"{t}|{e.spell_name}|{e.dst}", 16), "me": me, "t": t, "kind": kind, "spell": e.spell_name,
                "group": group, "who": _hash(e.dst, 12)}


def figures(acts: list[dict] | None, lo: datetime, hi: datetime) -> dict | None:
    """one character's acts in (lo, hi], None without any act known at all: {"strangers" (each once a day), "different"
    (strangers), "revives", "group_revives" (of them, in your group), "group_buffs"}"""
    if not acts:
        return None
    win = [a for a in acts if lo < datetime.fromisoformat(a["t"]) <= hi]
    out = [a for a in win if not a["group"] and a["kind"] != "revive"]
    return {"strangers": len({(a["t"][:10], a["who"]) for a in out}), "different": len({a["who"] for a in out}),
            "revives": sum(a["kind"] == "revive" for a in win),
            "group_revives": sum(a["group"] and a["kind"] == "revive" for a in win),
            "group_buffs": sum(a["group"] and a["kind"] == "buff" for a in win)}
