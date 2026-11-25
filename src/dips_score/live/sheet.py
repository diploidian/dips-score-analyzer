"""The character sheet: what the character carries and knows, from the add-on's snapshot (Sheet.lua), joined to how the
window's fights used it. Pure data, plain values; what cannot be known is None, never a guess.

sheet(char, win, fig) -> None without a snapshot that holds one, else {"taken" (the time() what is worn was read), "gear", "stats",
"abilities", "points", "trees", "skills", "projections"}. win: the window's fights; fig: profile.figures of it, for the main
role.

  gear         one per slot of SLOTS: {"slot", "label", "name", "level", "quality", "enchant" (id, 0 none, None not read), "flags",
               "stats" (its numbers) and "text" (what it does), both lines as the game writes them, "whole" (the tooltip was read;
               else "stats" has only what reads the same everywhere: armor, the five, resistances, a weapon's damage)}
  stats        {key: {"value" (None: hidden by the game), "gear" (how much of it the items give, None when none does),
               "by_quality" {item quality: its part of that}}}; a primary one also has "own" (without gear or buffs), "buffs"
               (buffs, enchants and set bonuses) and "lost" (to debuffs) when the snapshot has the game's bonus figure (add-on 0.5.1)
  abilities    every spell known: {"name", "rank" (the highest one cast, its text, None when the fights don't say), "ranks" (how many), "casts" (in fights),
               "share" (of the window's damage, its procs with it, None without), "lower" (only ranks under the highest one known were cast)}
  projections  {key: {"value", "source" ("measured", "game", "estimate" or None), "n" (what it rests on)}}, see _projections

  worth        worth.spells: what spell power adds to a hit of each spell
  swings       worth.hits: how your swings landed, None with too few"""
from __future__ import annotations

import re
from statistics import median

from . import traits, worth
from .habits import _damage_fights
from .summary import NO_GEAR_LEVEL

SLOTS = ((1, "Head"), (2, "Neck"), (3, "Shoulder"), (5, "Chest"), (6, "Waist"), (7, "Legs"), (8, "Feet"), (9, "Wrist"),
         (10, "Hands"), (11, "Ring 1"), (12, "Ring 2"), (13, "Trinket 1"), (14, "Trinket 2"), (15, "Back"),
         (16, "Main hand"), (17, "Off hand"), (18, "Ranged"))
MAY_BE_EMPTY = {17, 18}                 # a two-hander fills the off hand, and not every class has a ranged slot
ENCHANTABLE = {5, 8, 9, 10, 15, 16}     # chest, feet, wrist, hands, back, weapon
# a stat's key in Sheet.lua -> the game's key on an item
ITEM_KEY = {"str": "ITEM_MOD_STRENGTH_SHORT", "agi": "ITEM_MOD_AGILITY_SHORT", "sta": "ITEM_MOD_STAMINA_SHORT",
            "int": "ITEM_MOD_INTELLECT_SHORT", "spi": "ITEM_MOD_SPIRIT_SHORT", "armor": "RESISTANCE0_NAME"}
STAT_NAME = {"ITEM_MOD_STRENGTH_SHORT": "Strength", "ITEM_MOD_AGILITY_SHORT": "Agility", "ITEM_MOD_STAMINA_SHORT": "Stamina",
             "ITEM_MOD_INTELLECT_SHORT": "Intellect", "ITEM_MOD_SPIRIT_SHORT": "Spirit", "RESISTANCE0_NAME": "Armor",
             "RESISTANCE1_NAME": "Holy resistance", "RESISTANCE2_NAME": "Fire resistance", "RESISTANCE3_NAME": "Nature resistance",
             "RESISTANCE4_NAME": "Frost resistance", "RESISTANCE5_NAME": "Shadow resistance", "RESISTANCE6_NAME": "Arcane resistance"}
WEAPON_DPS = "ITEM_MOD_DAMAGE_PER_SECOND_SHORT"
AP_PER_DPS = 14                         # the classic rule: 14 attack power is one damage per second
NOT_A_SPELL = {"Attack"}                # auto attack is in the book too
CLOSE = 0.10                            # an estimate is shown only this near the game's own figure
MIN_DAMAGE, MIN_HEALING, MIN_SWINGS = 10, 5, 10      # fights a measure needs


