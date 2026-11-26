"""What a point of each stat on gear is worth to you, and what a whole item's stats are worth. Pure data.

A role's table counts every stat in points, one point being what 1 attack power (melee, ranged, tank) or 1 spell power
(caster, healer) adds. The tables are standard estimates: the classic-era rules of thumb most guides use (1 Strength is 2
attack power for most melee, 1 Agility is 1 attack power and some crit for rogues, 2 for hunters, 1% crit is about 20 attack
power), never measured. What your own fights measured (worth.py) replaces a standard point only for the stat it is about:
attack power from your swings, spell power from your spells' hits, and then as damage per second, never as points.
Healers, tanks and ranged damage dealers get standard values only (their swings or heals are not what is measured), and a
weapon is always standard: a new one changes the swings the measure was made on.

role(main_role, win, cls) -> "melee", "ranged", "caster", "healer" or "tank"
measured(role, projections, spell_dps) -> {stat key: {"value" (damage per second a point adds), "n", "of" ("swing"/"hit")}}
score(stats, role, measured, slot, cls) -> {"dps", "points", "rank", "parts"}, see score
worth(role, measured, cls) -> what one point of each stat is worth, most first"""
from __future__ import annotations

from . import traits

STR, AGI, STA, INT, SPI = (f"ITEM_MOD_{k}_SHORT" for k in ("STRENGTH", "AGILITY", "STAMINA", "INTELLECT", "SPIRIT"))
AP, RAP = "ITEM_MOD_ATTACK_POWER_SHORT", "ITEM_MOD_RANGED_ATTACK_POWER_SHORT"
SP, SPD, HEAL = "ITEM_MOD_SPELL_POWER_SHORT", "ITEM_MOD_SPELL_DAMAGE_DONE_SHORT", "ITEM_MOD_SPELL_HEALING_DONE_SHORT"
CRIT, HIT, HASTE = "ITEM_MOD_CRIT_RATING_SHORT", "ITEM_MOD_HIT_RATING_SHORT", "ITEM_MOD_HASTE_RATING_SHORT"
SCRIT, SHIT = "ITEM_MOD_CRIT_SPELL_RATING_SHORT", "ITEM_MOD_HIT_SPELL_RATING_SHORT"
DODGE, PARRY, BLOCK = "ITEM_MOD_DODGE_RATING_SHORT", "ITEM_MOD_PARRY_RATING_SHORT", "ITEM_MOD_BLOCK_RATING_SHORT"
BLOCKV, DEF, MP5 = "ITEM_MOD_BLOCK_VALUE_SHORT", "ITEM_MOD_DEFENSE_SKILL_RATING_SHORT", "ITEM_MOD_MANA_REGENERATION_SHORT"
ARMOR, DPS = "RESISTANCE0_NAME", "ITEM_MOD_DAMAGE_PER_SECOND_SHORT"
# an item's rating is ten to a percent on this client: "+5 Hit" on an item that gives 0.5%.
# shortcut: one item seen (2026-11-24), check more items before trusting the rating rows
PCT = 10

TABLES = {
    "melee": {STR: 2, AGI: 1, AP: 1, CRIT: 20 / PCT, HIT: 15 / PCT, HASTE: 10 / PCT, DPS: 14},
    "ranged": {AGI: 2.4, RAP: 1, AP: 1, INT: .2, CRIT: 20 / PCT, HIT: 15 / PCT, DPS: 14},
    "caster": {SP: 1, SPD: 1, INT: .4, SPI: .1, MP5: .8, SCRIT: 10 / PCT, SHIT: 12 / PCT, DPS: 3},
    "healer": {HEAL: 1, SP: 1, INT: .6, SPI: .4, MP5: 1.5, SCRIT: 8 / PCT, STA: .1},
    "tank": {STA: 1.5, AGI: 1.5, STR: 1.5, AP: 1, ARMOR: .1, DEF: 1.5, DODGE: 25 / PCT, PARRY: 20 / PCT, BLOCK: 10 / PCT,
             BLOCKV: .5, HIT: 10 / PCT, CRIT: 10 / PCT, DPS: 7},
}
CLASS = {("melee", "ROGUE"): {STR: 1, AGI: 1.7}}        # a rogue's Strength is 1 attack power, its Agility that and crit
ANCHOR = {"melee": "attack power", "ranged": "attack power", "tank": "attack power", "caster": "spell power", "healer": "healing"}
WEAPON_SLOTS = {"melee": {16, 17}, "tank": {16, 17}, "ranged": {18}, "caster": {18}, "healer": set()}  # a weapon's DPS counts
WEAPONS = {16, 17, 18}
STANDARD_ONLY = {"ranged", "healer", "tank"}
BY_CLASS = {"HUNTER": "ranged", "MAGE": "caster", "PRIEST": "caster", "WARLOCK": "caster"}     # before any fight says
SHOT, SWING = .10, .20          # shares of your damage that make you ranged (Auto Shot), or melee (swings)
NAME = {STR: "Strength", AGI: "Agility", STA: "Stamina", INT: "Intellect", SPI: "Spirit", AP: "Attack power",
        RAP: "Ranged attack power", SP: "Spell power", SPD: "Spell damage", HEAL: "Healing", CRIT: "Critical strike rating",
        HIT: "Hit rating", HASTE: "Haste rating", SCRIT: "Spell critical strike rating", SHIT: "Spell hit rating",
        DODGE: "Dodge rating", PARRY: "Parry rating", BLOCK: "Block rating", BLOCKV: "Block value", DEF: "Defense",
        MP5: "Mana every 5 seconds", ARMOR: "Armor", DPS: "Weapon damage per second"}


