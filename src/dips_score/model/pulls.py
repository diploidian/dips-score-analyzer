"""Enemies and pulls.

Every hostile NPC the group touched becomes an Enemy: when it first touched the group, who and
how (an ability like Charge, or "body pull" when the mob acted first), the raid markers it wore,
who it went for first, and when and by whom it died.

The log has no threat data, so "who it went for first" is the first player it hit or cast at.
That's usually who has its threat, but not always.

Each fight's enemies are split into packs: a mob first touched more than PACK_GAP seconds after
the one before starts a new pack. Every pack after the first joined mid-fight (an extra pull),
and its puller is whoever touched its first mob.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..sources.combatlog import is_enemy, marker, npc_id
from .roster import Player
from .run import Fight, RunData

PACK_GAP = 4.0
LEAD_IN = 20.0      # a mob engaged this long before your combat started still belongs to that fight
                    # (a healer's combat starts at their first heal, often after the tank pulled)
# touching a mob with these doesn't pull it
NOT_A_PULL = {"Hunter's Mark", "Detect Magic", "Mind Vision", "Eagle Eye", "Track Humanoids", "Track Beasts"}
_NOT_ENGAGING = {"SPELL_AURA_REMOVED", "SPELL_AURA_REMOVED_DOSE", "UNIT_DIED", "PARTY_KILL", "UNIT_DESTROYED",
                 "SPELL_SUMMON", "SPELL_CREATE"}


@dataclass
class Enemy:
    guid: str
    name: str
    npc: int | None
    first_seen: float
    engaged_by: str | None = None      # player GUID (a pet counts as its owner when known)
    how: str = ""                      # the ability, "body pull", or "melee"
    first_target: str | None = None    # first player it hit or cast at
    markers: list[str] = field(default_factory=list)
    died: float | None = None
    killer: str | None = None          # player GUID, when a group member landed the blow
    killing_blow: str = ""             # the spell (or "melee")
    damage_taken: int = 0

    @property
    def marker(self) -> str | None:
        return self.markers[-1] if self.markers else None


@dataclass
class Pack:
    start: float
    enemies: list[Enemy]
    puller: str | None
    how: str
    extra: bool                        # joined a fight already going


@dataclass
class Pull:
    index: int                         # which fight (rd.fights)
    fight: Fight
    packs: list[Pack]

    @property
    def enemies(self) -> list[Enemy]:
        return [e for p in self.packs for e in p.enemies]

    @property
    def start(self) -> float:
        """when the first mob was engaged (can be before your own combat started)"""
        return min([self.fight.start] + [p.start for p in self.packs])

    @property
    def kill_order(self) -> list[Enemy]:
        return sorted((e for e in self.enemies if e.died is not None), key=lambda e: e.died)


def find_enemies(rd: RunData, roster: dict[str, Player]) -> dict[str, Enemy]:
    # pets and guardians count as their owner (a hunter's pet pulling is the hunter's pull)
    owners = {e.dst: e.src for e in rd.events if e.event == "SPELL_SUMMON" and e.src in roster}
    enemies: dict[str, Enemy] = {}
    last_hit: dict[str, tuple[str, str]] = {}   # enemy -> (player, spell) of the last group hit on it

    def group_side(guid: str) -> str | None:
        return guid if guid in roster else owners.get(guid)

    for e in rd.events:
        t = rd.rel(e.ts)
        if e.event not in _NOT_ENGAGING and e.spell_name not in NOT_A_PULL:
            them, us = None, None
            if is_enemy(e.src, e.src_flags) and group_side(e.dst):
                them, us = e.src, group_side(e.dst)
                if them not in enemies:
                    enemies[them] = Enemy(them, e.src_name, npc_id(them), t, us, "body pull")
                if enemies[them].first_target is None:
                    enemies[them].first_target = us
            elif is_enemy(e.dst, e.dst_flags) and group_side(e.src) and e.dst not in enemies:
                how = e.spell_name or ("melee" if e.event.startswith("SWING") else e.event.lower())
                enemies[e.dst] = Enemy(e.dst, e.dst_name, npc_id(e.dst), t, group_side(e.src), how)
        for g, raid in ((e.src, e.src_raid), (e.dst, e.dst_raid)):
            if raid and g in enemies:
                m = marker(raid)
                if m and (not enemies[g].markers or enemies[g].markers[-1] != m):
                    enemies[g].markers.append(m)
        if e.dst in enemies:
            en = enemies[e.dst]
            if e.event.endswith("_DAMAGE") and not e.event.endswith("_LANDED") and en.died is None:
                en.damage_taken += e.amount
                if group_side(e.src):
                    spell = e.spell_name or "melee"
                    last_hit[e.dst] = (group_side(e.src), spell if e.src in roster else f"{spell} (pet)")
            if e.event == "PARTY_KILL" and group_side(e.src):
                en.killer = group_side(e.src)
                # this log doesn't mark the killing hit itself: it's the killer's last hit on it
                hit = last_hit.get(e.dst)
                en.killing_blow = hit[1] if hit and hit[0] == en.killer else ""
            if e.event == "UNIT_DIED" and en.died is None:
                en.died = t
                # the kill credit can come before the killing hit in the log: settle it now
                hit = last_hit.get(e.dst)
                if hit and (en.killer is None or (en.killer == hit[0] and not en.killing_blow)):
                    en.killer, en.killing_blow = hit
    return enemies


def build_pulls(rd: RunData, roster: dict[str, Player]) -> tuple[list[Pull], list[Enemy]]:
    """(pulls, enemies touched outside any fight of yours)"""
    enemies = sorted(find_enemies(rd, roster).values(), key=lambda e: e.first_seen)
    pulls = [Pull(i, f, []) for i, f in enumerate(rd.fights)]
    loose: list[Enemy] = []
    by_fight: dict[int, list[Enemy]] = {}
    for en in enemies:
        # the fight it was engaged in; else the next fight, if that starts within LEAD_IN after
        idx = next((i for i, f in enumerate(rd.fights) if f.start - 1 <= en.first_seen <= f.end), None)
        if idx is None:
            idx = next((i for i, f in enumerate(rd.fights) if 0 <= f.start - en.first_seen <= LEAD_IN), None)
        if idx is None:
            loose.append(en)
        else:
            by_fight.setdefault(idx, []).append(en)
    for idx, ens in by_fight.items():
        packs: list[list[Enemy]] = []
        for en in ens:
            if packs and en.first_seen - packs[-1][-1].first_seen <= PACK_GAP:
                packs[-1].append(en)
            else:
                packs.append([en])
        pulls[idx].packs = [Pack(p[0].first_seen, p, p[0].engaged_by, p[0].how, i > 0) for i, p in enumerate(packs)]
    return pulls, loose