NOT_SAID = re.compile(r"Item Level |Soulbound$|Binds |Unique|Durability |Requires |Classes: |Races: |Sell Price|Quest Item$|Cooldown remaining|Equipment Sets: |\s*$")
WORN_AS = {"Head", "Neck", "Shoulder", "Back", "Chest", "Shirt", "Tabard", "Wrist", "Hands", "Waist", "Legs", "Feet", "Finger", "Trinket",
           "One-Hand", "Two-Hand", "Main Hand", "Off Hand", "Held In Off-hand", "Held In Off-Hand", "Ranged", "Thrown", "Relic", "Projectile"}
NUMBER_LINE = re.compile(r"[+\-−] ?\d|[\d,.]+ (?:- [\d,.]+ )?(?:\w+ )?(?:Armor|Block|Damage)$|\([\d,.]+ damage per second\)$")


def _lines(tip: list[tuple[bool, str, str]], name: str | None) -> tuple[list[str], list[str]]:
    """an item's tooltip, its name and what the sheet says elsewhere left out: (its numbers, what it does). A line not known
    to be noise stays, word for word: an item is never shown short of something"""
    stats, text, a_set = [], [], False
    for active, left, right in tip:
        s = left.strip()
        a_set = a_set or bool(re.search(r"\(\d+/\d+\)$", s))
        piece = a_set and left[:1].isspace()
        need = s.startswith("Requires ") and not active         # only a need that is not met is news
        if s == name or (NOT_SAID.match(s) and not need) or s in WORN_AS or piece:
            continue
        off = "" if active else " (not active)" if not need else " (not met)"
        if NUMBER_LINE.match(s) and active:
            stats += [s.removeprefix("(").removesuffix(")") if s.startswith("(") else s] + ([right] if right else [])
        else:
            text.append(f"{s} {right}".strip() + off)
    return stats, text


def _holds(tip: list[tuple[bool, str, str]], stats: dict) -> bool:
    """whether the tooltip has every flat number of the item: without one it was not all there when it was read"""
    said = [left.replace(",", "") for _, left, _ in tip]
    for key, name in STAT_NAME.items():
        if v := abs(stats.get(key) or 0):
            each = [float(x) for s in said for x in re.findall(r"\d+(?:\.\d+)?", s)]
            own = sum(float(m[1]) for s in said if (m := re.match(rf"[+\-−]?(\d+(?:\.\d+)?) {name}$", s)))     # with its enchant's
            if v not in each and v != own:
                return False
    return True


def _flat(stats: dict) -> list[str]:
    """an item's numbers without its tooltip: those that mean the same on every item (a rating's key is not its percent)"""
    weapon = [f"{stats[WEAPON_DPS]:.1f} damage per second"] if stats.get(WEAPON_DPS) else []
    number = lambda v: f"{v:g}" if v == int(v) else f"{v:.1f}"  # noqa: E731
    names = ["RESISTANCE0_NAME"] + [k for k in STAT_NAME if k != "RESISTANCE0_NAME"]
    return weapon + [f"{number(stats[k])} Armor" if STAT_NAME[k] == "Armor" else f"{'+' if stats[k] > 0 else '−'}{number(abs(stats[k]))} {STAT_NAME[k]}"
                     for k in names if stats.get(k)]


def _broken(char: dict, slot: int) -> bool:
    left = (char.get("wear") or {}).get(slot)
    return bool(left) and left[1] > 0 and left[0] == 0


def _all_read(char: dict) -> bool:
    """whether every worn item's stats were read and count (a broken one gives none), so a sum of them is the whole of it"""
    given, tips = char.get("itemstats") or {}, char.get("tips") or {}
    for slot, item in (char.get("items") or {}).items():
        if slot in NO_GEAR_LEVEL:
            continue
        none = slot in tips and not any(re.match(r"[+\-−] ?\d|[\d,]+ Armor$", x) for x in _lines(tips[slot], item["name"])[0])
        if not item.get("name") or _broken(char, slot) or (slot not in given and not none):
            return False
    return True