def role(main_role: str | None, win: list[dict], cls: str | None) -> str:
    """the table for you: a healer's or a tank's by the main role, else how your fights did their damage: Auto Shot (a tenth of it
    and more than your swings) is ranged, swings (a fifth) melee, the rest caster; by class before any fight says"""
    if main_role in ("healer", "tank"):
        return main_role
    rows = traits.abilities(win)["all"] if win else {}
    total = sum(r[3] for r in rows.values())
    if not total:
        return BY_CLASS.get(cls or "", "melee")
    shot, swing = (rows.get("Auto Shot") or [0] * 4)[3] / total, (rows.get("Melee") or [0] * 4)[3] / total
    return "ranged" if shot >= SHOT and shot >= swing else "melee" if swing >= SWING else "caster"


def measured(role: str, projections: dict, spell_dps: list[dict]) -> dict:
    """what your fights measured a point is worth, for the stats a role's measure is about: attack power by your swings (melee),
    spell power by your spells' hits (caster, the spells measured added up)"""
    ap = (projections or {}).get("ap10") or {}
    if role == "melee" and ap.get("source") == "measured":
        return {AP: {"value": ap["value"] / 10, "n": ap["n"], "of": "swing"}}
    if role == "caster" and spell_dps:
        got = {"value": sum(s["value"] for s in spell_dps), "n": sum(s["n"] for s in spell_dps), "of": "hit"}
        return {SP: got, SPD: got}
    return {}


def table(role: str, cls: str | None = None) -> dict[str, float]:
    return TABLES[role] | CLASS.get((role, cls), {})


def score(stats: dict, role: str, measured: dict | None = None, slot: int | None = None, cls: str | None = None) -> dict:
    """what an item's stats (the game's keys, as itemstats has them) are worth to role, worn in slot: {"dps" (damage per second from
    the stats your fights measured, None when none is), "points" (the rest, standard), "rank" (all of it in points, to put items in
    order), "parts" [{"key", "amount", "dps", "points", "source" ("measured" or "standard")}]}. A weapon's DPS counts only in the
    slots the role fights with; a weapon is always standard"""
    weights = table(role, cls)
    if role in STANDARD_ONLY or slot in WEAPONS or DPS in stats:
        measured = {}
    dps, points, rank, parts = None, 0.0, 0.0, []
    for key, amount in stats.items():
        w = weights.get(key)
        if not w or not amount or key == DPS and slot is not None and slot not in WEAPON_SLOTS[role]:
            continue
        rank += amount * w
        if m := (measured or {}).get(key):
            dps = (dps or 0.0) + amount * m["value"]
            parts.append({"key": key, "amount": amount, "dps": amount * m["value"], "points": None, "source": "measured"})
        else:
            points += amount * w
            parts.append({"key": key, "amount": amount, "dps": None, "points": amount * w, "source": "standard"})
    return {"dps": dps, "points": points, "rank": rank, "parts": parts}


def worth(role: str | None, measured: dict | None = None, cls: str | None = None) -> list[dict]:
    """what one point of each stat is worth to role, most first: {"key", "name", "points" (standard), "dps" (measured, else None),
    "n", "of"}; [] without a role"""
    if role not in TABLES:
        return []
    got = {} if role in STANDARD_ONLY else measured or {}
    rows = [{"key": k, "name": NAME[k], "points": w, "dps": (got.get(k) or {}).get("value"), "n": (got.get(k) or {}).get("n"),
             "of": (got.get(k) or {}).get("of")} for k, w in table(role, cls).items()]
    return sorted(rows, key=lambda r: (-r["points"], r["name"]))
