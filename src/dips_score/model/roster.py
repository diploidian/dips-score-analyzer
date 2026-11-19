"""Who was in the group: clean names, class and role.

Class and role come from, best first:
    1. what you picked in the window (saved in roster.json, by player GUID)
    2. the addon's P lines (exact: the game's own class and the group finder's role)
    3. for you only, your talents (the add-on's character snapshot): the role of your fullest tree
    4. a guess from the combat log: class from the spells they cast; role from what they did
       (healing, or a tank's abilities and the most damage taken)
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from ..scoring.classes import talent_role
from ..sources.combatlog import Event

CLASSES = ["WARRIOR", "PALADIN", "HUNTER", "ROGUE", "PRIEST", "SHAMAN", "MAGE", "WARLOCK", "DRUID"]
ROLES = ["TANK", "HEALER", "DPS"]

CLASS_COLORS = {  # the game's class colors
    "WARRIOR": (0.78, 0.61, 0.43), "PALADIN": (0.96, 0.55, 0.73), "HUNTER": (0.67, 0.83, 0.45),
    "ROGUE": (1.00, 0.96, 0.41), "PRIEST": (1.00, 1.00, 1.00), "SHAMAN": (0.00, 0.44, 0.87),
    "MAGE": (0.25, 0.78, 0.92), "WARLOCK": (0.53, 0.53, 0.93), "DRUID": (1.00, 0.49, 0.04),
}

# spells only one class casts, for guessing a class from the combat log
SIGNATURE = {
    "WARRIOR": ["Heroic Strike", "Sunder Armor", "Shield Slam", "Shield Block", "Revenge", "Charge", "Bloodrage",
                "Battle Shout", "Mortal Strike", "Bloodthirst", "Whirlwind", "Execute", "Rend", "Thunder Clap",
                "Taunt", "Cleave", "Overpower", "Demoralizing Shout", "Shield Bash", "Pummel", "Hamstring"],
    "PALADIN": ["Holy Light", "Flash of Light", "Seal of Righteousness", "Seal of Command", "Judgement",
                "Consecration", "Blessing of Might", "Holy Shock", "Divine Shield", "Hammer of Justice",
                "Exorcism", "Righteous Fury", "Holy Shield", "Crusader Strike", "Blessing of Kings"],
    "HUNTER": ["Auto Shot", "Aimed Shot", "Multi-Shot", "Arcane Shot", "Serpent Sting", "Hunter's Mark",
               "Raptor Strike", "Mongoose Bite", "Steady Shot", "Feign Death", "Wing Clip", "Concussive Shot",
               "Summon Hawk", "Kill Command"],
    "ROGUE": ["Sinister Strike", "Eviscerate", "Backstab", "Slice and Dice", "Kick", "Gouge", "Ambush", "Garrote",
              "Rupture", "Kidney Shot", "Sprint", "Evasion", "Hemorrhage", "Mutilate", "Sap"],
    "PRIEST": ["Heal", "Flash Heal", "Greater Heal", "Renew", "Power Word: Shield", "Mind Blast", "Mind Flay",
               "Shadow Word: Pain", "Smite", "Holy Fire", "Prayer of Healing", "Psychic Scream", "Inner Fire",
               "Shadowform", "Devouring Plague", "Vampiric Embrace", "Power Word: Fortitude"],
    "SHAMAN": ["Lightning Bolt", "Chain Lightning", "Earth Shock", "Flame Shock", "Frost Shock", "Healing Wave",
               "Lesser Healing Wave", "Chain Heal", "Stormstrike", "Windfury Weapon", "Rockbiter Weapon",
               "Searing Totem", "Lava Burst", "Lightning Shield"],
    "MAGE": ["Fireball", "Frostbolt", "Arcane Missiles", "Arcane Explosion", "Fire Blast", "Scorch", "Pyroblast",
             "Blizzard", "Frost Nova", "Polymorph", "Arcane Intellect", "Blast Wave", "Arcane Blast", "Ice Lance",
             "Living Bomb", "Counterspell"],
    "WARLOCK": ["Shadow Bolt", "Corruption", "Curse of Agony", "Immolate", "Drain Life", "Life Tap", "Fear",
                "Searing Pain", "Hellfire", "Drain Soul", "Summon Imp", "Summon Voidwalker", "Incinerate",
                "Chaos Bolt", "Haunt", "Curse of the Elements"],
    "DRUID": ["Wrath", "Moonfire", "Starfire", "Rejuvenation", "Regrowth", "Healing Touch", "Lifebloom",
              "Swiftmend", "Maul", "Swipe", "Mangle", "Shred", "Rake", "Claw", "Ferocious Bite", "Bear Form",
              "Cat Form", "Insect Swarm", "Wild Growth", "Mark of the Wild"],
}
_CLASS_OF = {s: c for c, spells in SIGNATURE.items() for s in spells}
TANK_SPELLS = {"Shield Slam", "Shield Block", "Revenge", "Taunt", "Defensive Stance", "Righteous Fury",
               "Holy Shield", "Maul", "Swipe", "Growl", "Bear Form", "Dire Bear Form", "Sunder Armor"}
GROUP_ROLE = {"TANK": "TANK", "HEALER": "HEALER", "DAMAGER": "DPS"}


def clean_name(name: str) -> str:
    """'Priime-Tiime-PvP-US' -> 'Priime Tiime'. Names here are "First Surname"; the log adds the realm
    type and region on the end. Names from elsewhere ('Name-Realm') keep just the name."""
    parts = [p for p in name.split("-") if p]
    if len(parts) >= 4:
        return " ".join(parts[:-2])
    if len(parts) >= 2:
        return parts[0]
    return name or "?"


@dataclass
class Player:
    guid: str
    name: str
    cls: str | None = None
    role: str | None = None
    cls_from: str = "?"      # "you", "addon", "spells" (role_from can also be "talents")
    role_from: str = "?"
    is_me: bool = False
    race: str | None = None  # the game's token, e.g. "NightElf"; None for logs from before races were recorded

    @property
    def color(self) -> tuple[float, float, float]:
        return CLASS_COLORS.get(self.cls or "", (0.75, 0.75, 0.78))

    @property
    def color_hex(self) -> str:
        r, g, b = self.color
        return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"


class Overrides:
    """Your class and role picks, by player GUID, in a small JSON file."""

    def __init__(self, path: Path | None):
        self.path = path
        self.data: dict[str, dict[str, str]] = {}
        if path and path.exists():
            try:
                self.data = json.loads(path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                self.data = {}

    def get(self, guid: str) -> dict[str, str]:
        return self.data.get(guid, {})

    def set(self, guid: str, cls: str | None = None, role: str | None = None):
        d = self.data.setdefault(guid, {})
        if cls:
            d["class"] = cls
        if role:
            d["role"] = role
        self.save()

    def clear(self, guid: str):
        self.data.pop(guid, None)
        self.save()

    def save(self):
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=1), encoding="utf-8")


def _is_group(flags: int) -> bool:
    return flags & 0x7 in (0x1, 0x2, 0x4)   # affiliation: mine, party, raid


def build_roster(events: list[Event], addon_lines, me: str | None, overrides: Overrides | None = None,
                 char: dict | None = None) -> dict[str, Player]:
    """guid -> Player for everyone in the group. addon_lines: the run's P lines (TLine-like, fields
    guid, name, class, role, race). char: your character snapshot (savedvars.load_char), or None."""
    players: dict[str, Player] = {}
    for e in events:
        for g, n, fl in ((e.src, e.src_name, e.src_flags), (e.dst, e.dst_name, e.dst_flags)):
            if g.startswith("Player-") and _is_group(fl) and g not in players:
                players[g] = Player(g, clean_name(n), is_me=(g == me))

    # 2. the addon's roster
    for ln in addon_lines:
        guid, name, cls, role, race = (ln.f(0), ln.f(1), ln.f(2), ln.f(3), ln.f(4))
        if not guid.startswith("Player-"):
            continue
        p = players.setdefault(guid, Player(guid, name or "?", is_me=(guid == me)))
        if name and name != "?":
            p.name = name
        if race:  # older logs have no race field: ln.f gives "" and the player keeps None
            p.race = race
        if cls in CLASS_COLORS:
            p.cls, p.cls_from = cls, "addon"
        if role in GROUP_ROLE:
            p.role, p.role_from = GROUP_ROLE[role], "addon"

    # 3. your talents
    you = players.get(me or "")
    if you and you.role is None and char and char.get("guid") == me:
        role = talent_role(char.get("class") or you.cls, char.get("talents") or [])
        if role:
            you.role, you.role_from = role, "talents"

    # 4. guesses from the combat log
    casts: dict[str, Counter] = {g: Counter() for g in players}
    dmg, taken, cast_heal = Counter(), Counter(), Counter()
    cast_ids: dict[str, set[int]] = {g: set() for g in players}
    for e in events:
        if e.src in players:
            if e.event in ("SPELL_CAST_SUCCESS", "SPELL_CAST_START", "SPELL_AURA_APPLIED"):
                casts[e.src][e.spell_name] += 1
                if e.event != "SPELL_AURA_APPLIED" and e.spell_id:
                    cast_ids[e.src].add(e.spell_id)
            if e.event.endswith("_DAMAGE") and not e.event.endswith("_LANDED"):
                dmg[e.src] += e.amount
        if e.dst in players and e.event.endswith("_DAMAGE") and not e.event.endswith("_LANDED"):
            taken[e.dst] += e.amount
    for e in events:
        if e.src in players and e.event.endswith("_HEAL") and e.spell_id in cast_ids[e.src]:
            cast_heal[e.src] += max(0, e.amount - e.overheal)

    for g, p in players.items():
        if p.cls is None:
            votes = Counter()
            for spell, n in casts[g].items():
                c = _CLASS_OF.get(spell)
                if c:
                    votes[c] += 1  # how many different signature spells, not how often
            if votes:
                p.cls, p.cls_from = votes.most_common(1)[0][0], "spells"
    tanks = [g for g, p in players.items() if p.role is None and p.cls in ("WARRIOR", "PALADIN", "DRUID")
             and sum(casts[g][s] for s in TANK_SPELLS) >= 5]
    tank = max(tanks, key=lambda g: taken[g], default=None)
    for g, p in players.items():
        if p.role is not None:
            continue
        if g == tank:
            p.role = "TANK"
        elif cast_heal[g] >= 0.3 * (cast_heal[g] + dmg[g]) and cast_heal[g] > 0:
            p.role = "HEALER"
        else:
            p.role = "DPS"
        p.role_from = "spells"

    # 1. your picks win
    if overrides:
        for g, p in players.items():
            o = overrides.get(g)
            if o.get("class") in CLASS_COLORS:
                p.cls, p.cls_from = o["class"], "you"
            if o.get("role") in ROLES:
                p.role, p.role_from = o["role"], "you"
    return players