def _gear(char: dict) -> list[dict]:
    levels, items = char.get("gear") or {}, char.get("items") or {}
    if not levels and not items:            # not read: fourteen empty slots would be a guess
        return []
    given = char.get("itemstats") or {}
    tips = char.get("tips") or {}
    for slot, tip in tips.items():
        if slot in items and (said := next((m for _, s, _ in tip if (m := re.match(r"Item Level (\d+)", s))), None)):
            levels = levels | {slot: int(said[1])}          # what the game shows you
    known = [levels[s] for s, _ in SLOTS if levels.get(s)]
    out = []
    for slot, label in SLOTS:
        item = items.get(slot)
        level, flags = levels.get(slot), []
        if not item and slot not in levels:
            if slot in MAY_BE_EMPTY:
                continue
            flags.append("empty")
        elif item and slot in ENCHANTABLE and item.get("enchant") == 0:
            flags.append("not enchanted")
        if _broken(char, slot):
            flags.insert(0, "broken")
        tip = tips.get(slot) or []
        flat = _flat(given.get(slot) or {})
        stats, text = _lines(tip, (item or {}).get("name"))
        whole = bool(tip) and _holds(tip, given.get(slot) or {})
        if not whole:
            stats, text = flat, []
        if level and known and level == min(known) < max(known) and slot not in NO_GEAR_LEVEL:
            flags.append("lowest")
        out.append({"slot": slot, "label": label, "name": (item or {}).get("name") or None, "level": level,
                    "quality": (item or {}).get("quality"), "enchant": (item or {}).get("enchant"), "flags": flags,
                    "stats": stats, "text": text, "whole": whole or not item})
    return out


def _stats(char: dict) -> dict[str, dict]:
    given, items = char.get("itemstats") or {}, char.get("items") or {}
    out, read, whole = {}, char.get("stats") or {}, _all_read(char)
    for key, value in read.items():
        if key.endswith(("_pos", "_neg")):
            continue
        by: dict[int | None, float] = {}
        for slot, s in given.items() if whole else ():          # part of the gear is not "from gear"
            if (n := s.get(ITEM_KEY.get(key, ""))):
                q = (items.get(slot) or {}).get("quality")
                by[q] = by.get(q, 0) + n
        out[key] = {"value": value, "gear": sum(by.values()) or None, "by_quality": by}
        pos, neg = read.get(f"{key}_pos"), read.get(f"{key}_neg")
        each = [s.get(ITEM_KEY.get(key, "")) or 0 for s in given.values()] if whole else []
        gear, cost = sum(n for n in each if n > 0), -sum(n for n in each if n < 0)      # an item that takes some away
        if value is not None and sum(by.values()) > value:         # more than there is: not a part of it
            out[key] |= {"gear": None, "by_quality": {}}
            continue
        # a bonus under what the items give can't hold them: then it is not split
        if whole and key in ITEM_KEY and None not in (value, pos, neg) and pos >= gear and value - pos + abs(neg) >= 0 and abs(neg) >= cost:
            out[key] |= {"own": value - pos + abs(neg), "buffs": pos - gear, "lost": abs(neg) - cost}
    return out


def _abilities(char: dict, win: list[dict]) -> list[dict]:
    """the spells known, most damage first, then by name. Saved fights carry no cast ids before 0.21, so "lower" is only
    said of fights that do"""
    ids: dict[str, list[int]] = {}
    for sid, name in (char.get("spell_ids") or {}).items():
        if name not in NOT_A_SPELL:
            ids.setdefault(name, []).append(sid)
    ranks = char.get("ranks") or {}
    ab = traits.abilities(win)
    split = ab["split"] or {}
    share = {n: s * split["ability"] for n, s in split.get("names") or []}      # Judgement of Command is Judgement's
    cast: dict[str, set[int]] = {}
    for f in win:
        for name, got in (f.get("cast_ids") or {}).items():
            cast.setdefault(name, set()).update(got)
    out = []
    for name, spells in ids.items():
        order = sorted(spells, key=lambda s: (_number(ranks.get(s)), s))
        top = order[-1]
        mine = cast.get(name, set()) & set(spells)
        out.append({"name": name, "rank": ranks.get(max(mine, key=order.index)) if mine else None, "ranks": len(spells), "casts": (ab["all"].get(name) or [0])[0],
                    "share": share.get(name), "lower": bool(mine) and top not in mine})
    return sorted(out, key=lambda a: (-(a["share"] or 0), -a["casts"], a["name"]))


