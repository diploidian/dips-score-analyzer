"""The character sheet: what the character carries and knows, from the add-on's snapshot (Sheet.lua), joined to how the
window's fights used it. Pure data, plain values; what cannot be known is None, never a guess.

sheet(char, win) -> None without a snapshot that holds one, else {"taken" (the snapshot's time()), "gear", "stats",
"abilities", "points", "trees", "skills", "projections"}. win: the window's fights.

  gear         one per slot of SLOTS: {"slot", "label", "name", "level", "quality", "enchant" (id, 0 none), "flags"}
  stats        {key: {"value" (None: hidden by the game), "gear" (how much of it the items give, None when none does)}}
  abilities    every spell known: {"name", "rank" (highest known, its text), "ranks" (how many), "casts" (in fights),
               "share" (of the window's damage, its procs with it, None without), "lower" (only ranks under the highest one known were cast)}
  projections  {key: {"value", "source" ("measured", "game", "estimate" or None), "n" (what it rests on)}}, see _projections

The combat log's own attack power is another number than the game's (625 against 287 with the same gear and buffs), so it
is not used: the worth of attack power is an estimate, not a measure."""
from __future__ import annotations

from statistics import median

from . import traits
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
WEAPON_DPS = "ITEM_MOD_DAMAGE_PER_SECOND_SHORT"
AP_PER_DPS = 14                         # the classic rule: 14 attack power is one damage per second
NOT_A_SPELL = {"Attack"}                # auto attack is in the book too
CLOSE = 0.10                            # an estimate is shown only this near the game's own figure
MIN_DAMAGE, MIN_HEALING, MIN_SWINGS = 10, 5, 10      # fights a measure needs


def _gear(char: dict) -> list[dict]:
    levels, items = char.get("gear") or {}, char.get("items") or {}
    known = [levels[s] for s, _ in SLOTS if levels.get(s)]
    out = []
    for slot, label in SLOTS:
        item = items.get(slot)
        level, flags = levels.get(slot), []
        if not item and slot not in levels:
            if slot in MAY_BE_EMPTY:
                continue
            flags.append("empty")
        elif item and slot in ENCHANTABLE and not item.get("enchant"):
            flags.append("not enchanted")
        if level and len(known) > 1 and level == min(known) and slot not in NO_GEAR_LEVEL:
            flags.append("lowest")
        out.append({"slot": slot, "label": label, "name": (item or {}).get("name") or None, "level": level,
                    "quality": (item or {}).get("quality"), "enchant": (item or {}).get("enchant"), "flags": flags})
    return out


def _stats(char: dict) -> dict[str, dict]:
    given = char.get("itemstats") or {}
    out = {}
    for key, value in (char.get("stats") or {}).items():
        got = [s[ITEM_KEY[key]] for s in given.values() if key in ITEM_KEY and ITEM_KEY[key] in s]
        out[key] = {"value": value, "gear": sum(got) if got else None}
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
        out.append({"name": name, "rank": ranks.get(top), "ranks": len(spells), "casts": (ab["all"].get(name) or [0])[0],
                    "share": share.get(name), "lower": bool(mine) and top not in mine})
    return sorted(out, key=lambda a: (-(a["share"] or 0), -a["casts"], a["name"]))


def _number(rank: str | None) -> int:
    digits = "".join(c for c in rank or "" if c.isdigit())
    return int(digits) if digits else 0


def _projections(char: dict, win: list[dict], stats: dict[str, dict]) -> dict[str, dict]:
    """measured from your fights first, then the game's own figure, then a classic formula while it agrees with the game:
    "dps", "hps", "swing" (seconds), "hit" (your average swing, against "game_low" and "game_high", what the game says it
    does before armor), "ap10" (what 10 attack power adds, damage per second before armor; "why" it is unknown:
    "weapon" (its stats are) or "fit")"""
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
    if weapon and speed and ap is not None and v("dmgmin") and v("dmgmax"):
        out["ap10"]["why"] = "fit"
        ours = weapon * speed + ap / AP_PER_DPS * speed + (v("dmgbonus") or 0)
        game = (v("dmgmin") + v("dmgmax")) / 2
        if abs(ours - game) <= CLOSE * game:
            out["ap10"] = {"value": 10 / AP_PER_DPS, "source": "estimate", "n": 0}
    return out


def sheet(char: dict | None, win: list[dict]) -> dict | None:
    if not char or not (char.get("stats") or char.get("items")):
        return None
    stats = _stats(char)
    return {"taken": char.get("taken"), "gear": _gear(char), "stats": stats, "abilities": _abilities(char, win),
            "points": char.get("points") or [], "trees": char.get("trees") or [], "skills": char.get("skills") or [],
            "projections": _projections(char, win, stats)}
