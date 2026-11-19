"""The class-specific tables, matched by spell name, since this server mixes spells from several eras and
the ids differ:
    upkeep       the effects each class is expected to keep up (upkeep.py judges how long you did). "self"
                 is a buff on you, "target" a debuff or DoT on an enemy. Only effects you actually applied
                 this run are judged, so level and talents never count against you.
    defensives   spells that save you when low (summary.py: ready and unused when your health was lowest).
                 Only spells in your spell book are judged, so a name you don't have costs nothing.
    tree roles   the role each talent tree plays; your tree with the most points gives your own role.

To change a class, put it in classes.json next to weights.json: {"ROGUE": [["Slice and Dice", "self"]]}
for upkeep, {"defensives": {"ROGUE": ["Evasion"]}} for defensives. A class listed there replaces the
built-in list for that class.
"""
from __future__ import annotations

import json
from pathlib import Path

DEFAULT_UPKEEP: dict[str, list[tuple[str, str]]] = {
    "WARRIOR": [("Battle Shout", "self"), ("Sunder Armor", "target"), ("Rend", "target"),
                ("Demoralizing Shout", "target"), ("Thunder Clap", "target")],
    "PALADIN": [("Seal of Righteousness", "self"), ("Seal of Command", "self"), ("Righteous Fury", "self"),
                ("Holy Shield", "self")],
    "HUNTER": [("Hunter's Mark", "target"), ("Serpent Sting", "target")],
    "ROGUE": [("Slice and Dice", "self"), ("Rupture", "target")],
    "PRIEST": [("Shadow Word: Pain", "target"), ("Devouring Plague", "target"), ("Inner Fire", "self")],
    "SHAMAN": [("Flame Shock", "target"), ("Lightning Shield", "self")],
    "MAGE": [("Living Bomb", "target")],
    "WARLOCK": [("Corruption", "target"), ("Curse of Agony", "target"), ("Immolate", "target")],
    "DRUID": [("Moonfire", "target"), ("Insect Swarm", "target"), ("Rake", "target"), ("Rip", "target")],
}
UPKEEP = {c: list(v) for c, v in DEFAULT_UPKEEP.items()}   # in use (load_upkeep fills it)

DEFAULT_DEFENSIVES: dict[str, list[str]] = {
    "WARRIOR": ["Shield Wall", "Last Stand"],
    "PALADIN": ["Divine Protection", "Divine Shield", "Lay on Hands", "Blessing of Protection"],
    "HUNTER": ["Feign Death", "Deterrence"],
    "ROGUE": ["Evasion", "Vanish", "Cloak of Shadows"],
    "PRIEST": ["Power Word: Shield", "Desperate Prayer"],
    "SHAMAN": ["Shamanistic Rage"],
    "MAGE": ["Ice Block", "Ice Barrier", "Mana Shield"],
    "WARLOCK": ["Death Coil", "Howl of Terror"],
    "DRUID": ["Barkskin", "Frenzied Regeneration", "Survival Instincts"],
}
DEFENSIVES = {c: list(v) for c, v in DEFAULT_DEFENSIVES.items()}   # in use (load_upkeep fills it)

# Feral Combat is left out: it can tank or do damage, so the guess from spells decides
TREE_ROLE: dict[str, dict[str, str]] = {
    "WARRIOR": {"Arms": "DPS", "Fury": "DPS", "Protection": "TANK"},
    "PALADIN": {"Holy": "HEALER", "Protection": "TANK", "Retribution": "DPS"},
    "PRIEST": {"Discipline": "HEALER", "Holy": "HEALER", "Shadow": "DPS"},
    "SHAMAN": {"Elemental": "DPS", "Enhancement": "DPS", "Restoration": "HEALER"},
    "DRUID": {"Balance": "DPS", "Restoration": "HEALER"},
    "HUNTER": {"Beast Mastery": "DPS", "Marksmanship": "DPS", "Survival": "DPS"},
    "ROGUE": {"Assassination": "DPS", "Combat": "DPS", "Subtlety": "DPS"},
    "MAGE": {"Arcane": "DPS", "Fire": "DPS", "Frost": "DPS"},
    "WARLOCK": {"Affliction": "DPS", "Demonology": "DPS", "Destruction": "DPS"},
}


def talent_role(cls: str | None, talents: list[tuple[str, int]]) -> str | None:
    """the role of your tree with the most points; None with no points, a tie for first, or a tree not known"""
    top = sorted(talents, key=lambda t: -t[1])
    if not top or top[0][1] <= 0 or (len(top) > 1 and top[1][1] == top[0][1]):
        return None
    return TREE_ROLE.get(cls or "", {}).get(top[0][0])


def load_upkeep(path: Path | None):
    """The built-in upkeep and defensive tables, with any class in classes.json replaced (upkeep at the top
    level, defensives under "defensives"); a malformed file or entry is ignored."""
    UPKEEP.clear()
    UPKEEP.update({c: list(v) for c, v in DEFAULT_UPKEEP.items()})
    DEFENSIVES.clear()
    DEFENSIVES.update({c: list(v) for c, v in DEFAULT_DEFENSIVES.items()})
    if path and path.exists():
        try:
            saved = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return
        if not isinstance(saved, dict):
            return
        for cls, rows in saved.items():
            if isinstance(rows, list) and all(isinstance(r, (list, tuple)) and len(r) == 2 and isinstance(r[0], str)
                                              and r[1] in ("self", "target") for r in rows):
                UPKEEP[cls] = [(n, k) for n, k in rows]
        defensives = saved.get("defensives")
        for cls, names in (defensives.items() if isinstance(defensives, dict) else ()):
            if isinstance(names, list) and all(isinstance(n, str) for n in names):
                DEFENSIVES[cls] = list(names)
