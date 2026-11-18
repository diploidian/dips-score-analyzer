"""The one class-specific table: the effects each class is expected to keep up (upkeep.py judges how
long you did). Matched by spell name, since this server mixes spells from several eras and the ids
differ. "self" is a buff on you, "target" a debuff or DoT on an enemy. Only effects you actually
applied this run are judged, so level and talents never count against you.

To change a class, put it in classes.json next to weights.json: {"ROGUE": [["Slice and Dice", "self"]]}.
A class listed there replaces the built-in list for that class.
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


def load_upkeep(path: Path | None):
    """The built-in table, with any class in classes.json replaced; a malformed file is ignored."""
    UPKEEP.clear()
    UPKEEP.update({c: list(v) for c, v in DEFAULT_UPKEEP.items()})
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