def _auto(win: list[dict]) -> dict:
    """the shares of your damage that no ability did: {"auto" (swings and shots), "proc"}, empty without damage"""
    split = traits.abilities(win)["split"]
    return {"auto": split["melee"] + split["shot"], "proc": split["proc"]} if split else {}


def _number(rank: str | None) -> int:
    digits = "".join(c for c in rank or "" if c.isdigit())
    return int(digits) if digits else 0


def _projections(char: dict, win: list[dict], stats: dict[str, dict]) -> dict[str, dict]:
    """measured from your fights first, then the game's own figure, then a classic formula while it agrees with the game:
    "dps", "hps", "swing" (seconds), "hit" (your average swing, against "game_low" and "game_high", what the game says it
    does before armor), "ap10" (what 10 attack power adds, damage per second before armor; measured, also "swing", to one swing,
    and "error" of it; "why" it is unknown: "weapon" (its stats are) or "fit")"""
    v = lambda k: (stats.get(k) or {}).get("value")  # noqa: E731
    none = {"value": None, "source": None, "n": 0}
    out = {k: dict(none) for k in ("dps", "hps", "swing", "hit", "ap10")}
    dmg = [f for f in _damage_fights(win) if f.get("damage") and f.get("duration")]
    if len(dmg) >= MIN_DAMAGE:
        out["dps"] = {"value": sum(f["damage"] for f in dmg) / sum(f["duration"] for f in dmg), "source": "measured",
                      "n": len(dmg)}
    heal = [f for f in win if f.get("healing_role") and f.get("healing") and f.get("duration")]
    if len(heal) >= MIN_HEALING:
        out["hps"] = {"value": sum(f["healing"] for f in heal) / sum(f["duration"] for f in heal), "source": "measured",
                      "n": len(heal)}
    speeds = [f["auto"]["speed"] for f in win if (f.get("auto") or {}).get("speed")]
    if len(speeds) >= MIN_SWINGS:
        out["swing"] = {"value": median(speeds), "source": "measured", "n": len(speeds), "game": v("speed")}
    elif v("speed"):
        out["swing"] = {"value": v("speed"), "source": "game", "n": 0}
    melee = [a for f in win for a in f.get("abilities") or [] if a.get("name") == "Melee" and a.get("hits")]
    hits = sum(a["hits"] for a in melee)
    if hits >= MIN_SWINGS:
        out["hit"] = {"value": sum(a["damage"] for a in melee) / hits, "source": "measured", "n": hits,
                      "game_low": v("dmgmin"), "game_high": v("dmgmax")}
    weapon, speed, ap = (char.get("itemstats") or {}).get(16, {}).get(WEAPON_DPS), v("speed"), v("ap")
    out["ap10"]["why"] = "weapon"
    got = worth.swing(win, v("dmgmin"), v("dmgmax"))
    if got and speed:
        out["ap10"] = {"value": 10 * got["value"] / speed, "source": "measured", "n": got["n"], "swing": 10 * got["value"],
                       "error": 10 * got["error"]}
    elif weapon and speed and ap is not None and v("dmgmin") and v("dmgmax"):
        out["ap10"]["why"] = "fit"
        ours = weapon * speed + ap / AP_PER_DPS * speed + (v("dmgbonus") or 0)
        game = (v("dmgmin") + v("dmgmax")) / 2
        if abs(ours - game) <= CLOSE * game:
            out["ap10"] = {"value": 10 / AP_PER_DPS, "source": "estimate", "n": 0}
    return out


def sheet(char: dict | None, win: list[dict], fig: dict | None = None) -> dict | None:
    if not char or not (char.get("stats") or char.get("items")):
        return None
    stats, fig = _stats(char), fig or {}
    return {"taken": char.get("geartaken") or char.get("taken"), "gear": _gear(char), "stats": stats, "abilities": _abilities(char, win),
            "points": char.get("points") or [], "trees": char.get("trees") or [], "skills": char.get("skills") or [],
            "projections": _projections(char, win, stats), "role": fig.get("main_role"), "auto": _auto(win),
            "worth": worth.spells(win, char.get("levels")), "swings": worth.hits(win)}
